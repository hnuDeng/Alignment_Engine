"""
Bias assessor for detecting annotation biases.
"""

import logging
from collections import defaultdict
from typing import Any, Dict, List

import numpy as np

from backend.data_quality.assessors.base import AssessmentResult, BaseAssessor

logger = logging.getLogger(__name__)


class BiasAssessor(BaseAssessor):
    """
    Assessor for detecting annotation biases.
    
    Detects:
    - Label imbalance
    - Annotator bias towards specific labels
    """
    
    @property
    def name(self) -> str:
        return 'bias'
    
    @property
    def description(self) -> str:
        return 'Detects annotation biases'
    
    def assess(
        self,
        tasks: List[Dict[str, Any]],
        annotations: List[Dict[str, Any]],
        include_details: bool = True
    ) -> AssessmentResult:
        """
        Run bias assessment.
        
        Args:
            tasks: List of task data
            annotations: List of annotation data
            include_details: Whether to include detailed statistics
        
        Returns:
            AssessmentResult with bias score and issues
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
        
        # Compute label distribution
        label_dist = defaultdict(int)
        annotator_labels = defaultdict(list)
        
        for ann in annotations:
            label = self.extract_label(ann)
            label_dist[label] += 1
            annotator_labels[ann['annotator_id']].append(label)
        
        total_annotations = len(annotations)
        
        # Check for severe imbalance
        imbalance_ratio = 1.0
        if label_dist:
            max_count = max(label_dist.values())
            min_count = min(label_dist.values())
            
            imbalance_ratio = max_count / min_count if min_count > 0 else float('inf')
            
            if imbalance_ratio > 10:
                dominant_label = max(label_dist.items(), key=lambda x: x[1])[0]
                
                self.add_issue(
                    issue_type='bias',
                    severity='high' if imbalance_ratio > 50 else 'medium',
                    title='Severe label imbalance detected',
                    description=(
                        f'Label "{dominant_label}" appears {imbalance_ratio:.1f}x '
                        f'more often than the least common label'
                    ),
                    details={
                        'imbalance_ratio': imbalance_ratio,
                        'label_distribution': dict(label_dist),
                        'dominant_label': dominant_label,
                    }
                )
        
        # Check for annotator bias
        biased_annotators = []
        for annotator_id, labels in annotator_labels.items():
            annotator_dist = defaultdict(int)
            for label in labels:
                annotator_dist[label] += 1
            
            # Check if annotator has extreme preference
            if annotator_dist:
                max_label = max(annotator_dist.items(), key=lambda x: x[1])
                max_pct = max_label[1] / len(labels)
                
                if max_pct > 0.9 and len(labels) > 10:
                    biased_annotators.append({
                        'annotator_id': annotator_id,
                        'preferred_label': max_label[0],
                        'percentage': max_pct,
                        'total_annotations': len(labels),
                    })
                    
                    self.add_issue(
                        issue_type='bias',
                        severity='medium',
                        title=f'Annotator {annotator_id} shows label bias',
                        description=(
                            f'Annotator uses label "{max_label[0]}" for '
                            f'{max_pct:.1%} of annotations'
                        ),
                        annotator_id=annotator_id,
                        details={
                            'preferred_label': max_label[0],
                            'percentage': max_pct,
                            'distribution': dict(annotator_dist),
                        }
                    )
        
        # Compute bias score
        bias_issues = len(biased_annotators)
        if imbalance_ratio > 10:
            bias_issues += 1
        
        bias_rate = bias_issues / (len(annotator_labels) + 1) if annotator_labels else 0
        bias_score = max(0, 1.0 - bias_rate)
        
        self.statistics = {
            'total_annotations': total_annotations,
            'unique_labels': len(label_dist),
            'label_distribution': dict(label_dist),
            'imbalance_ratio': imbalance_ratio if label_dist else 1.0,
            'biased_annotators': len(biased_annotators),
            'annotator_count': len(annotator_labels),
        }
        
        if include_details:
            self.statistics['biased_annotator_details'] = biased_annotators[:10]
        
        return AssessmentResult(
            assessor_name=self.name,
            score=bias_score,
            statistics=self.statistics,
            issues=self.issues,
        )
