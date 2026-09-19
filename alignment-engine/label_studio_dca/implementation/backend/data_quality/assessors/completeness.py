"""
Completeness assessor for checking annotation coverage.
"""

import logging
from typing import Any, Dict, List

from backend.data_quality.assessors.base import AssessmentResult, BaseAssessor

logger = logging.getLogger(__name__)


class CompletenessAssessor(BaseAssessor):
    """
    Assessor for annotation completeness.
    
    Checks:
    - Task coverage (how many tasks are annotated)
    - Annotation density (annotations per task)
    - Missing annotations
    """
    
    @property
    def name(self) -> str:
        return 'completeness'
    
    @property
    def description(self) -> str:
        return 'Assesses annotation completeness'
    
    def assess(
        self,
        tasks: List[Dict[str, Any]],
        annotations: List[Dict[str, Any]],
        include_details: bool = True
    ) -> AssessmentResult:
        """
        Run completeness assessment.
        
        Args:
            tasks: List of task data
            annotations: List of annotation data
            include_details: Whether to include detailed statistics
        
        Returns:
            AssessmentResult with completeness score and issues
        """
        self.issues = []
        self.statistics = {}
        
        if not tasks:
            return AssessmentResult(
                assessor_name=self.name,
                score=1.0,
                statistics={'message': 'No tasks to assess'},
                issues=[],
            )
        
        # Count annotated tasks
        annotated_task_ids = set(ann['task_id'] for ann in annotations)
        total_tasks = len(tasks)
        annotated_tasks = len(annotated_task_ids)
        unannotated_tasks = total_tasks - annotated_tasks
        
        # Compute coverage
        coverage = annotated_tasks / total_tasks if total_tasks > 0 else 0
        
        # Check for low coverage
        if coverage < 0.5:
            self.add_issue(
                issue_type='missing',
                severity='high' if coverage < 0.2 else 'medium',
                title='Low annotation coverage',
                description=f'Only {coverage:.1%} of tasks have annotations',
                details={
                    'total_tasks': total_tasks,
                    'annotated_tasks': annotated_tasks,
                    'unannotated_tasks': unannotated_tasks,
                    'coverage': coverage,
                }
            )
        
        # Compute annotation density
        total_annotations = len(annotations)
        avg_annotations_per_task = total_annotations / annotated_tasks if annotated_tasks > 0 else 0
        
        # Compute completeness score
        completeness_score = coverage * 0.7 + min(1.0, avg_annotations_per_task / 1.0) * 0.3
        
        self.statistics = {
            'total_tasks': total_tasks,
            'annotated_tasks': annotated_tasks,
            'unannotated_tasks': unannotated_tasks,
            'coverage': coverage,
            'total_annotations': total_annotations,
            'avg_annotations_per_task': avg_annotations_per_task,
        }
        
        return AssessmentResult(
            assessor_name=self.name,
            score=completeness_score,
            statistics=self.statistics,
            issues=self.issues,
        )
