"""
Active Learning data models.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class StrategyType(Enum):
    """Available active learning strategies."""
    UNCERTAINTY = 'uncertainty'
    DIVERSITY = 'diversity'
    COMMITTEE = 'committee'
    HYBRID = 'hybrid'
    RANDOM = 'random'


class UncertaintyMethod(Enum):
    """Uncertainty sampling methods."""
    LEAST_CONFIDENCE = 'least_confidence'
    MARGIN_SAMPLING = 'margin_sampling'
    ENTROPY = 'entropy'


@dataclass
class TaskData:
    """Represents a task with its data and metadata."""
    
    id: int
    data: Dict[str, Any]
    meta: Optional[Dict[str, Any]] = None
    is_labeled: bool = False
    total_annotations: int = 0
    total_predictions: int = 0
    created_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'data': self.data,
            'meta': self.meta,
            'is_labeled': self.is_labeled,
            'total_annotations': self.total_annotations,
            'total_predictions': self.total_predictions,
        }


@dataclass
class Prediction:
    """Represents a model prediction for a task."""
    
    task_id: int
    result: List[Dict[str, Any]]
    score: Optional[float] = None
    model_version: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'task_id': self.task_id,
            'result': self.result,
            'score': self.score,
            'model_version': self.model_version,
        }


@dataclass
class TaskScore:
    """Represents the selection score for a task."""
    
    task_id: int
    uncertainty_score: Optional[float] = None
    diversity_score: Optional[float] = None
    committee_disagreement: Optional[float] = None
    final_score: float = 0.0
    rank: int = 0
    is_selected: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'task_id': self.task_id,
            'uncertainty_score': self.uncertainty_score,
            'diversity_score': self.diversity_score,
            'committee_disagreement': self.committee_disagreement,
            'final_score': self.final_score,
            'rank': self.rank,
            'is_selected': self.is_selected,
        }


@dataclass
class SelectionResult:
    """Result of a task selection operation."""
    
    round_id: int
    round_number: int
    selected_task_ids: List[int]
    task_scores: Dict[int, float]
    strategy_used: str
    avg_uncertainty: float
    diversity_score: float
    selection_summary: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'round_id': self.round_id,
            'round_number': self.round_number,
            'selected_task_ids': self.selected_task_ids,
            'task_scores': self.task_scores,
            'strategy_used': self.strategy_used,
            'avg_uncertainty': self.avg_uncertainty,
            'diversity_score': self.diversity_score,
            'selection_summary': self.selection_summary,
            'created_at': self.created_at.isoformat(),
        }


@dataclass
class ActiveLearningRound:
    """Represents a round of active learning."""
    
    id: int
    config_id: int
    round_number: int
    selected_tasks: List[int]
    task_count: int
    strategy_used: str
    selection_scores: Dict[int, float]
    avg_uncertainty: Optional[float] = None
    diversity_score: Optional[float] = None
    is_completed: bool = False
    completed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'config_id': self.config_id,
            'round_number': self.round_number,
            'selected_tasks': self.selected_tasks,
            'task_count': self.task_count,
            'strategy_used': self.strategy_used,
            'selection_scores': self.selection_scores,
            'avg_uncertainty': self.avg_uncertainty,
            'diversity_score': self.diversity_score,
            'is_completed': self.is_completed,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat(),
        }


@dataclass
class ActiveLearningConfig:
    """Configuration for active learning in a project."""
    
    id: int
    project_id: int
    strategy: StrategyType = StrategyType.UNCERTAINTY
    uncertainty_method: UncertaintyMethod = UncertaintyMethod.ENTROPY
    batch_size: int = 10
    is_enabled: bool = False
    auto_select: bool = False
    auto_train: bool = False
    min_annotations_for_training: int = 10
    diversity_metric: str = 'cosine'
    committee_size: int = 5
    strategy_params: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'project_id': self.project_id,
            'strategy': self.strategy.value,
            'uncertainty_method': self.uncertainty_method.value,
            'batch_size': self.batch_size,
            'is_enabled': self.is_enabled,
            'auto_select': self.auto_select,
            'auto_train': self.auto_train,
            'min_annotations_for_training': self.min_annotations_for_training,
            'diversity_metric': self.diversity_metric,
            'committee_size': self.committee_size,
            'strategy_params': self.strategy_params,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }
    
    def get_strategy_instance(self):
        """Get the strategy instance based on configuration."""
        from backend.active_learning.strategies import get_strategy
        
        return get_strategy(
            strategy_name=self.strategy.value,
            uncertainty_method=self.uncertainty_method.value,
            diversity_metric=self.diversity_metric,
            committee_size=self.committee_size,
            **self.strategy_params
        )


@dataclass
class ActiveLearningFeedback:
    """Feedback from annotators about selection quality."""
    
    id: int
    config_id: int
    task_id: int
    feedback_type: str  # 'useful', 'not_useful', 'already_known', 'too_difficult', 'too_easy'
    comment: Optional[str] = None
    created_by: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'config_id': self.config_id,
            'task_id': self.task_id,
            'feedback_type': self.feedback_type,
            'comment': self.comment,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat(),
        }
