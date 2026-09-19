"""
单元测试 —— 推理模块 (core/analyzer.py)

覆盖范围：
- NumPy 降级路径的正确性
- 漂移样本的检测逻辑
- 阈值计算的合理性
- DriftReport 结构的完整性
- 不同 sigma 参数的影响
"""

from __future__ import annotations

import uuid
from typing import List

import numpy as np
import pytest

from schemas import DataSliceContext, DriftReport, SampleRecord
from core.analyzer import Analyzer


# ---------------------------------------------------------------------------
# 辅助工厂
# ---------------------------------------------------------------------------
def _make_context_with_outliers(
    n_normal: int = 8,
    n_outliers: int = 2,
    embedding_dim: int = 128,
) -> DataSliceContext:
    """
    创建包含明确异常样本的 DataSliceContext。

    正常样本围绕原点分布，异常样本远离原点。
    """
    rng = np.random.default_rng(seed=123)
    records: List[SampleRecord] = []

    # 正常样本：均值 0，标准差 1
    for _ in range(n_normal):
        records.append(
            SampleRecord(
                image_id=str(uuid.uuid4()),
                label="normal",
                embedding=list(rng.normal(0, 1, embedding_dim)),
            )
        )

    # 异常样本：均值 10，标准差 1（远离正常分布）
    for _ in range(n_outliers):
        records.append(
            SampleRecord(
                image_id=str(uuid.uuid4()),
                label="outlier",
                embedding=list(rng.normal(10, 1, embedding_dim)),
            )
        )

    return DataSliceContext(
        source="test",
        sample_records=records,
        extraction_timestamp="2025-01-01T00:00:00+00:00",
        total_count=len(records),
    )


def _make_uniform_context(
    n: int = 10, embedding_dim: int = 128
) -> DataSliceContext:
    """创建所有样本完全一致的 DataSliceContext（无异常）。"""
    embedding = [0.0] * embedding_dim
    records = [
        SampleRecord(
            image_id=str(uuid.uuid4()),
            label="uniform",
            embedding=list(embedding),
        )
        for _ in range(n)
    ]
    return DataSliceContext(
        source="test_uniform",
        sample_records=records,
        extraction_timestamp="2025-01-01T00:00:00+00:00",
        total_count=n,
    )


# ---------------------------------------------------------------------------
# Analyzer 测试
# ---------------------------------------------------------------------------
class TestAnalyzerNumPy:
    """测试 Analyzer 的 NumPy 降级路径。"""

    def setup_method(self) -> None:
        """每个测试前创建 Analyzer 实例。"""
        self.analyzer = Analyzer(sigma_multiplier=2.0)

    def test_returns_drift_report(self) -> None:
        """分析应返回 DriftReport 实例。"""
        ctx = _make_context_with_outliers()
        report = self.analyzer.analyze(ctx)
        assert isinstance(report, DriftReport)

    def test_analysis_mode_is_numpy(self) -> None:
        """NumPy 路径的 analysis_mode 应为 'mock_numpy'。"""
        ctx = _make_context_with_outliers()
        report = self.analyzer.analyze(ctx)
        assert report.analysis_mode == "mock_numpy"

    def test_mode_property(self) -> None:
        """分析后 mode 属性应为 'mock_numpy'。"""
        ctx = _make_context_with_outliers()
        self.analyzer.analyze(ctx)
        assert self.analyzer.mode == "mock_numpy"

    def test_detects_outliers(self) -> None:
        """应检测出异常样本。"""
        ctx = _make_context_with_outliers(n_normal=8, n_outliers=2)
        report = self.analyzer.analyze(ctx)
        assert len(report.drift_samples) >= 1

    def test_outlier_ids_consistency(self) -> None:
        """drift_sample_ids 应与 drift_samples 中的 ID 一致。"""
        ctx = _make_context_with_outliers()
        report = self.analyzer.analyze(ctx)
        ids_from_samples = [s.image_id for s in report.drift_samples]
        assert report.drift_sample_ids == ids_from_samples

    def test_drift_score_positive(self) -> None:
        """所有漂移分数应为正数。"""
        ctx = _make_context_with_outliers()
        report = self.analyzer.analyze(ctx)
        for sample in report.drift_samples:
            assert sample.drift_score > 0

    def test_threshold_greater_than_mean(self) -> None:
        """阈值应大于均值距离。"""
        ctx = _make_context_with_outliers()
        report = self.analyzer.analyze(ctx)
        assert report.threshold > report.mean_distance

    def test_mean_distance_non_negative(self) -> None:
        """均值距离应为非负数。"""
        ctx = _make_context_with_outliers()
        report = self.analyzer.analyze(ctx)
        assert report.mean_distance >= 0

    def test_reason_populated(self) -> None:
        """每个漂移样本应有非空的 reason。"""
        ctx = _make_context_with_outliers()
        report = self.analyzer.analyze(ctx)
        for sample in report.drift_samples:
            assert len(sample.reason) > 0
            assert "欧氏距离" in sample.reason or "最高" in sample.reason

    def test_max_drift_limit(self) -> None:
        """漂移样本数不应超过 max_drift。"""
        ctx = _make_context_with_outliers(n_normal=5, n_outliers=5)
        analyzer = Analyzer(max_drift=2)
        report = analyzer.analyze(ctx)
        assert len(report.drift_samples) <= 2

    def test_min_drift_guarantee(self) -> None:
        """漂移样本数至少为 min_drift（当总样本 >= min_drift）。"""
        ctx = _make_context_with_outliers(n_normal=8, n_outliers=2)
        analyzer = Analyzer(min_drift=2, sigma_multiplier=100.0)
        report = analyzer.analyze(ctx)
        # 即使阈值极高，至少应报告 2 个
        assert len(report.drift_samples) >= 2

    def test_uniform_data_no_drift(self) -> None:
        """完全一致的数据应报告极低的均值距离。"""
        ctx = _make_uniform_context()
        report = self.analyzer.analyze(ctx)
        assert report.mean_distance == 0.0
        assert report.threshold == 0.0

    def test_sigma_multiplier_affects_threshold(self) -> None:
        """较大的 sigma 应导致较大的阈值。"""
        ctx = _make_context_with_outliers()
        a1 = Analyzer(sigma_multiplier=1.0)
        a2 = Analyzer(sigma_multiplier=5.0)
        r1 = a1.analyze(ctx)
        r2 = a2.analyze(ctx)
        assert r2.threshold > r1.threshold

    def test_immutable_report(self) -> None:
        """DriftReport 应为不可变对象。"""
        ctx = _make_context_with_outliers()
        report = self.analyzer.analyze(ctx)
        with pytest.raises(Exception):
            report.threshold = 999.0  # type: ignore[misc]


class TestAnalyzerHelperMethods:
    """测试 Analyzer 内部辅助方法。"""

    def test_build_embedding_matrix(self) -> None:
        """嵌入矩阵的形状应正确。"""
        ctx = _make_context_with_outliers(n_normal=5, n_outliers=3)
        matrix, ids = Analyzer._build_embedding_matrix(ctx)
        assert matrix.shape == (8, 128)
        assert len(ids) == 8

    def test_compute_distances(self) -> None:
        """距离计算应返回正确形状的数组。"""
        rng = np.random.default_rng(42)
        embeddings = rng.normal(0, 1, (10, 128))
        distances, mean_dist, threshold, centroid = Analyzer()._compute_distances(
            embeddings
        )
        assert distances.shape == (10,)
        assert mean_dist >= 0
        assert threshold >= mean_dist
        assert centroid.shape == (128,)
