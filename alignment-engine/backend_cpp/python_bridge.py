"""
C++ 特征图引擎的 Python 桥接层。

提供两层接口：
1. NativeCppBackend：直接调用 pybind11 绑定的 C++ 引擎（需要编译）
2. MockCppBackend：纯 Python 复刻的等价功能（无编译依赖）

对外统一暴露 CppBackendFacade，自动选择可用后端。
"""

from __future__ import annotations

import logging
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# 数据结构
# ══════════════════════════════════════════════════════════════

@dataclass
class CppDriftResult:
    """C++ 引擎的漂移检测结果（Python 端镜像 fg::DriftResult）。"""

    outlier_ids: List[int] = field(default_factory=list)
    outlier_scores: List[float] = field(default_factory=list)
    outlier_reasons: List[str] = field(default_factory=list)
    mean_distance: float = 0.0
    threshold: float = 0.0


# ══════════════════════════════════════════════════════════════
# Mock C++ 后端（纯 Python 复刻 BFS 异常检测）
# ══════════════════════════════════════════════════════════════

class MockCppBackend:
    """
    纯 Python 实现的 BFS 异常检测器。

    算法与 C++ FeatureGraph::bfs_isolation_score 完全等价：
    1. 计算质心（均值向量）
    2. 计算每个节点到质心的欧氏距离
    3. 按距离阈值构建邻接图
    4. 从距质心最近的 K 个种子节点发起层序 BFS
    5. 跳数越大 → 孤立度越高
    """

    def __init__(
        self,
        embedding_dim: int = 128,
        sigma: float = 2.0,
        max_outliers: int = 3,
        k_nearest: int = 5,
        max_bfs_hops: int = 10,
        adjacency_threshold: float = 15.0,
    ) -> None:
        self.embedding_dim = embedding_dim
        self.sigma = sigma
        self.max_outliers = max_outliers
        self.k_nearest = k_nearest
        self.max_bfs_hops = max_bfs_hops
        self.adjacency_threshold = adjacency_threshold

    def detect(
        self,
        ids: List[int],
        labels: List[int],
        embeddings: np.ndarray,
    ) -> CppDriftResult:
        """
        执行 BFS 漂移检测。

        Args:
            ids:         样本 ID 列表（长度 N）
            labels:      标签 ID 列表（长度 N）
            embeddings:  嵌入矩阵 (N x D)

        Returns:
            CppDriftResult
        """
        n = len(ids)
        if n == 0:
            return CppDriftResult()

        embeddings = np.asarray(embeddings, dtype=np.float64)
        if embeddings.ndim == 1:
            embeddings = embeddings.reshape(n, -1)

        d = embeddings.shape[1]

        # Step 1: 质心
        centroid = embeddings.mean(axis=0)

        # Step 2: 质心距离
        diff = embeddings - centroid
        dist_sq = np.sum(diff * diff, axis=1)
        distances = np.sqrt(dist_sq)

        # Step 3: 统计阈值
        mean_dist = float(distances.mean())
        std_dist = float(distances.std())
        threshold = mean_dist + self.sigma * std_dist

        # Step 4: 邻接图（阈值化）
        threshold_sq = self.adjacency_threshold ** 2
        neighbors: List[List[int]] = [[] for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                d_sq = float(np.sum((embeddings[i] - embeddings[j]) ** 2))
                if d_sq < threshold_sq:
                    neighbors[i].append(j)

        # Step 5: BFS 孤立度评分
        isolation_scores = self._bfs_isolation(
            n, neighbors, distances, self.k_nearest, self.max_bfs_hops
        )

        # Step 6: 选取 Top-K 异常
        ranked = sorted(
            range(n),
            key=lambda i: (-isolation_scores[i], -distances[i]),
        )
        pick = min(self.max_outliers, n)

        result = CppDriftResult(mean_distance=mean_dist, threshold=threshold)
        for i in ranked[:pick]:
            result.outlier_ids.append(ids[i])
            result.outlier_scores.append(isolation_scores[i])
            result.outlier_reasons.append(
                f"BFS isolation score={isolation_scores[i]:.1f}, "
                f"centroid distance={distances[i]:.4f} "
                f"(threshold={threshold:.4f}), label_id={labels[i]}"
            )

        return result

    @staticmethod
    def _bfs_isolation(
        n: int,
        neighbors: List[List[int]],
        distances: np.ndarray,
        k_nearest: int,
        max_hops: int,
    ) -> List[float]:
        """BFS 层序遍历，返回每个节点的孤立度分数。"""
        # 按到质心距离升序排列，取前 k 个作为种子
        sorted_indices = np.argsort(distances)
        seed_count = min(k_nearest, n)
        seeds = sorted_indices[:seed_count].tolist()

        # BFS
        hop: List[int] = [-1] * n  # -1 = 未访问
        queue: deque = deque()

        for s in seeds:
            if hop[s] == -1:
                hop[s] = 0
                queue.append(s)

        current_hop = 0
        while queue and current_hop < max_hops:
            level_size = len(queue)
            current_hop += 1
            for _ in range(level_size):
                u = queue.popleft()
                for v in neighbors[u]:
                    if hop[v] == -1:
                        hop[v] = current_hop
                        queue.append(v)

        # 分数：跳数越大越孤立；未访问 = max_hops + 1
        max_score = float(max_hops + 1)
        return [float(h) if h != -1 else max_score for h in hop]


# ══════════════════════════════════════════════════════════════
# 原生 C++ 后端（pybind11 桥接）
# ══════════════════════════════════════════════════════════════

class NativeCppBackend:
    """
    通过 pybind11 调用编译后的 C++ FeatureGraph 引擎。

    要求已编译 feature_graph_py 模块：
        cd backend_cpp && mkdir build && cd build
        cmake .. && cmake --build .
    """

    def __init__(self, **kwargs) -> None:
        try:
            import feature_graph_py as fgp  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "feature_graph_py 模块未编译。"
                "请先在 backend_cpp/build/ 下执行 cmake 编译。"
            ) from exc

        self._fgp = fgp
        self._detector = fgp.DriftDetector(
            embedding_dim=kwargs.get("embedding_dim", 128),
            sigma=kwargs.get("sigma", 2.0),
            max_outliers=kwargs.get("max_outliers", 3),
            k_nearest=kwargs.get("k_nearest", 5),
            max_bfs_hops=kwargs.get("max_bfs_hops", 10),
            adjacency_threshold=kwargs.get("adjacency_threshold", 15.0),
        )
        logger.info("NativeCppBackend 初始化成功 | C++ 引擎版本=%s", fgp.__version__)

    def detect(
        self,
        ids: List[int],
        labels: List[int],
        embeddings: np.ndarray,
    ) -> CppDriftResult:
        """调用 C++ DriftDetector::detect。"""
        ids_arr = np.array(ids, dtype=np.uint32)
        labels_arr = np.array(labels, dtype=np.uint32)
        emb_arr = np.asarray(embeddings, dtype=np.float64).flatten()

        result = self._detector.detect(ids_arr, labels_arr, emb_arr)

        return CppDriftResult(
            outlier_ids=[int(x) for x in result.outlier_ids],
            outlier_scores=[float(x) for x in result.outlier_scores],
            outlier_reasons=list(result.outlier_reasons),
            mean_distance=float(result.mean_distance),
            threshold=float(result.threshold),
        )


# ══════════════════════════════════════════════════════════════
# 统一门面（自动选择后端）
# ══════════════════════════════════════════════════════════════

class CppBackendFacade:
    """
    C++ 引擎的统一 Python 门面。

    自动检测编译后的 C++ 模块是否可用：
    - 可用 → 使用 NativeCppBackend
    - 不可用 → 降级到 MockCppBackend
    """

    def __init__(self, **kwargs) -> None:
        self._backend: object
        try:
            self._backend = NativeCppBackend(**kwargs)
            self._mode = "native_cpp"
            logger.info("CppBackendFacade: 使用原生 C++ 后端")
        except ImportError:
            self._backend = MockCppBackend(**kwargs)
            self._mode = "mock_python"
            logger.warning(
                "CppBackendFacade: C++ 模块不可用，降级到 Mock Python 后端"
            )

    @property
    def mode(self) -> str:
        return self._mode

    def detect(
        self,
        ids: List[int],
        labels: List[int],
        embeddings: np.ndarray,
    ) -> CppDriftResult:
        """执行漂移检测（自动路由到可用后端）。"""
        return self._backend.detect(ids, labels, embeddings)  # type: ignore
