"""
单元测试 —— 感知模块 (core/extractor.py)

覆盖范围：
- Mock 提取路径的正确性
- 返回数据结构的完整性
- 嵌入维度和样本数的验证
- 多次提取的随机性（UUID 不同）
"""

from __future__ import annotations

import sys
from unittest.mock import patch, MagicMock

import pytest
import numpy as np

from schemas import DataSliceContext
from core.extractor import Extractor


class TestExtractorMockMode:
    """测试 Extractor 的 Mock 降级路径。"""

    def setup_method(self) -> None:
        """每个测试前创建新的 Extractor 实例。"""
        self.extractor = Extractor(mock_sample_count=10, embedding_dim=128)

    def test_mock_returns_data_slice_context(self) -> None:
        """Mock 模式应返回 DataSliceContext 实例。"""
        # 强制使用 mock 路径（模拟 FiftyOne 不可用）
        with patch.dict(sys.modules, {"fiftyone": None}):
            ctx = self.extractor.extract()

        assert isinstance(ctx, DataSliceContext)

    def test_mock_source_field(self) -> None:
        """Mock 模式返回的 source 应为 'mock'。"""
        ctx = self.extractor._extract_mock()
        assert ctx.source == "mock"

    def test_mock_sample_count(self) -> None:
        """Mock 模式应生成指定数量的样本。"""
        ctx = self.extractor._extract_mock()
        assert ctx.total_count == 10
        assert len(ctx.sample_records) == 10

    def test_custom_sample_count(self) -> None:
        """支持自定义样本数量。"""
        ext = Extractor(mock_sample_count=5)
        ctx = ext._extract_mock()
        assert ctx.total_count == 5

    def test_embedding_dimension(self) -> None:
        """所有样本的嵌入维度应为 128。"""
        ctx = self.extractor._extract_mock()
        for record in ctx.sample_records:
            assert len(record.embedding) == 128

    def test_labels_cycle(self) -> None:
        """标签应循环使用 MOCK_LABELS 池。"""
        ctx = self.extractor._extract_mock()
        labels = [r.label for r in ctx.sample_records]
        # 前 10 个标签应来自 MOCK_LABELS（有 10 个标签）
        expected = [
            "cat", "dog", "bird", "car", "bicycle",
            "airplane", "boat", "horse", "deer", "truck",
        ]
        assert labels == expected

    def test_unique_image_ids(self) -> None:
        """每个样本的 image_id 应唯一。"""
        ctx = self.extractor._extract_mock()
        ids = [r.image_id for r in ctx.sample_records]
        assert len(ids) == len(set(ids))

    def test_timestamp_format(self) -> None:
        """提取时间戳应为 ISO 格式字符串。"""
        ctx = self.extractor._extract_mock()
        assert "T" in ctx.extraction_timestamp
        assert "+" in ctx.extraction_timestamp or "Z" in ctx.extraction_timestamp

    def test_metadata_populated(self) -> None:
        """每个样本应包含元数据。"""
        ctx = self.extractor._extract_mock()
        for record in ctx.sample_records:
            assert "camera_model" in record.metadata
            assert "weather" in record.metadata
            assert "time_of_day" in record.metadata

    def test_embeddings_are_numeric(self) -> None:
        """嵌入向量的所有元素应为浮点数。"""
        ctx = self.extractor._extract_mock()
        for record in ctx.sample_records:
            for val in record.embedding:
                assert isinstance(val, float)

    def test_different_extractions_yield_different_ids(self) -> None:
        """两次独立提取应生成不同的 UUID。"""
        ctx1 = self.extractor._extract_mock()
        ctx2 = self.extractor._extract_mock()
        ids1 = {r.image_id for r in ctx1.sample_records}
        ids2 = {r.image_id for r in ctx2.sample_records}
        # 由于 seed=42 相同，UUID 是确定的；但两次调用应各自独立
        # 这里用不同 seed 验证
        ext2 = Extractor(mock_sample_count=10)
        ctx2 = ext2._extract_mock()
        ids2 = {r.image_id for r in ctx2.sample_records}
        assert ids1 != ids2

    def test_mode_property_after_mock(self) -> None:
        """提取后 mode 属性应为 'mock'。"""
        self.extractor._extract_mock()
        assert self.extractor.mode == "mock"

    def test_extract_fallback_on_import_error(self) -> None:
        """当 FiftyOne 不可用时，extract() 应自动降级到 Mock。"""
        # 确保 fiftyone 模块不可导入
        with patch.dict(sys.modules, {"fiftyone": None}):
            ctx = self.extractor.extract()
        assert ctx.source == "mock"
        assert self.extractor.mode == "mock"


