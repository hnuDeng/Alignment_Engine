"""
数据契约层 —— 基于 Pydantic 的不可变数据结构定义。

本模块定义了多智能体流水线中各节点之间传递的所有数据模型。
所有模型均配置为 frozen=True，保证数据在整个流水线中的不可变性与可追溯性。
"""

from __future__ import annotations

import uuid
from typing import Dict, List, Optional

import numpy as np
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# 共享配置：所有模型均为不可变的 (frozen)
# ---------------------------------------------------------------------------
class _FrozenBase(BaseModel):
    """所有数据契约的基类，强制不可变。"""

    model_config = {"frozen": True, "arbitrary_types_allowed": True}


# ---------------------------------------------------------------------------
# 节点 1 → 节点 2 的数据契约
# ---------------------------------------------------------------------------
class SampleRecord(_FrozenBase):
    """单个数据样本的结构化记录。"""

    image_id: str = Field(..., description="样本唯一标识 (UUID 字符串)")
    label: str = Field(..., description="分类标签，如 'cat', 'dog'")
    embedding: List[float] = Field(
        ..., description="128 维特征向量（嵌入表示）"
    )
    metadata: Dict[str, str] = Field(
        default_factory=dict, description="可选的额外元数据"
    )

    @field_validator("embedding")
    @classmethod
    def validate_embedding_dim(cls, v: List[float]) -> List[float]:
        """校验嵌入维度为 128。"""
        if len(v) != 128:
            raise ValueError(
                f"嵌入维度应为 128，实际为 {len(v)}"
            )
        return v


class DataSliceContext(_FrozenBase):
    """
    Extractor 输出 / Analyzer 输入 的数据切片上下文。

    包含一组从数据集中提取的样本记录，以及来源描述和时间戳等元信息。
    """

    source: str = Field(..., description="数据来源描述，如 'fiftyone' 或 'mock'")
    sample_records: List[SampleRecord] = Field(
        ..., min_length=1, description="样本记录列表"
    )
    extraction_timestamp: str = Field(
        ..., description="提取时间戳 (ISO 格式)"
    )
    total_count: int = Field(..., description="样本总数")

    @field_validator("total_count")
    @classmethod
    def validate_count_matches(cls, v: int, info) -> int:
        """校验 total_count 与实际记录数一致。"""
        records = info.data.get("sample_records")
        if records is not None and v != len(records):
            raise ValueError(
                f"total_count ({v}) 与 sample_records 长度 "
                f"({len(records)}) 不一致"
            )
        return v


# ---------------------------------------------------------------------------
# 节点 2 → 节点 3 的数据契约
# ---------------------------------------------------------------------------
class DriftSample(_FrozenBase):
    """单个分布漂移异常样本的详细信息。"""

    image_id: str = Field(..., description="异常样本的唯一标识")
    drift_score: float = Field(
        ..., description="漂移分数（越大越异常）"
    )
    reason: str = Field(..., description="被判定为异常的原因说明")


class DriftReport(_FrozenBase):
    """
    Analyzer 输出 / Reviewer 输入 的分布漂移报告。

    包含被检测出的异常样本列表、漂移原因以及整体统计摘要。
    """

    drift_samples: List[DriftSample] = Field(
        ..., min_length=1, description="异常样本列表"
    )
    drift_sample_ids: List[str] = Field(
        ..., description="异常样本 ID 汇总（便于下游快速查询）"
    )
    mean_distance: float = Field(
        ..., description="所有样本到质心的平均欧氏距离"
    )
    threshold: float = Field(
        ..., description="用于判定异常的距离阈值"
    )
    analysis_mode: str = Field(
        ..., description="分析模式，如 'cuda' 或 'mock_numpy'"
    )

    @field_validator("drift_sample_ids")
    @classmethod
    def validate_ids_match(cls, v: List[str], info) -> List[str]:
        """校验 drift_sample_ids 与 drift_samples 中的 ID 一致。"""
        samples = info.data.get("drift_samples")
        if samples is not None:
            expected = [s.image_id for s in samples]
            if v != expected:
                raise ValueError(
                    "drift_sample_ids 与 drift_samples 中的 image_id 不一致"
                )
        return v


# ---------------------------------------------------------------------------
# 节点 3 输出数据契约
# ---------------------------------------------------------------------------
class ReviewDecision(_FrozenBase):
    """
    Reviewer 输出的最终审计决策。

    包含生成的 FiftyOne 更新脚本、AST 静态审计结果以及执行日志。
    """

    generated_script: str = Field(
        ..., description="生成的 FiftyOne 更新脚本 (Python 代码字符串)"
    )
    ast_check_passed: bool = Field(
        ..., description="AST 静态检查是否通过"
    )
    ast_issues: List[str] = Field(
        default_factory=list,
        description="AST 检查发现的安全问题列表（为空表示无问题）",
    )
    executed: bool = Field(
        ..., description="脚本是否被实际执行"
    )
    execution_log: Optional[str] = Field(
        default=None, description="执行日志或错误信息"
    )
