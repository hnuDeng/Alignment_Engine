"""
Label drift detector.
"""

import logging
from collections import Counter
from typing import Any, Dict, List

import numpy as np

from backend.drift_detection.detectors.statistical import ChiSquareDetector
from backend.drift_detection.models import DriftDetectionResult

logger = logging.getLogger(__name__)


class LabelDriftDetector:
    """
    Detector for label drift.
    
    Analyzes changes in annotation label distributions over time.
    """
    
    def __init__(self, threshold: float = 0.05):
        """
        Initialize label drift detector.
        
        Args:
            threshold: Significance threshold
        """
        self.threshold = threshold
        self.detector = ChiSquareDetector(threshold)
    
    def extract_labels(self, annotations: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Extract label distribution from annotations.
        
        Args:
            annotations: List of annotations
        
        Returns:
            Dictionary mapping label to count
        """
        label_counts = Counter()
        
        for ann in annotations:
            result = ann.get('result', [])
            for item in result:
                value = item.get('value', {})
                
                if 'choices' in value:
                    choices = value['choices']
                    if isinstance(choices, list):
                        for choice in choices:
                            label_counts[choice] += 1
                    elif isinstance(choices, dict):
                        for choice in choices:
                            label_counts[choice] += 1
                
                if 'labels' in value:
                    labels = value['labels']
                    if isinstance(labels, list):
                        for label in labels:
                            label_counts[label] += 1
        
        return dict(label_counts)
    
    def detect(
        self,
        baseline_annotations: List[Dict[str, Any]],
        current_annotations: List[Dict[str, Any]]
    ) -> DriftDetectionResult:
        """
        Detect label drift.
        
        Args:
            baseline_annotations: Baseline annotations
            current_annotations: Current annotations
        
        Returns:
            DriftDetectionResult
        """
        baseline_dist = self.extract_labels(baseline_annotations)
        current_dist = self.extract_labels(current_annotations)
        
        if not baseline_dist or not current_dist:
            return DriftDetectionResult(
                has_drift=False,
                drift_score=0.0,
                details={'message': 'Insufficient label data'}
            )
        
        # Get all labels
        all_labels = set(baseline_dist.keys()) | set(current_dist.keys())
        
        # Create arrays for chi-square test
        baseline_counts = np.array([baseline_dist.get(label, 0) for label in all_labels])
        current_counts = np.array([current_dist.get(label, 0) for label in all_labels])
        
        # Perform detection
        result = self.detector.detect(baseline_counts, current_counts)
        result.details.update({
            'baseline_distribution': baseline_dist,
            'current_distribution': current_dist,
            'labels': list(all_labels),
        })
        
        return result
