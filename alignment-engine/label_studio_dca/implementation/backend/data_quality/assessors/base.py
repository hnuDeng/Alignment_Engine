"""
Base class for quality assessors.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class QualityIssueData:
    """Represents a quality issue found during assessment."""
    
    issue_type: str
    severity: str
    title: str
    description: str
    task_id: Optional[int] = None
    annotation_id: Optional[int] = None
    annotator_id: Optional[int] = None
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'issue_type': self.issue_type,
            'severity': self.severity,
            'title': self.title,
            'description': self.description,
            'task_id': self.task_id,
            'annotation_id': self.annotation_id,
            'annotator_id': self.annotator_id,
            'details': self.details,
        }


@dataclass
class AssessmentResult:
    """Result of a quality assessment."""
    
    assessor_name: str
    score: float  # 0-1, higher is better
    statistics: Dict[str, Any]
    issues: List[QualityIssueData]
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'assessor': self.assessor_name,
            'score': self.score,
            'statistics': self.statistics,
            'issue_count': len(self.issues),
            'issues': [issue.to_dict() for issue in self.issues],
            'details': self.details,
        }


class BaseAssessor(ABC):
    """Base class for all quality assessors."""
    
    def __init__(self, project_id: int):
        """
        Initialize assessor.
        
        Args:
            project_id: Project ID
        """
        self.project_id = project_id
        self.issues: List[QualityIssueData] = []
        self.statistics: Dict[str, Any] = {}
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Assessor name."""
        raise NotImplementedError
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Assessor description."""
        raise NotImplementedError
    
    @abstractmethod
    def assess(
        self,
        tasks: List[Dict[str, Any]],
        annotations: List[Dict[str, Any]],
        include_details: bool = True
    ) -> AssessmentResult:
        """
        Run assessment.
        
        Args:
            tasks: List of task data
            annotations: List of annotation data
            include_details: Whether to include detailed statistics
        
        Returns:
            AssessmentResult
        """
        raise NotImplementedError
    
    def add_issue(
        self,
        issue_type: str,
        severity: str,
        title: str,
        description: str,
        task_id: Optional[int] = None,
        annotation_id: Optional[int] = None,
        annotator_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Add a quality issue."""
        issue = QualityIssueData(
            issue_type=issue_type,
            severity=severity,
            title=title,
            description=description,
            task_id=task_id,
            annotation_id=annotation_id,
            annotator_id=annotator_id,
            details=details or {},
        )
        self.issues.append(issue)
    
    def extract_label(self, annotation: Dict[str, Any]) -> str:
        """
        Extract label from annotation result.
        
        Args:
            annotation: Annotation dictionary
        
        Returns:
            Label string
        """
        result = annotation.get('result', [])
        
        for item in result:
            value = item.get('value', {})
            
            # Handle choices
            if 'choices' in value:
                choices = value['choices']
                if isinstance(choices, list) and choices:
                    return choices[0]
                elif isinstance(choices, dict):
                    return max(choices.items(), key=lambda x: x[1])[0]
            
            # Handle labels
            if 'labels' in value:
                labels = value['labels']
                if isinstance(labels, list) and labels:
                    return labels[0]
        
        return 'unknown'
