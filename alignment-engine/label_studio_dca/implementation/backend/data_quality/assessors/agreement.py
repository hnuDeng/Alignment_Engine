"""
Agreement assessor for computing inter-annotator agreement.
"""

import logging
from collections import defaultdict
from itertools import combinations
from typing import Any, Dict, List

import numpy as np

from backend.data_quality.assessors.base import AssessmentResult, BaseAssessor

logger = logging.getLogger(__name__)


class AgreementAssessor(BaseAssessor):
    """
    Assessor for inter-annotator agreement.
    
    Computes agreement metrics including:
    - Pairwise agreement rates
    - Overall agreement score
    """
    
    @property
    def name(self) -> str:
        return 'agreement'
    
    @property
    def description(self) -> str:
        return 'Assesses inter-annotator agreement'
    
    def assess(
        self,
        tasks: List[Dict[str, Any]],
        annotations: List[Dict[str, Any]],
        include_details: bool = True
    ) -> AssessmentResult:
        """
        Run agreement assessment.
        
        Args:
            tasks: List of task data
            annotations: List of annotation data
            include_details: Whether to include detailed statistics
        
        Returns:
            AssessmentResult with agreement score and issues
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
        
        # Group by task and annotator
        task_annotator_labels = defaultdict(dict)
        for ann in annotations:
            label = self.extract_label(ann)
            task_annotator_labels[ann['task_id']][ann['annotator_id']] = label
        
        # Compute pairwise agreement
        annotator_pairs = defaultdict(list)
        
        for task_id, annotator_labels_dict in task_annotator_labels.items():
            annotators = list(annotator_labels_dict.keys())
            
            # Pairwise comparisons
            for a1, a2 in combinations(annotators, 2):
                label1 = annotator_labels_dict[a1]
                label2 = annotator_labels_dict[a2]
                
                agreement = 1.0 if label1 == label2 else 0.0
                annotator_pairs[(a1, a2)].append(agreement)
        
        # Compute agreement rates
        pair_agreements = {}
        for (a1, a2), agreements in annotator_pairs.items():
            pair_agreements[(a1, a2)] = {
                'agreement_rate': float(np.mean(agreements)),
                'task_count': len(agreements),
            }
        
        # Compute overall agreement
        all_agreement_rates = [v['agreement_rate'] for v in pair_agreements.values()]
        overall_agreement = float(np.mean(all_agreement_rates)) if all_agreement_rates else 1.0
        
        # Find low-agreement pairs
        low_agreement_pairs = []
        for (a1, a2), stats in pair_agreements.items():
            if stats['agreement_rate'] < 0.5:
                low_agreement_pairs.append({
                    'annotator1': a1,
                    'annotator2': a2,
                    'agreement_rate': stats['agreement_rate'],
                    'task_count': stats['task_count'],
                })
                
                self.add_issue(
                    issue_type='low_agreement',
                    severity='high' if stats['agreement_rate'] < 0.3 else 'medium',
                    title=f'Low agreement between annotators {a1} and {a2}',
                    description=f'Agreement rate: {stats["agreement_rate"]:.2%}',
                    details={
                        'annotator1': a1,
                        'annotator2': a2,
                        'agreement_rate': stats['agreement_rate'],
                        'task_count': stats['task_count'],
                    }
                )
        
        self.statistics = {
            'total_annotators': len(set(ann['annotator_id'] for ann in annotations)),
            'total_pairs': len(pair_agreements),
            'overall_agreement_rate': overall_agreement,
            'low_agreement_pairs': len(low_agreement_pairs),
        }
        
        if include_details:
            self.statistics['low_agreement_details'] = low_agreement_pairs[:10]
        
        return AssessmentResult(
            assessor_name=self.name,
            score=overall_agreement,
            statistics=self.statistics,
            issues=self.issues,
        )