class TestExtractorEdgeCases:
    """测试 Extractor 的边界情况。"""

    def test_single_sample(self) -> None:
        """只生成 1 个样本时应正常工作。"""
        ext = Extractor(mock_sample_count=1)
        ctx = ext._extract_mock()
        assert ctx.total_count == 1
        assert len(ctx.sample_records) == 1

    def test_large_sample_count(self) -> None:
        """生成 100 个样本时应正常工作。"""
        ext = Extractor(mock_sample_count=100)
        ctx = ext._extract_mock()
        assert ctx.total_count == 100

    def test_class_offset_in_embeddings(self) -> None:
        """不同类别的嵌入应有不同的偏移量。"""
        ext = Extractor(mock_sample_count=2, embedding_dim=128)
        ctx = ext._extract_mock()
        # 第 0 个样本偏移量 0，第 1 个偏移量 0.5
        mean0 = np.mean(ctx.sample_records[0].embedding)
        mean1 = np.mean(ctx.sample_records[1].embedding)
        # 两者均值应有明显差异
        assert abs(mean0 - mean1) > 0.1

class TestExtractorFiftyOneMode:
    def setup_method(self) -> None:
        self.extractor = Extractor(mock_sample_count=2, embedding_dim=128)

    @patch('core.extractor.logger')
    def test_extract_via_fiftyone_no_session(self, mock_logger) -> None:
        fiftyone_mock = MagicMock()
        fiftyone_mock.launch_app.return_value = None
        with patch.dict(sys.modules, {"fiftyone": fiftyone_mock}):
            ctx = self.extractor.extract()
            assert self.extractor.mode == "mock"
            assert ctx.source == "mock"
            mock_logger.warning.assert_called()

    def test_extract_via_fiftyone_empty_dataset(self) -> None:
        fiftyone_mock = MagicMock()
        session_mock = MagicMock()
        fiftyone_mock.launch_app.return_value = session_mock
        session_mock.dataset = MagicMock()
        session_mock.dataset.__len__.return_value = 0
        
        with patch.dict(sys.modules, {"fiftyone": fiftyone_mock}):
            ctx = self.extractor.extract()
            assert self.extractor.mode == "mock"

    def test_extract_via_fiftyone_success(self) -> None:
        fiftyone_mock = MagicMock()
        session_mock = MagicMock()
        fiftyone_mock.launch_app.return_value = session_mock
        
        dataset_mock = MagicMock()
        session_mock.dataset = dataset_mock
        dataset_mock.__len__.return_value = 2
        
        view_mock = MagicMock()
        dataset_mock.view.return_value = view_mock
        view_mock.values.return_value = ["id1", "id2"]
        
        sample1 = MagicMock()
        sample1.__getitem__.side_effect = lambda k: [0.1]*128 if k == "embedding" else "val"
        sample1.get.return_value = ["tag1"]
        sample1.field_names = ["id", "filepath", "tags", "embedding", "custom_meta"]
        
        sample2 = MagicMock()
        # Let sample2 have no embedding to test exception fallback
        sample2.__getitem__.side_effect = KeyError("No embedding")
        sample2.get.return_value = None
        sample2.field_names = ["id"]
        
        dataset_mock.__getitem__.side_effect = lambda x: sample1 if x == "id1" else sample2
        
        with patch.dict(sys.modules, {"fiftyone": fiftyone_mock}):
            ctx = self.extractor.extract()
            
            assert self.extractor.mode == "fiftyone"
            assert ctx.source == "fiftyone"
            assert len(ctx.sample_records) == 2
            
            meta_count = sum(1 for r in ctx.sample_records if "custom_meta" in r.metadata)
            assert meta_count == 1
