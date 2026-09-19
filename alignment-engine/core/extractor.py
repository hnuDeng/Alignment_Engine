"""
感知模块 (Extractor) —— 负责从数据集提取样本并封装为 DataSliceContext。

本模块实现了两条路径：
1. **FiftyOne 路径**：连接 FiftyOne Session，从当前视图中提取长尾样本。
2. **Mock 降级路径**：若 FiftyOne 不可用，使用 numpy / uuid 随机生成 10 条
   包含 128 维嵌入的模拟样本数据。

两种路径均返回符合 `DataSliceContext` 数据契约的不可变对象。
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import List

import numpy as np

from schemas import DataSliceContext, SampleRecord

logger = logging.getLogger(__name__)

# 模拟的标签池
_MOCK_LABELS: List[str] = [
    "cat", "dog", "bird", "car", "bicycle",
    "airplane", "boat", "horse", "deer", "truck",
]

# 模拟的元数据键值
_MOCK_METADATA_KEYS = ["camera_model", "weather", "time_of_day"]
_MOCK_METADATA_VALUES = {
    "camera_model": ["Canon EOS R5", "Sony A7III", "Nikon Z6"],
    "weather": ["sunny", "cloudy", "rainy", "snowy"],
    "time_of_day": ["morning", "afternoon", "evening", "night"],
}


class Extractor:
    """
    感知模块：从数据集提取样本特征与元数据。

    工作流程：
    1. 尝试导入 FiftyOne 并获取活动 Session。
    2. 若成功，从当前视图中随机选取样本（模拟长尾检测）。
    3. 若失败（ImportError 或无活动 Session），回退到 Mock 模式。

    Attributes:
        mock_sample_count: Mock 模式下生成的样本数量。
        embedding_dim: 嵌入向量的维度。
    """

    def __init__(
        self,
        mock_sample_count: int = 10,
        embedding_dim: int = 128,
    ) -> None:
        self.mock_sample_count = mock_sample_count
        self.embedding_dim = embedding_dim
        self._mode: str = "unknown"
        logger.info(
            "Extractor 初始化完成 | mock_sample_count=%d | embedding_dim=%d",
            mock_sample_count,
            embedding_dim,
        )

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------
    def extract(self) -> DataSliceContext:
        """
        执行样本提取。

        优先尝试 FiftyOne 路径，失败后自动降级到 Mock 路径。

        Returns:
            DataSliceContext: 包含样本记录的数据切片上下文。
        """
        try:
            return self._extract_via_fiftyone()
        except Exception as exc:
            logger.warning(
                "FiftyOne 路径失败 (%s: %s)，降级到 Mock 模式",
                type(exc).__name__,
                exc,
            )
            return self._extract_mock()

    @property
    def mode(self) -> str:
        """当前运行模式：'fiftyone' 或 'mock'。"""
        return self._mode

    # ------------------------------------------------------------------
    # FiftyOne 路径
    # ------------------------------------------------------------------
    def _extract_via_fiftyone(self) -> DataSliceContext:
        """
        通过 FiftyOne 提取样本。

        Raises:
            ImportError: FiftyOne 未安装。
            RuntimeError: 无可用的 FiftyOne Session 或数据集为空。

        Returns:
            DataSliceContext: 真实数据切片上下文。
        """
        import fiftyone as fo  # type: ignore[import-untyped]

        session = fo.launch_app()
        if session is None:
            raise RuntimeError("无法获取 FiftyOne Session")

        dataset = session.dataset
        if dataset is None or len(dataset) == 0:
            raise RuntimeError("当前数据集为空")

        # 获取视图并随机采样（模拟长尾检测）
        view = dataset.view()
        sample_ids = list(view.values("id"))
        rng = np.random.default_rng()
        selected_indices = rng.choice(
            len(sample_ids),
            size=min(self.mock_sample_count, len(sample_ids)),
            replace=False,
        )
        selected_ids = [sample_ids[i] for i in selected_indices]

        records: List[SampleRecord] = []
        for sid in selected_ids:
            sample = dataset[sid]
            # 尝试提取嵌入；若字段不存在则生成随机嵌入
            try:
                emb = list(sample["embedding"])
                if len(emb) != self.embedding_dim:
                    emb = list(rng.standard_normal(self.embedding_dim))
            except (KeyError, AttributeError, TypeError):
                emb = list(rng.standard_normal(self.embedding_dim))

            label = str(sample.get("tags", ["unknown"])[0]) if sample.get("tags") else "unknown"
            metadata = {}
            for field_name in sample.field_names:
                if field_name not in ("id", "filepath", "tags", "embedding"):
                    val = sample[field_name]
                    if isinstance(val, str):
                        metadata[field_name] = val

            records.append(
                SampleRecord(
                    image_id=str(sid),
                    label=label,
                    embedding=emb,
                    metadata=metadata,
                )
            )

        self._mode = "fiftyone"
        now = datetime.now(timezone.utc).isoformat()
        ctx = DataSliceContext(
            source="fiftyone",
            sample_records=records,
            extraction_timestamp=now,
            total_count=len(records),
        )
        logger.info(
            "FiftyOne 提取完成 | 样本数=%d | 时间=%s", len(records), now
        )
        return ctx

    # ------------------------------------------------------------------
    # Mock 降级路径
    # ------------------------------------------------------------------
    def _extract_mock(self) -> DataSliceContext:
        """
        使用 Mock 数据生成样本记录。

        生成包含随机 128 维嵌入、随机标签和随机元数据的模拟样本。

        Returns:
            DataSliceContext: Mock 数据切片上下文。
        """
        rng = np.random.default_rng(seed=42)
        records: List[SampleRecord] = []

        for i in range(self.mock_sample_count):
            image_id = str(uuid.uuid4())
            label = _MOCK_LABELS[i % len(_MOCK_LABELS)]
            # 使用不同均值模拟不同类别的嵌入分布
            class_offset = (i % len(_MOCK_LABELS)) * 0.5
            embedding = list(
                rng.normal(loc=class_offset, scale=1.0, size=self.embedding_dim)
            )
            metadata = {
                key: rng.choice(_MOCK_METADATA_VALUES[key])
                for key in _MOCK_METADATA_KEYS
            }
            records.append(
                SampleRecord(
                    image_id=image_id,
                    label=label,
                    embedding=embedding,
                    metadata=metadata,
                )
            )

        self._mode = "mock"
        now = datetime.now(timezone.utc).isoformat()
        ctx = DataSliceContext(
            source="mock",
            sample_records=records,
            extraction_timestamp=now,
            total_count=len(records),
        )
        logger.info(
            "Mock 提取完成 | 样本数=%d | 时间=%s", len(records), now
        )
        return ctx
