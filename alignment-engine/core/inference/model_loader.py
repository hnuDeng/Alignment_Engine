"""
模型加载优化器 (ModelLoader) —— 4-bit 量化 + FP16 混合精度 VLM 加载。

功能：
  1. 使用 BitsAndBytes 4-bit NF4 量化加载大型 VLM（如 LLaVA）
  2. FP16 混合精度推理准备
  3. 显存感知的模型放置策略（自动检测可用 VRAM）
  4. 完整的 Mock 降级（无 GPU 时返回 Dummy 模型包装器）

显存生命周期注释：
  - 模型加载时在 GPU 上分配 ~4-6 GB（4-bit LLaVA-7B）
  - 每次推理前检查 MemoryManager 状态
  - 推理完成后通过 unload() 显式释放
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# 模型配置
# ══════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class QuantizationConfig:
    """量化配置。"""
    enabled: bool = True
    bits: int = 4                       # 4-bit NF4
    quant_type: str = "nf4"             # nf4 / fp4
    compute_dtype: str = "float16"      # 计算精度
    double_quant: bool = True           # 双重量化（更省显存）
    # 显存生命周期：4-bit 量化将 7B 模型从 ~14GB 压缩到 ~4GB


@dataclass(frozen=True)
class ModelLoadConfig:
    """模型加载配置。"""
    model_name: str = "llava-hf/llava-1.5-7b-hf"
    device_map: str = "auto"            # 自动放置到可用 GPU
    max_memory: Optional[Dict[int, str]] = None  # 如 {0: "6GiB"}
    torch_dtype: str = "float16"        # 推理精度
    trust_remote_code: bool = True
    low_cpu_mem_usage: bool = True      # 低 CPU 内存占用加载


# ══════════════════════════════════════════════════════════════
# 模型包装器
# ══════════════════════════════════════════════════════════════

@dataclass
class ModelInfo:
    """已加载模型的信息。"""
    model_name: str
    device_map: str
    quantized: bool
    quant_bits: int
    dtype: str
    load_time_seconds: float
    parameter_count: int
    vram_bytes: int  # 占用的 GPU 显存（字节）


class DummyModel:
    """
    Mock 模式下的 Dummy 模型包装器。

    模拟推理行为，返回随机特征向量。
    用于无 GPU / 无 transformers 环境下的降级运行。
    """

    def __init__(self, embedding_dim: int = 4096) -> None:
        self.embedding_dim = embedding_dim
        self._call_count = 0
        logger.info("DummyModel 初始化 | embedding_dim=%d", embedding_dim)

    def generate(self, **kwargs) -> Any:
        """模拟推理，返回 None。"""
        self._call_count += 1
        logger.debug("DummyModel.generate() 调用 #%d", self._call_count)
        return None

    def __call__(self, *args, **kwargs) -> Any:
        return self.generate(**kwargs)

    def to(self, device: str) -> "DummyModel":
        """模拟 device 迁移（no-op）。"""
        return self

    def eval(self) -> "DummyModel":
        """模拟 eval 模式切换。"""
        return self


# ══════════════════════════════════════════════════════════════
# ModelLoader
# ══════════════════════════════════════════════════════════════

class ModelLoader:
    """
    模型加载优化器。

    支持三种加载模式：
    1. 4-bit 量化 (BitsAndBytes NF4) — 首选，最省显存
    2. FP16 半精度 — 次选
    3. Mock Dummy — 无 GPU 降级

    Attributes:
        quant_config:   量化配置
        load_config:    模型加载配置
        mock_mode:      是否为 Mock 模式
    """

    def __init__(
        self,
        quant_config: Optional[QuantizationConfig] = None,
        load_config: Optional[ModelLoadConfig] = None,
    ) -> None:
        self.quant_config = quant_config or QuantizationConfig()
        self.load_config = load_config or ModelLoadConfig()
        self.mock_mode: bool = True
        self._model: Any = None
        self._processor: Any = None
        self._model_info: Optional[ModelInfo] = None
        self._torch_available: bool = False
        self._cuda_available: bool = False

        # ── 检测环境 ────────────────────────────────────────
        try:
            import torch  # type: ignore[import-untyped]
            self._torch_available = True
            if torch.cuda.is_available():
                self._cuda_available = True
                self.mock_mode = False
                logger.info(
                    "ModelLoader | CUDA 可用 | 设备=%s | 显存=%.1f GB",
                    torch.cuda.get_device_name(0),
                    torch.cuda.get_device_properties(0).total_mem / 1e9,
                )
        except ImportError:
            logger.warning("torch 未安装，ModelLoader 进入 Mock 模式")

    # ── 模型加载 ─────────────────────────────────────────────

    def load(self) -> Any:
        """
        加载模型。

        优先尝试 4-bit 量化加载；若 BitsAndBytes 不可用则回退 FP16；
        若 CUDA 不可用则返回 DummyModel。

        【显存生命周期】加载时在 GPU 上分配显存，需配合 MemoryManager 监控。

        Returns:
            加载好的模型对象（transformers 模型或 DummyModel）
        """
        if self.mock_mode:
            return self._load_dummy()

        try:
            return self._load_quantized_4bit()
        except ImportError:
            logger.warning("BitsAndBytes 不可用，回退到 FP16 加载")
            try:
                return self._load_fp16()
            except Exception as exc:
                logger.error("FP16 加载失败: %s，回退到 DummyModel", exc)
                return self._load_dummy()
        except Exception as exc:
            logger.error("4-bit 量化加载失败: %s，回退到 FP16", exc)
            try:
                return self._load_fp16()
            except Exception:
                return self._load_dummy()

    def _load_quantized_4bit(self) -> Any:
        """
        4-bit NF4 量化加载。

        【显存生命周期】加载时 GPU 显存增长 ~4 GB (7B 模型)
        """
        import torch  # type: ignore[import-untyped]
        from transformers import AutoModelForCausalLM, AutoProcessor  # type: ignore[import-untyped]
        from transformers import BitsAndBytesConfig  # type: ignore[import-untyped]

        t0 = time.time()

        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type=self.quant_config.quant_type,
            bnb_4bit_compute_dtype=getattr(torch, self.quant_config.compute_dtype),
            bnb_4bit_use_double_quant=self.quant_config.double_quant,
        )

        max_mem = self.load_config.max_memory
        if max_mem is None:
            # 自动计算：预留 1 GB 给推理
            total = torch.cuda.get_device_properties(0).total_mem
            usable = int(total * 0.85)  # 使用 85% 显存
            max_mem = {0: f"{usable // (1024**2)}MiB"}

        logger.info(
            "开始 4-bit 量化加载 | model=%s | max_memory=%s",
            self.load_config.model_name, max_mem,
        )

        model = AutoModelForCausalLM.from_pretrained(
            self.load_config.model_name,
            quantization_config=bnb_config,
            device_map=self.load_config.device_map,
            max_memory=max_mem,
            trust_remote_code=self.load_config.trust_remote_code,
            low_cpu_mem_usage=self.load_config.low_cpu_mem_usage,
        )

        processor = AutoProcessor.from_pretrained(
            self.load_config.model_name,
            trust_remote_code=self.load_config.trust_remote_code,
        )

        load_time = time.time() - t0
        vram = torch.cuda.memory_allocated(0)

        self._model = model
        self._processor = processor
        self._model_info = ModelInfo(
            model_name=self.load_config.model_name,
            device_map=self.load_config.device_map,
            quantized=True,
            quant_bits=4,
            dtype=self.quant_config.compute_dtype,
            load_time_seconds=round(load_time, 2),
            parameter_count=sum(p.numel() for p in model.parameters()),
            vram_bytes=vram,
        )

        logger.info(
            "4-bit 量化加载完成 | 耗时=%.1fs | 参数量=%s | VRAM=%.1f GB",
            load_time,
            f"{self._model_info.parameter_count / 1e9:.1f}B",
            vram / 1e9,
        )

        return model

    def _load_fp16(self) -> Any:
        """
        FP16 半精度加载（不使用量化）。

        【显存生命周期】加载时 GPU 显存增长 ~14 GB (7B 模型 FP16)
        """
        import torch  # type: ignore[import-untyped]
        from transformers import AutoModelForCausalLM, AutoProcessor  # type: ignore[import-untyped]

        t0 = time.time()

        model = AutoModelForCausalLM.from_pretrained(
            self.load_config.model_name,
            torch_dtype=getattr(torch, self.load_config.torch_dtype),
            device_map=self.load_config.device_map,
            trust_remote_code=self.load_config.trust_remote_code,
            low_cpu_mem_usage=self.load_config.low_cpu_mem_usage,
        )

        processor = AutoProcessor.from_pretrained(
            self.load_config.model_name,
            trust_remote_code=self.load_config.trust_remote_code,
        )

        load_time = time.time() - t0
        vram = torch.cuda.memory_allocated(0)

        self._model = model
        self._processor = processor
        self._model_info = ModelInfo(
            model_name=self.load_config.model_name,
            device_map=self.load_config.device_map,
            quantized=False,
            quant_bits=16,
            dtype=self.load_config.torch_dtype,
            load_time_seconds=round(load_time, 2),
            parameter_count=sum(p.numel() for p in model.parameters()),
            vram_bytes=vram,
        )

        logger.info(
            "FP16 加载完成 | 耗时=%.1fs | VRAM=%.1f GB",
            load_time, vram / 1e9,
        )

        return model

    def _load_dummy(self) -> DummyModel:
        """Mock 模式加载 DummyModel。"""
        model = DummyModel()
        self._model = model
        self._model_info = ModelInfo(
            model_name="DummyModel",
            device_map="cpu",
            quantized=False,
            quant_bits=0,
            dtype="mock",
            load_time_seconds=0.0,
            parameter_count=0,
            vram_bytes=0,
        )
        return model

    # ── 模型卸载 ─────────────────────────────────────────────

    def unload(self) -> None:
        """
        显式卸载模型并释放显存。

        【显存生命周期】调用后 GPU 显存应恢复到加载前的水平。
        """
        import gc

        if self._model is not None:
            del self._model
            self._model = None
        if self._processor is not None:
            del self._processor
            self._processor = None

        gc.collect()

        if self._torch_available and self._cuda_available:
            import torch  # type: ignore[import-untyped]
            torch.cuda.empty_cache()
            remaining = torch.cuda.memory_allocated(0)
            logger.info("模型已卸载 | 剩余 VRAM=%.1f MB", remaining / 1e6)
        else:
            logger.info("[Mock] 模型已卸载")

        self._model_info = None

    # ── 查询接口 ─────────────────────────────────────────────

    @property
    def model(self) -> Any:
        return self._model

    @property
    def processor(self) -> Any:
        return self._processor

    @property
    def model_info(self) -> Optional[ModelInfo]:
        return self._model_info

    @property
    def is_loaded(self) -> bool:
        return self._model is not None
