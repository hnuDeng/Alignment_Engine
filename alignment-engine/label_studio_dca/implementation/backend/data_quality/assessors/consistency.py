"""
Consistency assessor for detecting annotation inconsistencies.
"""

import logging
from collections import defaultdict
from typing import Any, Dict, List

import numpy as np

from backend.data_quality.assessors.base import AssessmentResult, BaseAssessor

logger = logging.getLogger(__name__)


class ConsistencyAssessor(BaseAssessor):
    """
    Assessor for annotation consistency.
    
    Detects inconsistencies in annotations, such as:
    - Same task annotated differently by same annotator
    - Conflicting labels for similar data
    """
    
    @property
    def name(self) -> str:
        return 'consistency'
    
    @property
    def description(self) -> str:
        return 'Assesses annotation consistency and detects inconsistencies'
    
    def assess(
        self,
        tasks: List[Dict[str, Any]],
        annotations: List[Dict[str, Any]],
        include_details: bool = True
    ) -> AssessmentResult:
        """
        Run consistency assessment.
        
        Args:
            tasks: List of task data
            annotations: List of annotation data
            include_details: Whether to include detailed statistics
        
        Returns:
            AssessmentResult with consistency score and issues
        """
        self.issues = []
        self.statistics = {}
        
        if not annotations:
            return AssessmentResult(
                assessor_name=self.name,
                score=1.0,
                statistics={'message': 'No annotations to assess'},
                issues=[],
            )
        
        # Group annotations by task
        task_annotations = defaultdict(list)
        for ann in annotations:
            task_annotations[ann['task_id']].append(ann)
        
        # Check for inconsistencies
        inconsistent_tasks = []
        total_tasks = len(task_annotations)
        
        for task_id, task_anns in task_annotations.items():
            if len(task_anns) < 2:
                continue
            
            # Extract labels from each annotation
            labels = [self.extract_label(ann) for ann in task_anns]
            unique_labels = set(labels)
            
            # If multiple different labels, it's inconsistent
            if len(unique_labels) > 1:
                inconsistent_tasks.append({
                    'task_id': task_id,
                    'labels': labels,
                    'unique_labels': list(unique_labels),
                    'annotation_count': len(task_anns),
                })
                
                self.add_issue(
                    issue_type='inconsistency',
                    severity='high' if len(unique_labels) > 2 else 'medium',
                    title=f'Inconsistent annotations for task {task_id}',
                    description=f'Task has {len(unique_labels)} different labels: {", ".join(unique_labels)}',
                    task_id=task_id,
                    details={
                        'labels': labels,
                        'unique_labels': list(unique_labels),
                    }
                )
        
        # Compute consistency score
        if total_tasks > 0:
            consistency_rate = 1.0 - (len(inconsistent_tasks) / total_tasks)
        else:
            consistency_rate = 1.0
        
        self.statistics = {
            'total_tasks_with_multiple_annotations': total_tasks,
            'inconsistent_tasks': len(inconsistent_tasks),
            'consistency_rate': consistency_rate,
        }
        
        if include_details:
            self.statistics['inconsistency_details'] = inconsistent_tasks[:20]
        
        return AssessmentResult(
            assessor_name=self.name,
            score=consistency_rate,
            statistics=self.statistics,
            issues=self.issues,
        )
