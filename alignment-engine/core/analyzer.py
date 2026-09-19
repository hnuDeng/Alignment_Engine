"""
推理模块 (Analyzer) —— 负责分布漂移检测与异常样本识别。

本模块实现了两条路径：
1. **CUDA 路径**：尝试加载 PyTorch 视觉模型，针对 8GB 显存做优化
   （半精度推理、及时清缓存），在 GPU 上计算嵌入距离。
2. **NumPy 降级路径**：若无 CUDA 或 PyTorch，使用纯 NumPy 计算欧氏距离
   与均值偏移，基于统计阈值挑出异常样本。

两种路径均返回符合 `DriftReport` 数据契约的不可变对象。
"""

from __future__ import annotations

import logging
from typing import List, Tuple

import numpy as np

from schemas import DataSliceContext, DriftReport, DriftSample

logger = logging.getLogger(__name__)

# 分布漂移检测的默认参数
_DEFAULT_SIGMA_MULTIPLIER: float = 2.0  # 阈值 = 均值 + sigma * 标准差
_MIN_DRIFT_SAMPLES: int = 2  # 最少检测出的异常样本数
_MAX_DRIFT_SAMPLES: int = 3  # 最多检测出的异常样本数


class Analyzer:
    """
    推理模块：基于嵌入空间的分布漂移检测。

    工作流程：
    1. 尝试导入 PyTorch 并检测 CUDA 可用性。
    2. 若 CUDA 可用，进行 GPU 加速的距离计算（含 8GB 显存优化）。
    3. 否则回退到 NumPy 实现。

    Attributes:
        sigma_multiplier: 标准差倍数，用于计算漂移阈值。
        min_drift: 最少报告的异常样本数。
        max_drift: 最多报告的异常样本数。
    """

    def __init__(
        self,
        sigma_multiplier: float = _DEFAULT_SIGMA_MULTIPLIER,
        min_drift: int = _MIN_DRIFT_SAMPLES,
        max_drift: int = _MAX_DRIFT_SAMPLES,
    ) -> None:
        self.sigma_multiplier = sigma_multiplier
        self.min_drift = min_drift
        self.max_drift = max_drift
        self._mode: str = "unknown"
        logger.info(
            "Analyzer 初始化完成 | sigma=%.2f | drift_range=[%d, %d]",
            sigma_multiplier,
            min_drift,
            max_drift,
        )

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------
    def analyze(self, context: DataSliceContext) -> DriftReport:
        """
        对输入数据切片执行分布漂移检测。

        优先尝试 CUDA 路径，失败后自动降级到 NumPy 路径。

        Args:
            context: Extractor 输出的数据切片上下文。

        Returns:
            DriftReport: 包含异常样本列表与统计信息的漂移报告。
        """
        try:
            return self._analyze_cuda(context)
        except Exception as exc:
            logger.warning(
                "CUDA 路径失败 (%s: %s)，降级到 NumPy 模式",
                type(exc).__name__,
                exc,
            )
            return self._analyze_numpy(context)

    @property
    def mode(self) -> str:
        """当前运行模式：'cuda' 或 'mock_numpy'。"""
        return self._mode

    # ------------------------------------------------------------------
    # 通用辅助方法
    # ------------------------------------------------------------------
    @staticmethod
    def _build_embedding_matrix(
        context: DataSliceContext,
    ) -> Tuple[np.ndarray, List[str]]:
        """
        从 DataSliceContext 提取嵌入矩阵与对应的样本 ID 列表。

        Returns:
            (embedding_matrix, sample_ids)
            embedding_matrix 的 shape 为 (N, 128)。
        """
        sample_ids = [r.image_id for r in context.sample_records]
        embeddings = np.array(
            [r.embedding for r in context.sample_records], dtype=np.float64
        )
        return embeddings, sample_ids

    def _compute_distances(
        self, embeddings: np.ndarray
    ) -> Tuple[np.ndarray, float, float, np.ndarray]:
        """
        计算每个样本到质心的欧氏距离，以及漂移阈值。

        Returns:
            (distances, mean_dist, threshold, centroid)
        """
        centroid = embeddings.mean(axis=0)
        diff = embeddings - centroid
        distances = np.sqrt(np.sum(diff * diff, axis=1))
        mean_dist = float(distances.mean())
        std_dist = float(distances.std())
        threshold = mean_dist + self.sigma_multiplier * std_dist
        return distances, mean_dist, threshold, centroid

    def _select_drift_samples(
        self,
        distances: np.ndarray,
        sample_ids: List[str],
        labels: List[str],
        mean_dist: float,
        threshold: float,
    ) -> List[DriftSample]:
        """
        根据距离阈值选取异常样本。

        选取策略：
        - 优先选取超过阈值的样本。
        - 若不足 min_drift 个，则补充距离最大的样本直到达到 min_drift。
        - 最多选取 max_drift 个。

        Returns:
            DriftSample 列表。
        """
        sorted_indices = np.argsort(-distances)
        selected: List[DriftSample] = []

        for idx in sorted_indices:
            if len(selected) >= self.max_drift:
                break
            
            is_above_threshold = distances[idx] > threshold
            if is_above_threshold or len(selected) < self.min_drift:
                reason_text = "超过阈值" if is_above_threshold else f"为最高之一（均值 {mean_dist:.4f}）"
                selected.append(
                    DriftSample(
                        image_id=sample_ids[idx],
                        drift_score=round(float(distances[idx]), 6),
                        reason=(
                            f"样本到质心的欧氏距离 ({distances[idx]:.4f}) "
                            f"{reason_text}，"
                            f"标签为 '{labels[idx]}'"
                        ),
                    )
                )
            else:
                # Since array is sorted, if this one isn't above threshold and we reached min_drift, the rest won't be either
                break

        return selected

    # ------------------------------------------------------------------
    # CUDA 路径
    # ------------------------------------------------------------------
    def _analyze_cuda(self, context: DataSliceContext) -> DriftReport:
        """
        使用 PyTorch CUDA 进行 GPU 加速的分布漂移检测。

        针对 8GB 显存的优化措施：
        - 使用半精度 (float16) 推理以减半显存占用。
        - 每次计算后调用 torch.cuda.empty_cache() 及时释放缓存。
        - 使用 torch.no_grad() 禁用梯度追踪。

        Raises:
            ImportError: PyTorch 未安装。
            RuntimeError: CUDA 不可用或显存不足。

        Returns:
            DriftReport: GPU 计算的漂移报告。
        """
        import torch  # type: ignore[import-untyped]

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA 不可用，无法执行 GPU 加速分析")

        device = torch.device("cuda:0")

        # 显存优化：检查可用显存，不足时主动报错
        total_mem = torch.cuda.get_device_properties(device).total_mem
        free_mem = total_mem - torch.cuda.memory_allocated(device)
        required_mem = (
            context.total_count * 128 * 2  # 半精度 float16
        )
        if free_mem < required_mem:
            raise RuntimeError(
                f"显存不足：需要 {required_mem / 1e6:.1f} MB，"
                f"可用 {free_mem / 1e6:.1f} MB"
            )

        embeddings_np, sample_ids = self._build_embedding_matrix(context)
        labels = [r.label for r in context.sample_records]

        with torch.no_grad():
            # 半精度推理以节省显存
            embeddings_t = torch.tensor(
                embeddings_np, dtype=torch.float16, device=device
            )
            centroid_t = embeddings_t.mean(dim=0)
            diff_t = embeddings_t - centroid_t
            distances_t = torch.sqrt(torch.sum(diff_t * diff_t, dim=1))
            distances_np = distances_t.cpu().numpy().astype(np.float64)

        # 及时释放 GPU 显存
        del embeddings_t, centroid_t, diff_t, distances_t
        torch.cuda.empty_cache()

        mean_dist = float(distances_np.mean())
        std_dist = float(distances_np.std())
        threshold = mean_dist + self.sigma_multiplier * std_dist

        drift_samples = self._select_drift_samples(
            distances_np, sample_ids, labels, mean_dist, threshold
        )
        drift_ids = [s.image_id for s in drift_samples]

        self._mode = "cuda"
        report = DriftReport(
            drift_samples=drift_samples,
            drift_sample_ids=drift_ids,
            mean_distance=round(mean_dist, 6),
            threshold=round(threshold, 6),
            analysis_mode="cuda",
        )
        logger.info(
            "CUDA 分析完成 | 漂移样本数=%d | 均值距离=%.4f | 阈值=%.4f",
            len(drift_samples),
            mean_dist,
            threshold,
        )
        return report

    # ------------------------------------------------------------------
    # NumPy 降级路径
    # ------------------------------------------------------------------
    def _analyze_numpy(self, context: DataSliceContext) -> DriftReport:
        """
        使用纯 NumPy 进行分布漂移检测（CPU 模式）。

        算法：
        1. 计算所有嵌入向量的质心（均值向量）。
        2. 计算每个样本到质心的欧氏距离。
        3. 阈值 = 均值距离 + sigma * 标准差。
        4. 选取超过阈值的样本（最少 min_drift 个，最多 max_drift 个）。

        Returns:
            DriftReport: CPU 计算的漂移报告。
        """
        embeddings, sample_ids = self._build_embedding_matrix(context)
        labels = [r.label for r in context.sample_records]

        distances, mean_dist, threshold, _centroid = self._compute_distances(
            embeddings
        )

        drift_samples = self._select_drift_samples(
            distances, sample_ids, labels, mean_dist, threshold
        )
        drift_ids = [s.image_id for s in drift_samples]

        self._mode = "mock_numpy"
        report = DriftReport(
            drift_samples=drift_samples,
            drift_sample_ids=drift_ids,
            mean_distance=round(mean_dist, 6),
            threshold=round(threshold, 6),
            analysis_mode="mock_numpy",
        )
        logger.info(
            "NumPy 分析完成 | 漂移样本数=%d | 均值距离=%.4f | 阈值=%.4f",
            len(drift_samples),
            mean_dist,
            threshold,
        )
        return report
