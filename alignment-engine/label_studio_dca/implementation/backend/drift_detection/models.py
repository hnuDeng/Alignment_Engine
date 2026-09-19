"""
Drift Detection data models.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class DriftLevel(Enum):
    """Drift severity levels."""
    NONE = 'none'
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'


class AlertStatus(Enum):
    """Alert status choices."""
    ACTIVE = 'active'
    ACKNOWLEDGED = 'acknowledged'
    RESOLVED = 'resolved'


class AlertType(Enum):
    """Types of drift alerts."""
    FEATURE = 'feature'
    LABEL = 'label'
    CONCEPT = 'concept'
    QUALITY = 'quality'


@dataclass
class DriftBaseline:
    """Baseline for drift detection."""
    
    id: int
    project_id: int
    name: str
    description: str = ''
    feature_statistics: Dict[str, Any] = field(default_factory=dict)
    label_distribution: Dict[str, Any] = field(default_factory=dict)
    sample_count: int = 0
    sample_start_date: Optional[datetime] = None
    sample_end_date: Optional[datetime] = None
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    created_by: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'project_id': self.project_id,
            'name': self.name,
            'description': self.description,
            'feature_statistics': self.feature_statistics,
            'label_distribution': self.label_distribution,
            'sample_count': self.sample_count,
            'sample_start_date': self.sample_start_date.isoformat() if self.sample_start_date else None,
            'sample_end_date': self.sample_end_date.isoformat() if self.sample_end_date else None,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
            'created_by': self.created_by,
        }


@dataclass
class DriftReport:
    """Drift detection report."""
    
    id: int
    project_id: int
    baseline_id: int
    drift_level: DriftLevel
    feature_drift_score: Optional[float] = None
    label_drift_score: Optional[float] = None
    overall_drift_score: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    task_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'project_id': self.project_id,
            'baseline_id': self.baseline_id,
            'drift_level': self.drift_level.value,
            'feature_drift_score': self.feature_drift_score,
            'label_drift_score': self.label_drift_score,
            'overall_drift_score': self.overall_drift_score,
            'details': self.details,
            'window_start': self.window_start.isoformat() if self.window_start else None,
            'window_end': self.window_end.isoformat() if self.window_end else None,
            'task_count': self.task_count,
            'created_at': self.created_at.isoformat(),
        }


@dataclass
class DriftAlert:
    """Drift alert."""
    
    id: int
    project_id: int
    report_id: Optional[int]
    alert_type: AlertType
    status: AlertStatus = AlertStatus.ACTIVE
    message: str = ''
    details: Dict[str, Any] = field(default_factory=dict)
    notified_users: List[int] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[int] = None
    resolved_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'project_id': self.project_id,
            'report_id': self.report_id,
            'alert_type': self.alert_type.value,
            'status': self.status.value,
            'message': self.message,
            'details': self.details,
            'notified_users': self.notified_users,
            'created_at': self.created_at.isoformat(),
            'acknowledged_at': self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            'acknowledged_by': self.acknowledged_by,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
        }
    
    def acknowledge(self, user_id: int):
        """Acknowledge the alert."""
        self.status = AlertStatus.ACKNOWLEDGED
        self.acknowledged_at = datetime.now()
        self.acknowledged_by = user_id
    
    def resolve(self):
        """Resolve the alert."""
        self.status = AlertStatus.RESOLVED
        self.resolved_at = datetime.now()


@dataclass
class DriftMonitorConfig:
    """Configuration for drift monitoring."""
    
    id: int
    project_id: int
    is_enabled: bool = False
    check_interval_hours: int = 24
    feature_drift_threshold: float = 0.3
    label_drift_threshold: float = 0.3
    alert_on_drift: bool = True
    notify_users: List[int] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'project_id': self.project_id,
            'is_enabled': self.is_enabled,
            'check_interval_hours': self.check_interval_hours,
            'feature_drift_threshold': self.feature_drift_threshold,
            'label_drift_threshold': self.label_drift_threshold,
            'alert_on_drift': self.alert_on_drift,
            'notify_users': self.notify_users,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


@dataclass
class DriftDetectionResult:
    """Result of drift detection."""
    
    has_drift: bool
    drift_score: float  # 0-1, higher = more drift
    p_value: Optional[float] = None
    statistic: Optional[float] = None
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'has_drift': self.has_drift,
            'drift_score': self.drift_score,
            'p_value': self.p_value,
            'statistic': self.statistic,
            'details': self.details,
        }
