"""
Data Quality data models.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ReportType(Enum):
    """Types of quality reports."""
    PROJECT = 'project'
    ANNOTATOR = 'annotator'
    TASK = 'task'
    LABEL = 'label'


class IssueType(Enum):
    """Types of quality issues."""
    INCONSISTENCY = 'inconsistency'
    OUTLIER = 'outlier'
    BIAS = 'bias'
    MISSING = 'missing'
    CONFLICT = 'conflict'
    LOW_AGREEMENT = 'low_agreement'
    SPEED_ANOMALY = 'speed_anomaly'


class SeverityLevel(Enum):
    """Severity levels for quality issues."""
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'


@dataclass
class QualityIssue:
    """Individual quality issue found during assessment."""
    
    id: int
    report_id: int
    issue_type: IssueType
    severity: SeverityLevel
    title: str
    description: str
    task_id: Optional[int] = None
    annotation_id: Optional[int] = None
    annotator_id: Optional[int] = None
    details: Dict[str, Any] = field(default_factory=dict)
    is_resolved: bool = False
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[int] = None
    resolution_notes: str = ''
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'report_id': self.report_id,
            'issue_type': self.issue_type.value,
            'severity': self.severity.value,
            'title': self.title,
            'description': self.description,
            'task_id': self.task_id,
            'annotation_id': self.annotation_id,
            'annotator_id': self.annotator_id,
            'details': self.details,
            'is_resolved': self.is_resolved,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'resolved_by': self.resolved_by,
            'resolution_notes': self.resolution_notes,
            'created_at': self.created_at.isoformat(),
        }
    
    def resolve(self, user_id: int, notes: str = ''):
        """Mark issue as resolved."""
        self.is_resolved = True
        self.resolved_at = datetime.now()
        self.resolved_by = user_id
        self.resolution_notes = notes


@dataclass
class QualityReport:
    """Data quality assessment report."""
    
    id: int
    project_id: int
    report_type: ReportType
    overall_score: float
    consistency_score: Optional[float] = None
    agreement_score: Optional[float] = None
    completeness_score: Optional[float] = None
    statistics: Dict[str, Any] = field(default_factory=dict)
    issue_count: int = 0
    critical_issue_count: int = 0
    tasks_analyzed: int = 0
    annotations_analyzed: int = 0
    annotators_analyzed: int = 0
    issues: List[QualityIssue] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    created_by: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'project_id': self.project_id,
            'report_type': self.report_type.value,
            'overall_score': self.overall_score,
            'consistency_score': self.consistency_score,
            'agreement_score': self.agreement_score,
            'completeness_score': self.completeness_score,
            'statistics': self.statistics,
            'issue_count': self.issue_count,
            'critical_issue_count': self.critical_issue_count,
            'tasks_analyzed': self.tasks_analyzed,
            'annotations_analyzed': self.annotations_analyzed,
            'annotators_analyzed': self.annotators_analyzed,
            'issues': [issue.to_dict() for issue in self.issues],
            'created_at': self.created_at.isoformat(),
            'created_by': self.created_by,
        }


@dataclass
class AnnotatorProfile:
    """Quality profile for an annotator."""
    
    id: int
    user_id: int
    project_id: int
    username: str
    total_annotations: int = 0
    agreement_rate: float = 0.0
    avg_annotation_time: float = 0.0
    quality_score: float = 0.0
    consistency_score: float = 0.0
    issue_count: int = 0
    critical_issue_count: int = 0
    statistics: Dict[str, Any] = field(default_factory=dict)
    first_annotation_at: Optional[datetime] = None
    last_annotation_at: Optional[datetime] = None
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'project_id': self.project_id,
            'username': self.username,
            'total_annotations': self.total_annotations,
            'agreement_rate': self.agreement_rate,
            'avg_annotation_time': self.avg_annotation_time,
            'quality_score': self.quality_score,
            'consistency_score': self.consistency_score,
            'issue_count': self.issue_count,
            'critical_issue_count': self.critical_issue_count,
            'statistics': self.statistics,
            'first_annotation_at': self.first_annotation_at.isoformat() if self.first_annotation_at else None,
            'last_annotation_at': self.last_annotation_at.isoformat() if self.last_annotation_at else None,
            'updated_at': self.updated_at.isoformat(),
        }


@dataclass
class LabelStats:
    """Quality statistics for a specific label."""
    
    id: int
    project_id: int
    label_name: str
    label_type: str
    usage_count: int = 0
    unique_annotators: int = 0
    agreement_rate: float = 0.0
    consistency_score: float = 0.0
    usage_percentage: float = 0.0
    statistics: Dict[str, Any] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'project_id': self.project_id,
            'label_name': self.label_name,
            'label_type': self.label_type,
            'usage_count': self.usage_count,
            'unique_annotators': self.unique_annotators,
            'agreement_rate': self.agreement_rate,
            'consistency_score': self.consistency_score,
            'usage_percentage': self.usage_percentage,
            'statistics': self.statistics,
            'updated_at': self.updated_at.isoformat(),
        }


@dataclass
class QualityConfig:
    """Configuration for quality assessment."""
    
    id: int
    project_id: int
    auto_assess: bool = False
    assess_after_count: int = 100
    low_agreement_threshold: float = 0.5
    speed_anomaly_threshold: float = 3.0
    outlier_detection_enabled: bool = True
    notify_on_critical: bool = True
    notify_users: List[int] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'project_id': self.project_id,
            'auto_assess': self.auto_assess,
            'assess_after_count': self.assess_after_count,
            'low_agreement_threshold': self.low_agreement_threshold,
            'speed_anomaly_threshold': self.speed_anomaly_threshold,
            'outlier_detection_enabled': self.outlier_detection_enabled,
            'notify_on_critical': self.notify_on_critical,
            'notify_users': self.notify_users,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


@dataclass
class AnnotationData:
    """Represents an annotation for quality assessment."""
    
    id: int
    task_id: int
    annotator_id: int
    result: List[Dict[str, Any]]
    lead_time: Optional[float] = None
    was_cancelled: bool = False
    ground_truth: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'task_id': self.task_id,
            'annotator_id': self.annotator_id,
            'result': self.result,
            'lead_time': self.lead_time,
            'was_cancelled': self.was_cancelled,
            'ground_truth': self.ground_truth,
            'created_at': self.created_at.isoformat(),
        }
