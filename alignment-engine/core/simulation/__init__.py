"""
core.simulation 包 —— 世界模型与反事实数据引擎。

子模块：
  - world_model_engine: 扩散模型底层 Latent 空间操作
  - synthetic_quality_validator: FID + CLIP 余弦相似度评估
"""

from __future__ import annotations

__all__ = [
    "world_model_engine",
    "synthetic_quality_validator",
]
