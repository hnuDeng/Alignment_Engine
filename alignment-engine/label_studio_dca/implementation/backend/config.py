"""
Configuration settings for Data-Centric AI workflow.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ActiveLearningConfig:
    """Configuration for Active Learning module."""
    
    # Default strategy
    default_strategy: str = 'uncertainty'
    
    # Batch settings
    default_batch_size: int = 10
    max_batch_size: int = 1000
    
    # Uncertainty methods
    uncertainty_methods: List[str] = field(
        default_factory=lambda: ['least_confidence', 'margin_sampling', 'entropy']
    )
    
    # Diversity settings
    diversity_metric: str = 'cosine'
    
    # Committee settings
    committee_size: int = 5
    
    # Auto-training
    auto_train_enabled: bool = False
    min_annotations_for_training: int = 100


@dataclass
class DataQualityConfig:
    """Configuration for Data Quality module."""
    
    # Assessment settings
    auto_assess_enabled: bool = False
    assess_after_count: int = 100
    
    # Thresholds
    low_agreement_threshold: float = 0.5
    speed_anomaly_threshold: float = 3.0
    outlier_detection_enabled: bool = True
    
    # Issue severity levels
    severity_levels: List[str] = field(
        default_factory=lambda: ['low', 'medium', 'high', 'critical']
    )


@dataclass
class DriftDetectionConfig:
    """Configuration for Drift Detection module."""
    
    # Detection settings
    default_threshold: float = 0.05
    check_interval_hours: int = 24
    
    # Feature drift thresholds
    feature_drift_threshold: float = 0.3
    label_drift_threshold: float = 0.3
    
    # Alert settings
    alert_on_drift: bool = True
    alert_thresholds: Dict[str, float] = field(
        default_factory=lambda: {
            'low': 0.1,
            'medium': 0.3,
            'high': 0.5,
            'critical': 0.7,
        }
    )


@dataclass
class DCAConfig:
    """Main configuration for Data-Centric AI workflow."""
    
    active_learning: ActiveLearningConfig = field(
        default_factory=ActiveLearningConfig
    )
    data_quality: DataQualityConfig = field(
        default_factory=DataQualityConfig
    )
    drift_detection: DriftDetectionConfig = field(
        default_factory=DriftDetectionConfig
    )
    
    # General settings
    debug: bool = False
    log_level: str = 'INFO'
    max_workers: int = 4


# Global configuration instance
config = DCAConfig()
