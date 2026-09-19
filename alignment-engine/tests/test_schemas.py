"""
单元测试 —— 数据契约层 (schemas.py)

覆盖范围：
- SampleRecord: 嵌入维度校验、不可变性
- DataSliceContext: total_count 一致性校验
- DriftReport: drift_sample_ids 一致性校验
- ReviewDecision: 完整构造
"""

from __future__ import annotations

import uuid
from typing import List

import pytest
from pydantic import ValidationError

from schemas import (
    DataSliceContext,
    DriftReport,
    DriftSample,
    ReviewDecision,
    SampleRecord,
)


# ---------------------------------------------------------------------------
# 辅助工厂
# ---------------------------------------------------------------------------
def _make_embedding(dim: int = 128, value: float = 0.0) -> List[float]:
    """生成指定维度的常量嵌入向量。"""
    return [value] * dim


def _make_sample_record(
    image_id: str | None = None,
    label: str = "cat",
    embedding: List[float] | None = None,
) -> SampleRecord:
    """创建一个 SampleRecord 实例。"""
    return SampleRecord(
        image_id=image_id or str(uuid.uuid4()),
        label=label,
        embedding=embedding or _make_embedding(),
    )


def _make_data_slice_context(
    n: int = 3, source: str = "mock"
) -> DataSliceContext:
    """创建一个包含 n 条记录的 DataSliceContext。"""
    records = [_make_sample_record(label=f"label_{i}") for i in range(n)]
    return DataSliceContext(
        source=source,
        sample_records=records,
        extraction_timestamp="2025-01-01T00:00:00+00:00",
        total_count=n,
    )


# ---------------------------------------------------------------------------
# SampleRecord 测试
# ---------------------------------------------------------------------------
class TestSampleRecord:
    """测试 SampleRecord 数据模型。"""

    def test_valid_creation(self) -> None:
        """正常创建 SampleRecord。"""
        rec = _make_sample_record(image_id="abc-123", label="dog")
        assert rec.image_id == "abc-123"
        assert rec.label == "dog"
        assert len(rec.embedding) == 128
        assert rec.metadata == {}

    def test_embedding_dim_validation(self) -> None:
        """嵌入维度不是 128 时应抛出 ValidationError。"""
        with pytest.raises(ValidationError, match="嵌入维度应为 128"):
            _make_sample_record(embedding=[0.0] * 64)

    def test_embedding_dim_too_large(self) -> None:
        """嵌入维度大于 128 时也应抛出 ValidationError。"""
        with pytest.raises(ValidationError, match="嵌入维度应为 128"):
            _make_sample_record(embedding=[0.0] * 256)

    def test_frozen_immutability(self) -> None:
        """SampleRecord 应为不可变对象。"""
        rec = _make_sample_record()
        with pytest.raises(ValidationError):
            rec.label = "changed"  # type: ignore[misc]

    def test_with_metadata(self) -> None:
        """支持携带自定义元数据。"""
        rec = _make_sample_record()
        rec_with_meta = SampleRecord(
            image_id=rec.image_id,
            label=rec.label,
            embedding=rec.embedding,
            metadata={"camera": "Canon", "weather": "sunny"},
        )
        assert rec_with_meta.metadata["camera"] == "Canon"


# ---------------------------------------------------------------------------
# DataSliceContext 测试
# ---------------------------------------------------------------------------
class TestDataSliceContext:
    """测试 DataSliceContext 数据模型。"""

    def test_valid_creation(self) -> None:
        """正常创建 DataSliceContext。"""
        ctx = _make_data_slice_context(n=5)
        assert ctx.total_count == 5
        assert len(ctx.sample_records) == 5
        assert ctx.source == "mock"

    def test_count_mismatch_raises(self) -> None:
        """total_count 与实际记录数不一致时应抛出 ValidationError。"""
        records = [_make_sample_record() for _ in range(3)]
        with pytest.raises(ValidationError, match="total_count.*不一致"):
            DataSliceContext(
                source="mock",
                sample_records=records,
                extraction_timestamp="2025-01-01T00:00:00",
                total_count=5,  # 不匹配
            )

    def test_empty_records_raises(self) -> None:
        """空的 sample_records 列表应抛出 ValidationError。"""
        with pytest.raises(ValidationError):
            DataSliceContext(
                source="mock",
                sample_records=[],
                extraction_timestamp="2025-01-01T00:00:00",
                total_count=0,
            )

    def test_frozen_immutability(self) -> None:
        """DataSliceContext 应为不可变对象。"""
        ctx = _make_data_slice_context()
        with pytest.raises(ValidationError):
            ctx.source = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# DriftReport 测试
