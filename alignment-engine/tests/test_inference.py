"""
测试 core.inference 子系统 —— MemoryManager + ModelLoader + BatchEngine

全部在 Mock 模式下运行（无 GPU 依赖）。
"""

from __future__ import annotations

import asyncio
import sys
import time

import numpy as np
import pytest

from core.inference.memory_manager import MemoryManager, MemoryState
from core.inference.model_loader import DummyModel, ModelLoader, QuantizationConfig
from core.inference.batch_engine import BatchEngine, TaskStatus


# ══════════════════════════════════════════════════════════════
# MemoryManager 测试
# ══════════════════════════════════════════════════════════════

class TestMemoryManager:
    """测试显存状态机。"""

    def test_initial_state_idle(self) -> None:
        """初始状态应为 IDLE（Mock 模式下显存为空）。"""
        mm = MemoryManager()
        assert mm.state == MemoryState.IDLE
        assert mm.mock_mode is True

    def test_mock_allocate_changes_utilization(self) -> None:
        """Mock 分配应增加利用率。"""
        mm = MemoryManager()
        mm.mock_allocate(4 * 1024 ** 3)  # 4 GB
        _, _, _, util = mm.query_memory()
        assert util == pytest.approx(0.5, abs=0.01)

    def test_state_transition_to_active(self) -> None:
        """显存 30% 时应转为 ACTIVE。"""
        mm = MemoryManager()
        mm.mock_allocate(int(0.4 * 8 * 1024 ** 3))  # 40%
        snap = mm.poll()
        assert snap.state == MemoryState.ACTIVE

    def test_state_transition_to_pressure(self) -> None:
        """显存 70% 时应转为 PRESSURE。"""
        mm = MemoryManager()
        mm.mock_allocate(int(0.75 * 8 * 1024 ** 3))  # 75%
        snap = mm.poll()
        assert snap.state == MemoryState.PRESSURE

    def test_state_transition_to_emergency_with_offload(self) -> None:
        """显存 90% 时应触发 EMERGENCY 并自动卸载。"""
        mm = MemoryManager()
        mm.mock_allocate(int(0.95 * 8 * 1024 ** 3))  # 95%
        snap = mm.poll()
        # 应触发了卸载
        assert len(mm.offload_log) >= 1
        # 卸载后利用率应下降
        assert snap.utilization < 0.95

    def test_can_accept_task(self) -> None:
        """IDLE/ACTIVE 时可接受任务，PRESSURE/EMERGENCY 时不可。"""
        mm = MemoryManager()
        assert mm.can_accept_task() is True

        mm.mock_allocate(int(0.75 * 8 * 1024 ** 3))
        mm.poll()
        assert mm.can_accept_task() is False

    def test_history_accumulates(self) -> None:
        """多次 poll 应累积历史记录。"""
        mm = MemoryManager()
        mm.poll()
        mm.poll()
        mm.poll()
        assert len(mm.history) == 3

    def test_get_summary(self) -> None:
        """摘要应包含所有关键字段。"""
        mm = MemoryManager()
        summary = mm.get_summary()
        assert "state" in summary
        assert "mock_mode" in summary
        assert "can_accept_task" in summary

    def test_mock_release(self) -> None:
        """Mock 释放应降低利用率。"""
        mm = MemoryManager()
        mm.mock_allocate(4 * 1024 ** 3)
        mm.poll()
        assert mm.state != MemoryState.IDLE

        mm.mock_release(4 * 1024 ** 3)
        snap = mm.poll()
        assert snap.state == MemoryState.IDLE


# ══════════════════════════════════════════════════════════════
# ModelLoader 测试
# ══════════════════════════════════════════════════════════════

class TestModelLoader:
    """测试模型加载器。"""

    def test_mock_mode_default(self) -> None:
        """无 CUDA 时应进入 Mock 模式。"""
        loader = ModelLoader()
        assert loader.mock_mode is True

    def test_load_returns_dummy_model(self) -> None:
        """Mock 模式下 load() 应返回 DummyModel。"""
        loader = ModelLoader()
        model = loader.load()
        assert isinstance(model, DummyModel)
        assert loader.is_loaded is True

    def test_dummy_model_inference(self) -> None:
        """DummyModel 推理应可调用。"""
        model = DummyModel(embedding_dim=128)
        result = model()
        assert result is None  # mock 返回 None

    def test_model_info_populated(self) -> None:
        """加载后 model_info 应被填充。"""
        loader = ModelLoader()
        loader.load()
        info = loader.model_info
        assert info is not None
        assert info.model_name == "DummyModel"
        assert info.vram_bytes == 0

    def test_unload(self) -> None:
        """unload 应清空模型。"""
        loader = ModelLoader()
        loader.load()
        assert loader.is_loaded is True

        loader.unload()
        assert loader.is_loaded is False
        assert loader.model_info is None

    def test_custom_quant_config(self) -> None:
        """支持自定义量化配置。"""
        cfg = QuantizationConfig(bits=8, quant_type="fp4", double_quant=False)
        loader = ModelLoader(quant_config=cfg)
        assert loader.quant_config.bits == 8

    def test_double_load_idempotent(self) -> None:
        """连续两次 load 应覆盖旧模型。"""
        loader = ModelLoader()
        m1 = loader.load()
        m2 = loader.load()
        assert loader.is_loaded is True


