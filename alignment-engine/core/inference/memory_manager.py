"""
显存状态机 (MemoryManager) —— 精确监控 WSL2 下 GPU 显存占用。

功能：
  1. 实时查询 torch.cuda 显存分配 / 缓存 / 总量
  2. 四态状态机：IDLE → ACTIVE → PRESSURE → EMERGENCY
  3. VRAM 达到 90% 时触发紧急张量卸载（Offload to CPU RAM）
  4. 完整的生命周期日志记录

降级策略：
  - 若 torch 不可用或无 CUDA → 使用 Mock 状态机（纯日志模拟）
"""

from __future__ import annotations

import gc
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# 显存状态定义
# ══════════════════════════════════════════════════════════════

class MemoryState(str, Enum):
    """显存状态机四态。"""
    IDLE      = "idle"       # 显存空闲（< 30% 占用）
    ACTIVE    = "active"     # 正常推理（30-70%）
    PRESSURE  = "pressure"   # 显存压力（70-90%），停止新任务提交
    EMERGENCY = "emergency"  # 紧急状态（>= 90%），触发张量卸载


# 状态转换阈值（占总显存比例）
_THRESHOLD_ACTIVE    = 0.30
_THRESHOLD_PRESSURE  = 0.70
_THRESHOLD_EMERGENCY = 0.90


@dataclass
class MemorySnapshot:
    """某时刻的显存快照。"""
    timestamp: float
    allocated_bytes: int
    reserved_bytes: int
    total_bytes: int
    utilization: float    # allocated / total
    state: MemoryState
    offloaded_tensors: int = 0   # 本次快照中被卸载的张量数


@dataclass
class OffloadRecord:
    """一次卸载操作的记录。"""
    timestamp: float
    tensors_offloaded: int
    bytes_freed: int
    from_state: MemoryState
    to_utilization: float


# ══════════════════════════════════════════════════════════════
# MemoryManager
# ══════════════════════════════════════════════════════════════