# ---------------------------------------------------------------------------
class TestDriftReport:
    """测试 DriftReport 数据模型。"""

    def test_valid_creation(self) -> None:
        """正常创建 DriftReport。"""
        samples = [
            DriftSample(
                image_id="id-1", drift_score=5.0, reason="距离过大"
            ),
            DriftSample(
                image_id="id-2", drift_score=4.5, reason="均值偏移"
            ),
        ]
        report = DriftReport(
            drift_samples=samples,
            drift_sample_ids=["id-1", "id-2"],
            mean_distance=2.0,
            threshold=3.5,
            analysis_mode="mock_numpy",
        )
        assert len(report.drift_samples) == 2
        assert report.analysis_mode == "mock_numpy"

    def test_ids_mismatch_raises(self) -> None:
        """drift_sample_ids 与 drift_samples 中的 ID 不一致时应抛出异常。"""
        samples = [
            DriftSample(
                image_id="id-1", drift_score=5.0, reason="test"
            ),
        ]
        with pytest.raises(ValidationError, match="不一致"):
            DriftReport(
                drift_samples=samples,
                drift_sample_ids=["id-wrong"],
                mean_distance=2.0,
                threshold=3.5,
                analysis_mode="mock_numpy",
            )

    def test_frozen_immutability(self) -> None:
        """DriftReport 应为不可变对象。"""
        report = DriftReport(
            drift_samples=[
                DriftSample(image_id="x", drift_score=1.0, reason="r")
            ],
            drift_sample_ids=["x"],
            mean_distance=0.5,
            threshold=1.0,
            analysis_mode="mock_numpy",
        )
        with pytest.raises(ValidationError):
            report.threshold = 99.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ReviewDecision 测试
# ---------------------------------------------------------------------------
class TestReviewDecision:
    """测试 ReviewDecision 数据模型。"""

    def test_full_creation(self) -> None:
        """正常创建包含所有字段的 ReviewDecision。"""
        decision = ReviewDecision(
            generated_script="print('hello')",
            ast_check_passed=True,
            ast_issues=[],
            executed=True,
            execution_log="success",
        )
        assert decision.ast_check_passed is True
        assert decision.executed is True
        assert decision.execution_log == "success"

    def test_failed_decision(self) -> None:
        """创建 AST 检查失败的决策。"""
        decision = ReviewDecision(
            generated_script="import os; os.system('rm -rf /')",
            ast_check_passed=False,
            ast_issues=["禁止导入模块 'os'"],
            executed=False,
            execution_log="脚本未通过 AST 安全检查，拒绝执行",
        )
        assert decision.ast_check_passed is False
        assert len(decision.ast_issues) == 1
        assert decision.executed is False

    def test_optional_execution_log(self) -> None:
        """execution_log 可以为 None。"""
        decision = ReviewDecision(
            generated_script="x = 1",
            ast_check_passed=True,
            executed=False,
        )
        assert decision.execution_log is None

    def test_frozen_immutability(self) -> None:
        """ReviewDecision 应为不可变对象。"""
        decision = ReviewDecision(
            generated_script="x = 1",
            ast_check_passed=True,
            executed=False,
        )
        with pytest.raises(ValidationError):
            decision.executed = True  # type: ignore[misc]
