"""
测试 backend_cpp Python 桥接层（新 GraphSearch 接口 + MockCppBackend BFS/DP）。
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

# 添加 backend_cpp 到搜索路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend_cpp"))

from python_bridge import CppBackendFacade, CppDriftResult, MockCppBackend


class TestMockCppBackendBFS:
    """测试 MockCppBackend BFS 孤立度检测。"""

    def setup_method(self) -> None:
        self.backend = MockCppBackend(
            embedding_dim=8, sigma=2.0, max_outliers=3,
            k_nearest=3, max_bfs_hops=5, adjacency_threshold=10.0,
        )

    def test_returns_cpp_drift_result(self) -> None:
        ids = [0, 1, 2, 3, 4]
        labels = [0, 0, 0, 1, 1]
        emb = np.array([
            [0]*8, [1]*8, [2]*8, [50]*8, [60]*8,
        ], dtype=np.float64)
        result = self.backend.detect(ids, labels, emb)
        assert isinstance(result, CppDriftResult)

    def test_detects_outliers(self) -> None:
        ids = list(range(10))
        labels = [0] * 8 + [1] * 2
        rng = np.random.default_rng(42)
        emb = np.vstack([
            rng.normal(0, 1, (8, 32)),
            rng.normal(50, 1, (2, 32)),
        ])
        backend = MockCppBackend(
            embedding_dim=32, sigma=2.0, max_outliers=2,
            k_nearest=3, max_bfs_hops=10, adjacency_threshold=15.0,
        )
        result = backend.detect(ids, labels, emb)
        assert len(result.outlier_ids) >= 1
        for oid in result.outlier_ids:
            assert oid >= 8

    def test_max_outliers_limit(self) -> None:
        backend = MockCppBackend(
            embedding_dim=4, max_outliers=2, k_nearest=2, adjacency_threshold=5.0,
        )
        emb = np.array([[0]*4, [1]*4, [2]*4, [100]*4, [200]*4, [300]*4], dtype=np.float64)
        result = backend.detect(list(range(6)), [0]*6, emb)
        assert len(result.outlier_ids) <= 2

    def test_empty_input(self) -> None:
        result = self.backend.detect([], [], np.array([]).reshape(0, 8))
        assert result.outlier_ids == []

    def test_single_sample(self) -> None:
        result = self.backend.detect([42], [0], np.array([[1, 2, 3, 4, 5, 6, 7, 8]], dtype=np.float64))
        assert len(result.outlier_ids) == 1


class TestCppBackendFacadeAutoDetect:
    """测试自动降级。"""

    def test_falls_back_to_mock(self) -> None:
        facade = CppBackendFacade(embedding_dim=8, max_outliers=2)
        assert facade.mode == "mock_python"

    def test_detect_works_after_fallback(self) -> None:
        facade = CppBackendFacade(embedding_dim=4, max_outliers=2, k_nearest=2, adjacency_threshold=10.0)
        emb = np.array([[0]*4, [1]*4, [100]*4], dtype=np.float64)
        result = facade.detect([0, 1, 2], [0, 0, 1], emb)
        assert isinstance(result, CppDriftResult)
        assert len(result.outlier_ids) >= 1

    def test_deterministic(self) -> None:
        facade = CppBackendFacade(embedding_dim=4, max_outliers=2, k_nearest=2, adjacency_threshold=5.0)
        emb = np.array([[0]*4, [1]*4, [50]*4], dtype=np.float64)
        r1 = facade.detect([0, 1, 2], [0, 0, 1], emb)
        r2 = facade.detect([0, 1, 2], [0, 0, 1], emb)
        assert r1.outlier_ids == r2.outlier_ids
