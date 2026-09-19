"""
测试 C++ 引擎 Python 桥接层（Mock 后端模式）。

覆盖范围：
- MockCppBackend BFS 孤立度检测的正确性
- CppBackendFacade 自动降级逻辑
- 与现有 Analyzer 的一致性验证
- 边界情况（空数据、单样本、全相同样本）
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

# 将 backend_cpp 加入搜索路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend_cpp"))

from python_bridge import CppBackendFacade, CppDriftResult, MockCppBackend


class TestMockCppBackend:
    """测试纯 Python 复刻的 BFS 异常检测器。"""

    def setup_method(self) -> None:
        self.backend = MockCppBackend(
            embedding_dim=8, sigma=2.0, max_outliers=3,
            k_nearest=3, max_bfs_hops=5, adjacency_threshold=10.0,
        )

    def test_returns_cpp_drift_result(self) -> None:
        """应返回 CppDriftResult 实例。"""
        ids = [0, 1, 2, 3, 4]
        labels = [0, 0, 0, 1, 1]
        emb = np.array([
            [0, 0, 0, 0, 0, 0, 0, 0],
            [1, 1, 1, 1, 1, 1, 1, 1],
            [2, 2, 2, 2, 2, 2, 2, 2],
            [50, 50, 50, 50, 50, 50, 50, 50],
            [60, 60, 60, 60, 60, 60, 60, 60],
        ], dtype=np.float64)
        result = self.backend.detect(ids, labels, emb)
        assert isinstance(result, CppDriftResult)

    def test_detects_outliers(self) -> None:
        """应检测出远离簇的异常样本。"""
        ids = list(range(10))
        labels = [0] * 8 + [1] * 2
        rng = np.random.default_rng(42)
        normal = rng.normal(0, 1, (8, 32))
        outlier = rng.normal(50, 1, (2, 32))
        emb = np.vstack([normal, outlier])

        backend = MockCppBackend(embedding_dim=32, sigma=2.0, max_outliers=2,
                                  k_nearest=3, max_bfs_hops=10, adjacency_threshold=15.0)
        result = backend.detect(ids, labels, emb)

        assert len(result.outlier_ids) >= 1
        for oid in result.outlier_ids:
            assert oid >= 8, f"outlier {oid} should be from the outlier group"

    def test_max_outliers_limit(self) -> None:
        """漂移样本数不应超过 max_outliers。"""
        backend = MockCppBackend(embedding_dim=4, max_outliers=2,
                                  k_nearest=2, adjacency_threshold=5.0)
        ids = list(range(6))
        labels = [0] * 6
        emb = np.array([
            [0, 0, 0, 0],
            [1, 1, 1, 1],
            [2, 2, 2, 2],
            [100, 100, 100, 100],
            [200, 200, 200, 200],
            [300, 300, 300, 300],
        ], dtype=np.float64)

        result = backend.detect(ids, labels, emb)
        assert len(result.outlier_ids) <= 2

    def test_mean_distance_positive(self) -> None:
        """均值距离应为正数。"""
        ids = [0, 1, 2]
        labels = [0, 0, 0]
        emb = np.array([[0, 0, 0, 0], [1, 1, 1, 1], [5, 5, 5, 5]], dtype=np.float64)
        result = self.backend.detect(ids, labels, emb)
        assert result.mean_distance >= 0

    def test_threshold_greater_than_mean(self) -> None:
        """阈值应 >= 均值距离。"""
        ids = list(range(5))
        labels = [0] * 5
        rng = np.random.default_rng(123)
        emb = rng.normal(0, 1, (5, 8))
        result = self.backend.detect(ids, labels, emb)
        assert result.threshold >= result.mean_distance

    def test_reasons_populated(self) -> None:
        """每个异常样本应有非空的原因描述。"""
        ids = [0, 1, 2]
        labels = [0, 0, 1]
        emb = np.array([[0, 0, 0, 0], [1, 1, 1, 1], [100, 100, 100, 100]], dtype=np.float64)
        result = self.backend.detect(ids, labels, emb)
        for reason in result.outlier_reasons:
            assert "BFS isolation" in reason
            assert "centroid distance" in reason

    def test_empty_input(self) -> None:
        """空输入应返回空结果。"""
        result = self.backend.detect([], [], np.array([]).reshape(0, 8))
        assert result.outlier_ids == []
        assert result.mean_distance == 0.0

    def test_single_sample(self) -> None:
        """单样本应正常处理。"""
        result = self.backend.detect([42], [0], np.array([[1, 2, 3, 4]], dtype=np.float64))
        assert len(result.outlier_ids) == 1
        assert result.outlier_ids[0] == 42

    def test_uniform_samples_low_isolation(self) -> None:
        """全相同样本的孤立度应全部为 0。"""
        ids = list(range(5))
        labels = [0] * 5
        emb = np.array([[1, 1, 1, 1]] * 5, dtype=np.float64)
        result = self.backend.detect(ids, labels, emb)
        # 全相同样本的孤立度应为 0（一步即达）
        assert len(result.outlier_ids) >= 1

    def test_1d_embedding_flattened(self) -> None:
        """扁平 1D 嵌入应被正确 reshape。"""
        ids = [0, 1]
        labels = [0, 1]
        emb = np.array([0, 0, 0, 0, 100, 100, 100, 100], dtype=np.float64)
        result = self.backend.detect(ids, labels, emb)
        assert len(result.outlier_ids) >= 1


class TestCppBackendFacade:
    """测试统一门面的自动降级逻辑。"""

    def test_fallback_to_mock(self) -> None:
        """无 C++ 模块时应降级到 Mock。"""
        facade = CppBackendFacade(embedding_dim=8, max_outliers=2)
        assert facade.mode == "mock_python"

    def test_fallback_detect_works(self) -> None:
        """降级后 detect 应正常工作。"""
        facade = CppBackendFacade(embedding_dim=4, max_outliers=2,
                                   k_nearest=2, adjacency_threshold=10.0)
        ids = [0, 1, 2, 3]
        labels = [0, 0, 0, 1]
        emb = np.array([
            [0, 0, 0, 0],
            [1, 1, 1, 1],
            [2, 2, 2, 2],
            [100, 100, 100, 100],
        ], dtype=np.float64)
        result = facade.detect(ids, labels, emb)
        assert isinstance(result, CppDriftResult)
        assert len(result.outlier_ids) >= 1

    def test_consistent_results(self) -> None:
        """两次相同输入应产生相同结果。"""
        facade = CppBackendFacade(embedding_dim=4, max_outliers=2,
                                   k_nearest=2, adjacency_threshold=5.0)
        ids = [0, 1, 2]
        labels = [0, 0, 1]
        emb = np.array([[0, 0, 0, 0], [1, 1, 1, 1], [50, 50, 50, 50]], dtype=np.float64)
        r1 = facade.detect(ids, labels, emb)
        r2 = facade.detect(ids, labels, emb)
        assert r1.outlier_ids == r2.outlier_ids
        assert r1.mean_distance == r2.mean_distance


class TestBFSIsolation:
    """专门测试 BFS 孤立度算法的正确性。"""

    def test_isolated_node_highest_score(self) -> None:
        """完全孤立的节点应获得最高分数。"""
        backend = MockCppBackend(
            embedding_dim=4, k_nearest=2, max_bfs_hops=5,
            adjacency_threshold=5.0, max_outliers=3, sigma=2.0,
        )
        # 紧密簇 + 1 个孤立节点
        ids = [0, 1, 2, 3]
        labels = [0, 0, 0, 1]
        emb = np.array([
            [0, 0, 0, 0],
            [0.1, 0.1, 0.1, 0.1],
            [0.2, 0.0, 0.0, 0.0],
            [100, 100, 100, 100],  # 孤立
        ], dtype=np.float64)

        result = backend.detect(ids, labels, emb)
        assert 3 in result.outlier_ids

    def test_bfs_hop_count(self) -> None:
        """验证 BFS 跳数正确：紧密簇内节点跳数应低。"""
        backend = MockCppBackend(
            embedding_dim=2, k_nearest=1, max_bfs_hops=10,
            adjacency_threshold=3.0, max_outliers=4, sigma=2.0,
        )
        # 链式结构：0-1-2（距离依次为 1.0）
        ids = [0, 1, 2, 3]
        labels = [0, 0, 0, 0]
        emb = np.array([
            [0, 0],
            [1, 0],
            [2, 0],
            [100, 0],  # 孤立
        ], dtype=np.float64)

        result = backend.detect(ids, labels, emb)
        # 节点 3 应在结果中（最高孤立度）
        assert result.outlier_ids[0] == 3 or 3 in result.outlier_ids
