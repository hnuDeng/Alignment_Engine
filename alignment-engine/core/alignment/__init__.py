"""
core.alignment -- RLHF/DPO 偏好对齐微调引擎。

本子包负责处理人类修正标签并在本地执行大模型偏好对齐。
包含两个核心模块：
- dpo_trainer: 底层 DPO 数学实现（纯 PyTorch，禁用 trl）
- preference_graph_builder: 元数据状态树 DFS 比对 + Pydantic 数据验证
"""

from core.alignment.dpo_trainer import (
    DPOConfig,
    DPOTrainer,
    DPOTrainingException,
    VRAMExhaustedException,
    GradientExplodeException,
    InvalidBatchException,
)
from core.alignment.preference_graph_builder import (
    PreferencePair,
    MetadataTree,
    PreferenceDatasetFactory,
    PreferenceBuilderException,
    TreeMismatchException,
    PairValidationException,
)

__all__ = [
    "DPOConfig",
    "DPOTrainer",
    "DPOTrainingException",
    "VRAMExhaustedException",
    "GradientExplodeException",
    "InvalidBatchException",
    "PreferencePair",
    "MetadataTree",
    "PreferenceDatasetFactory",
    "PreferenceBuilderException",
    "TreeMismatchException",
    "PairValidationException",
]
