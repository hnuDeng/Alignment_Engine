"""
异步队列批处理引擎 (BatchEngine) —— 无状态推理调度。

功能：
  1. 接收 Extractor 传来的多个特征切片，提交到异步队列
  2. 后台 worker 按批次打包送入 GPU 计算
  3. 计算完成后显式调用 torch.cuda.empty_cache() + gc.collect()
  4. 与 MemoryManager 联动：PRESSURE/EMERGENCY 时暂停提交

显存生命周期注释：
  - 每个 batch 推理时 GPU 显存临时增长（激活值缓存）
  - 推理完成后立即 empty_cache() 释放
  - EMERGENCY 时暂停所有新任务直到显存恢复
"""

from __future__ import annotations

import asyncio
import gc
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from core.inference.memory_manager import MemoryManager, MemoryState

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# 任务与结果定义
# ══════════════════════════════════════════════════════════════

class TaskStatus(str, Enum):
    PENDING  = "pending"
    RUNNING  = "running"
    DONE     = "done"
    FAILED   = "failed"
    DROPPED  = "dropped"   # 显存不足时被丢弃


@dataclass
class InferenceTask:
    """单个推理任务。"""
    task_id: str
    sample_ids: List[str]
    embeddings: np.ndarray    # shape (N, D)
    created_at: float
    priority: int = 0         # 越大越优先


@dataclass
class InferenceResult:
    """推理结果。"""
    task_id: str
    sample_ids: List[str]
    features: np.ndarray      # 输出特征
    status: TaskStatus
    processing_time_ms: float
    error: Optional[str] = None


# ══════════════════════════════════════════════════════════════
# 推理函数类型
# ══════════════════════════════════════════════════════════════

# 推理函数签名：接收嵌入矩阵，返回处理后的特征矩阵
InferenceFn = Callable[[np.ndarray], np.ndarray]


def _mock_inference_fn(embeddings: np.ndarray) -> np.ndarray:
    """Mock 推理函数：简单的 L2 归一化。"""
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return embeddings / norms


# ══════════════════════════════════════════════════════════════
# BatchEngine
# ══════════════════════════════════════════════════════════════