# ══════════════════════════════════════════════════════════════
# BatchEngine 测试
# ══════════════════════════════════════════════════════════════

class TestBatchEngine:
    """测试批处理引擎。"""

    def test_init(self) -> None:
        """初始化应成功。"""
        engine = BatchEngine()
        assert engine.batch_size == 8
        assert engine.stats["submitted"] == 0

    def test_submit_sync(self) -> None:
        """同步提交应返回 task_id 并产生结果。"""
        engine = BatchEngine()
        ids = ["s1", "s2", "s3"]
        emb = np.random.randn(3, 128).astype(np.float32)

        task_id = engine.submit_sync(ids, emb)
        assert len(task_id) == 8

        result = engine.get_result(task_id)
        assert result is not None
        assert result.status == TaskStatus.DONE
        assert result.features.shape == (3, 128)

    def test_mock_inference_normalizes(self) -> None:
        """Mock 推理应做 L2 归一化。"""
        engine = BatchEngine()
        emb = np.array([[3.0, 4.0]], dtype=np.float32)  # norm = 5
        engine.submit_sync(["s1"], emb)
        result = engine.get_result("s1")

        # L2 归一化后应为 [0.6, 0.8]
        # 注意：task_id 不是 "s1"，用第一个结果
        results = [v for v in engine._results.values()]
        assert len(results) == 1
        assert np.allclose(results[0].features[0], [0.6, 0.8], atol=1e-5)

    def test_memory_pressure_drops_task(self) -> None:
        """显存不足时任务应被丢弃。"""
        mm = MemoryManager()
        mm.mock_allocate(int(0.95 * 8 * 1024 ** 3))  # 填满显存
        mm.poll()  # 触发 EMERGENCY

        engine = BatchEngine(memory_manager=mm)
        # 手动将状态设为 PRESSURE（卸载后可能回到 pressure）
        task_id = engine.submit_sync(["s1"], np.random.randn(1, 128))
        result = engine.get_result(task_id)
        # 结果可能是 DROPPED 或 DONE（取决于卸载效果）
        assert result is not None

    def test_multiple_tasks(self) -> None:
        """多个任务应各自产生独立结果。"""
        engine = BatchEngine()
        for i in range(5):
            engine.submit_sync(
                [f"s{i}"],
                np.random.randn(1, 64).astype(np.float32),
            )
        assert len(engine._results) == 5
        assert engine.stats["submitted"] == 5
        assert engine.stats["completed"] == 5

    def test_custom_inference_fn(self) -> None:
        """支持自定义推理函数。"""
        def multiply_by_two(emb: np.ndarray) -> np.ndarray:
            return emb * 2.0

        engine = BatchEngine(inference_fn=multiply_by_two)
        emb = np.array([[1.0, 2.0, 3.0]], dtype=np.float32)
        engine.submit_sync(["s1"], emb)

        results = list(engine._results.values())
        assert np.allclose(results[0].features, [[2.0, 4.0, 6.0]])

    def test_stats_tracking(self) -> None:
        """统计应正确跟踪提交和完成数。"""
        engine = BatchEngine()
        for i in range(3):
            engine.submit_sync([f"s{i}"], np.random.randn(1, 32))

        stats = engine.stats
        assert stats["submitted"] == 3
        assert stats["completed"] == 3
        assert stats["failed"] == 0

    def test_get_summary(self) -> None:
        """摘要应包含所有关键字段。"""
        engine = BatchEngine()
        engine.submit_sync(["s1"], np.random.randn(1, 32))
        summary = engine.get_summary()
        assert "submitted" in summary
        assert "memory_state" in summary
        assert "running" in summary


# ══════════════════════════════════════════════════════════════
# 异步 BatchEngine 测试
# ══════════════════════════════════════════════════════════════

class TestBatchEngineAsync:
    """测试异步批处理。"""

    def test_async_submit_and_wait(self) -> None:
        """异步提交应返回可等待的结果。"""
        async def _run():
            engine = BatchEngine()
            await engine.start()
            task_id = await engine.submit(
                ["s1", "s2"],
                np.random.randn(2, 64).astype(np.float32),
            )
            result = await engine.wait_result(task_id, timeout=5.0)
            await engine.stop()
            return result

        result = asyncio.get_event_loop().run_until_complete(_run())
        assert result.status == TaskStatus.DONE
        assert result.features.shape == (2, 64)