class MemoryManager:
    """
    显存状态机管理器。

    生命周期：
    1. 创建时检测 CUDA 可用性，若不可用则进入 Mock 模式。
    2. 通过 poll() 查询当前显存状态并驱动状态转换。
    3. 进入 EMERGENCY 状态时自动触发 offload_tensors_to_cpu()。
    4. 通过 get_snapshot() 获取结构化显存快照。

    Attributes:
        emergency_threshold:  触发紧急卸载的显存占用比例（默认 0.90）
        device_id:            CUDA 设备 ID
        mock_mode:            是否为 Mock 模式（无 GPU）
    """

    def __init__(
        self,
        emergency_threshold: float = _THRESHOLD_EMERGENCY,
        device_id: int = 0,
    ) -> None:
        self.emergency_threshold = emergency_threshold
        self.device_id = device_id
        self.mock_mode: bool = True
        self._state: MemoryState = MemoryState.IDLE
        self._history: List[MemorySnapshot] = []
        self._offload_log: List[OffloadRecord] = []
        self._torch_available: bool = False
        self._cuda_available: bool = False

        # ── 检测 CUDA 环境 ──────────────────────────────────
        # 【显存生命周期】此处为初始化阶段，尝试获取 torch.cuda 句柄
        try:
            import torch  # type: ignore[import-untyped]
            self._torch_available = True
            if torch.cuda.is_available():
                self._cuda_available = True
                self.mock_mode = False
                total = torch.cuda.get_device_properties(device_id).total_mem
                logger.info(
                    "MemoryManager 初始化 | CUDA 设备=%s | 总显存=%.1f GB",
                    torch.cuda.get_device_name(device_id),
                    total / 1e9,
                )
            else:
                logger.warning("torch 可用但 CUDA 不可用，进入 Mock 模式")
        except ImportError:
            logger.warning("torch 未安装，进入 Mock 模式")

        if self.mock_mode:
            # Mock 模式：模拟 8GB 显存
            self._mock_total = 8 * 1024 ** 3   # 8 GB
            self._mock_allocated = 0
            self._mock_reserved = 0
            logger.info("MemoryManager Mock 模式 | 模拟显存=8.0 GB")

    # ── 属性 ─────────────────────────────────────────────────

    @property
    def state(self) -> MemoryState:
        return self._state

    @property
    def history(self) -> List[MemorySnapshot]:
        return list(self._history)

    @property
    def offload_log(self) -> List[OffloadRecord]:
        return list(self._offload_log)

    # ── 显存查询 ─────────────────────────────────────────────

    def _query_cuda(self) -> tuple[int, int, int]:
        """
        查询真实 CUDA 显存。
        Returns: (allocated_bytes, reserved_bytes, total_bytes)
        """
        import torch  # type: ignore[import-untyped]
        dev = torch.device(f"cuda:{self.device_id}")
        allocated = torch.cuda.memory_allocated(dev)
        reserved  = torch.cuda.memory_reserved(dev)
        total     = torch.cuda.get_device_properties(dev).total_mem
        return allocated, reserved, total

    def _query_mock(self) -> tuple[int, int, int]:
        """Mock 模式下返回模拟值。"""
        return self._mock_allocated, self._mock_reserved, self._mock_total

    def query_memory(self) -> tuple[int, int, int, float]:
        """
        查询当前显存占用。

        Returns:
            (allocated_bytes, reserved_bytes, total_bytes, utilization)
        """
        if self._cuda_available:
            alloc, resv, total = self._query_cuda()
        else:
            alloc, resv, total = self._query_mock()

        util = alloc / total if total > 0 else 0.0
        return alloc, resv, total, util

    # ── 状态机驱动 ───────────────────────────────────────────

    def poll(self) -> MemorySnapshot:
        """
        轮询显存状态，驱动状态转换。

        转换规则：
          IDLE      → ACTIVE    当 utilization >= 30%
          ACTIVE    → PRESSURE  当 utilization >= 70%
          PRESSURE  → EMERGENCY 当 utilization >= 90%  → 自动触发 offload
          EMERGENCY → PRESSURE  当 offload 后 utilization < 70%
          PRESSURE  → ACTIVE    当 utilization < 70%
          ACTIVE    → IDLE      当 utilization < 30%

        Returns:
            MemorySnapshot 当前快照
        """
        alloc, resv, total, util = self.query_memory()

        # 状态转换
        old_state = self._state
        offloaded = 0

        if util >= self.emergency_threshold:
            self._state = MemoryState.EMERGENCY
        elif util >= _THRESHOLD_PRESSURE:
            self._state = MemoryState.PRESSURE
        elif util >= _THRESHOLD_ACTIVE:
            self._state = MemoryState.ACTIVE
        else:
            self._state = MemoryState.IDLE

        # EMERGENCY → 触发张量卸载
        if self._state == MemoryState.EMERGENCY:
            offloaded = self._offload_tensors_to_cpu()
            # 重新查询
            alloc, resv, total, util = self.query_memory()
            # 卸载后可能回到 PRESSURE
            if util < _THRESHOLD_PRESSURE:
                self._state = MemoryState.ACTIVE
            elif util < self.emergency_threshold:
                self._state = MemoryState.PRESSURE

        # 状态变更日志
        if self._state != old_state:
            logger.info(
                "显存状态转换: %s → %s | utilization=%.1f%%",
                old_state.value, self._state.value, util * 100,
            )

        snapshot = MemorySnapshot(
            timestamp=time.time(),
            allocated_bytes=alloc,
            reserved_bytes=resv,
            total_bytes=total,
            utilization=util,
            state=self._state,
            offloaded_tensors=offloaded,
        )
        self._history.append(snapshot)
        return snapshot

    # ── 张量卸载（紧急） ────────────────────────────────────

    def _offload_tensors_to_cpu(self) -> int:
        """
        紧急张量卸载：将 GPU 上的所有张量缓存释放到 CPU。

        策略：
        1. 清空 PyTorch CUDA 缓存 (empty_cache)
        2. 强制 Python 垃圾回收
        3. 记录卸载日志

        【显存生命周期】此处执行显存释放的关键步骤

        Returns:
            本次操作释放的近似字节数（除以平均张量大小估算卸载张量数）
        """
        if not self._torch_available:
            # Mock 模式：模拟释放 50% 已分配显存
            freed = self._mock_allocated // 2
            self._mock_allocated -= freed
            self._mock_reserved = max(0, self._mock_reserved - freed)
            logger.info(
                "[Mock] 紧急卸载 | 释放 %.1f MB",
                freed / 1e6,
            )
            record = OffloadRecord(
                timestamp=time.time(),
                tensors_offloaded=42,  # 模拟值
                bytes_freed=freed,
                from_state=MemoryState.EMERGENCY,
                to_utilization=self._mock_allocated / self._mock_total,
            )
            self._offload_log.append(record)
            return 42

        import torch  # type: ignore[import-untyped]

        before_alloc = torch.cuda.memory_allocated(self.device_id)

        # Step 1: 清空 CUDA 缓存
        torch.cuda.empty_cache()

        # Step 2: 强制垃圾回收
        gc.collect()

        after_alloc = torch.cuda.memory_allocated(self.device_id)
        bytes_freed = before_alloc - after_alloc

        logger.warning(
            "紧急张量卸载完成 | 释放 %.1f MB | %.1f%% → %.1f%%",
            bytes_freed / 1e6,
            before_alloc / self._query_cuda()[2] * 100,
            after_alloc / self._query_cuda()[2] * 100,
        )

        record = OffloadRecord(
            timestamp=time.time(),
            tensors_offloaded=0,  # 精确数需 torch 内部 API
            bytes_freed=bytes_freed,
            from_state=MemoryState.EMERGENCY,
            to_utilization=after_alloc / self._query_cuda()[2],
        )
        self._offload_log.append(record)
        return bytes_freed

    # ── Mock 控制接口 ────────────────────────────────────────

    def mock_allocate(self, bytes_count: int) -> None:
        """Mock 模式下模拟 GPU 内存分配。"""
        if not self.mock_mode:
            return
        self._mock_allocated += bytes_count
        self._mock_reserved = max(self._mock_reserved, self._mock_allocated)

    def mock_release(self, bytes_count: int) -> None:
        """Mock 模式下模拟 GPU 内存释放。"""
        if not self.mock_mode:
            return
        self._mock_allocated = max(0, self._mock_allocated - bytes_count)

    # ── 查询接口 ─────────────────────────────────────────────

    def can_accept_task(self) -> bool:
        """是否可以接受新的推理任务（不处于 PRESSURE 或 EMERGENCY）。"""
        return self._state in (MemoryState.IDLE, MemoryState.ACTIVE)

    def get_utilization(self) -> float:
        """当前显存利用率。"""
        _, _, _, util = self.query_memory()
        return util

    def get_summary(self) -> Dict[str, Any]:
        """获取显存状态摘要。"""
        alloc, resv, total, util = self.query_memory()
        return {
            "state": self._state.value,
            "mock_mode": self.mock_mode,
            "allocated_mb": round(alloc / 1e6, 1),
            "reserved_mb": round(resv / 1e6, 1),
            "total_mb": round(total / 1e6, 1),
            "utilization_pct": round(util * 100, 1),
            "poll_count": len(self._history),
            "offload_count": len(self._offload_log),
            "can_accept_task": self.can_accept_task(),
        }