class BatchEngine:
    """
    异步队列批处理推理引擎。

    工作流程：
    1. submit() 将任务加入优先级队列
    2. 后台 worker 循环：
       a. 从队列中收集最多 batch_size 个任务
       b. 检查 MemoryManager 状态
       c. 若可执行，将嵌入拼接为 batch 送入推理函数
       d. 推理完成后：empty_cache() + gc.collect()
       e. 分发结果

    Attributes:
        memory_manager:  显存管理器
        inference_fn:    推理函数
        batch_size:      批次大小
        max_queue_size:  最大队列深度
        poll_interval:   worker 轮询间隔（秒）
    """

    def __init__(
        self,
        memory_manager: Optional[MemoryManager] = None,
        inference_fn: Optional[InferenceFn] = None,
        batch_size: int = 8,
        max_queue_size: int = 128,
        poll_interval: float = 0.1,
    ) -> None:
        self.memory_manager = memory_manager or MemoryManager()
        self.inference_fn = inference_fn or _mock_inference_fn
        self.batch_size = batch_size
        self.max_queue_size = max_queue_size
        self.poll_interval = poll_interval

        self._queue: asyncio.PriorityQueue[tuple[int, float, InferenceTask]] = (
            asyncio.PriorityQueue(maxsize=max_queue_size)
        )
        self._results: Dict[str, InferenceResult] = {}
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None  # type: ignore[type-arg]
        self._stats = {
            "submitted": 0,
            "completed": 0,
            "failed": 0,
            "dropped": 0,
            "total_processing_ms": 0.0,
        }

        logger.info(
            "BatchEngine 初始化 | batch_size=%d | max_queue=%d",
            batch_size, max_queue_size,
        )

    # ── 提交接口 ─────────────────────────────────────────────

    async def submit(
        self,
        sample_ids: List[str],
        embeddings: np.ndarray,
        priority: int = 0,
    ) -> str:
        """
        提交推理任务到队列。

        Args:
            sample_ids:  样本 ID 列表
            embeddings:  嵌入矩阵 (N, D)
            priority:    优先级（越大越优先）

        Returns:
            task_id

        Raises:
            RuntimeError: 队列已满
        """
        task_id = str(uuid.uuid4())[:8]
        task = InferenceTask(
            task_id=task_id,
            sample_ids=sample_ids,
            embeddings=np.asarray(embeddings, dtype=np.float32),
            created_at=time.time(),
            priority=priority,
        )

        # 优先级队列：(-priority, timestamp) 实现高优先级 + FIFO
        await self._queue.put((-priority, task.created_at, task))
        self._stats["submitted"] += 1

        logger.debug("任务已提交 | task_id=%s | samples=%d", task_id, len(sample_ids))
        return task_id

    def submit_sync(
        self,
        sample_ids: List[str],
        embeddings: np.ndarray,
        priority: int = 0,
    ) -> str:
        """同步版本的 submit（用于非 async 上下文）。"""
        task_id = str(uuid.uuid4())[:8]
        task = InferenceTask(
            task_id=task_id,
            sample_ids=sample_ids,
            embeddings=np.asarray(embeddings, dtype=np.float32),
            created_at=time.time(),
            priority=priority,
        )
        # 同步模式下直接处理
        result = self._process_single(task)
        self._results[task_id] = result
        self._stats["submitted"] += 1
        if result.status == TaskStatus.DONE:
            self._stats["completed"] += 1
        elif result.status == TaskStatus.FAILED:
            self._stats["failed"] += 1
        return task_id

    # ── 结果获取 ─────────────────────────────────────────────

    def get_result(self, task_id: str) -> Optional[InferenceResult]:
        """获取推理结果（非阻塞）。"""
        return self._results.get(task_id)

    async def wait_result(self, task_id: str, timeout: float = 30.0) -> InferenceResult:
        """等待推理结果。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            result = self._results.get(task_id)
            if result is not None:
                return result
            await asyncio.sleep(self.poll_interval)
        raise asyncio.TimeoutError(f"Task {task_id} timed out after {timeout}s")

    # ── 后台 Worker ──────────────────────────────────────────

    async def start(self) -> None:
        """启动后台推理 worker。"""
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("BatchEngine worker 已启动")

    async def stop(self) -> None:
        """停止后台 worker。"""
        self._running = False
        if self._worker_task is not None:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
        logger.info("BatchEngine worker 已停止")

    async def _worker_loop(self) -> None:
        """后台 worker 主循环。"""
        while self._running:
            try:
                await self._process_batch_from_queue()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Worker 异常: %s", exc)
                await asyncio.sleep(1.0)

    async def _process_batch_from_queue(self) -> None:
        """从队列收集一批任务并处理。"""
        # ── 显存检查 ────────────────────────────────────────
        # 【显存生命周期】推理前检查显存状态，拒绝在 PRESSURE/EMERGENCY 时提交
        snapshot = self.memory_manager.poll()
        if snapshot.state in (MemoryState.PRESSURE, MemoryState.EMERGENCY):
            logger.warning(
                "显存压力 (%s)，暂停 worker %.1fs",
                snapshot.state.value, self.poll_interval * 5,
            )
            await asyncio.sleep(self.poll_interval * 5)
            return

        # 收集任务
        tasks: List[InferenceTask] = []
        for _ in range(self.batch_size):
            if self._queue.empty():
                break
            try:
                _, _, task = self._queue.get_nowait()
                tasks.append(task)
            except asyncio.QueueEmpty:
                break

        if not tasks:
            await asyncio.sleep(self.poll_interval)
            return

        # 拼接 batch 并推理
        self._execute_batch(tasks)

    def _execute_batch(self, tasks: List[InferenceTask]) -> None:
        """
        执行一个 batch 的推理。

        【显存生命周期】
        1. 推理前：GPU 显存临时增长（激活值缓存）
        2. 推理后：显式 empty_cache() + gc.collect() 释放
        """
        # 拼接嵌入矩阵
        all_embeddings = np.vstack([t.embeddings for t in tasks])

        t0 = time.time()
        try:
            # 推理
            # 【显存生命周期】推理过程中 GPU 显存峰值在此处
            output_features = self.inference_fn(all_embeddings)

            processing_ms = (time.time() - t0) * 1000

            # 【显存生命周期】推理完成后立即释放 GPU 缓存
            self._post_inference_cleanup()

            # 分发结果
            offset = 0
            for task in tasks:
                n = len(task.sample_ids)
                result = InferenceResult(
                    task_id=task.task_id,
                    sample_ids=task.sample_ids,
                    features=output_features[offset:offset + n],
                    status=TaskStatus.DONE,
                    processing_time_ms=processing_ms / len(tasks),
                )
                self._results[task.task_id] = result
                offset += n

            self._stats["completed"] += len(tasks)
            self._stats["total_processing_ms"] += processing_ms

        except Exception as exc:
            logger.error("Batch 推理失败: %s", exc)
            self._post_inference_cleanup()

            for task in tasks:
                result = InferenceResult(
                    task_id=task.task_id,
                    sample_ids=task.sample_ids,
                    features=np.array([]),
                    status=TaskStatus.FAILED,
                    processing_time_ms=0.0,
                    error=str(exc),
                )
                self._results[task.task_id] = result
                self._stats["failed"] += 1

    def _process_single(self, task: InferenceTask) -> InferenceResult:
        """同步处理单个任务（用于 submit_sync）。"""
        snapshot = self.memory_manager.poll()
        if snapshot.state in (MemoryState.PRESSURE, MemoryState.EMERGENCY):
            return InferenceResult(
                task_id=task.task_id,
                sample_ids=task.sample_ids,
                features=np.array([]),
                status=TaskStatus.DROPPED,
                processing_time_ms=0.0,
                error=f"显存不足 ({snapshot.state.value})",
            )

        t0 = time.time()
        try:
            output = self.inference_fn(task.embeddings)
            self._post_inference_cleanup()
            return InferenceResult(
                task_id=task.task_id,
                sample_ids=task.sample_ids,
                features=output,
                status=TaskStatus.DONE,
                processing_time_ms=(time.time() - t0) * 1000,
            )
        except Exception as exc:
            self._post_inference_cleanup()
            return InferenceResult(
                task_id=task.task_id,
                sample_ids=task.sample_ids,
                features=np.array([]),
                status=TaskStatus.FAILED,
                processing_time_ms=(time.time() - t0) * 1000,
                error=str(exc),
            )

    def _post_inference_cleanup(self) -> None:
        """
        推理后清理：empty_cache + 强制 GC。

        【显存生命周期】这是显存释放的关键步骤。
        每次 batch 推理后必须调用，确保不累积显存碎片。
        """
        try:
            import torch  # type: ignore[import-untyped]
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

        gc.collect()

    # ── 状态查询 ─────────────────────────────────────────────

    @property
    def stats(self) -> Dict[str, Any]:
        return dict(self._stats)

    @property
    def queue_depth(self) -> int:
        return self._queue.qsize()

    def get_summary(self) -> Dict[str, Any]:
        return {
            **self._stats,
            "queue_depth": self.queue_depth,
            "running": self._running,
            "memory_state": self.memory_manager.state.value,
            "memory_utilization_pct": round(
                self.memory_manager.get_utilization() * 100, 1
            ),
        }
