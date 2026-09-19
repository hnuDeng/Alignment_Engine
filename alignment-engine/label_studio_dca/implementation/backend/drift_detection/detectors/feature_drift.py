"""
Feature drift detector.
"""

import logging
from collections import defaultdict
from typing import Any, Dict, List, Tuple

import numpy as np

from backend.drift_detection.detectors.statistical import KSTestDetector
from backend.drift_detection.models import DriftDetectionResult

logger = logging.getLogger(__name__)


class FeatureDriftDetector:
    """
    Detector for feature drift.
    
    Analyzes changes in task data features over time.
    """
    
    def __init__(
        self,
        threshold: float = 0.05,
        method: str = 'ks_test'
    ):
        """
        Initialize feature drift detector.
        
        Args:
            threshold: Significance threshold
            method: Detection method ('ks_test', 'chi_square', 'wasserstein')
        """
        self.threshold = threshold
        self.method = method
        
        # Select detector based on method
        if method == 'ks_test':
            self.detector = KSTestDetector(threshold)
        else:
            self.detector = KSTestDetector(threshold)  # Default
    
    def extract_features(self, tasks: List[Dict[str, Any]]) -> Dict[str, np.ndarray]:
        """
        Extract features from tasks.
        
        Args:
            tasks: List of task data
        
        Returns:
            Dictionary mapping feature name to values
        """
        features = defaultdict(list)
        
        for task in tasks:
            data = task.get('data', {})
            for key, value in data.items():
                if isinstance(value, (int, float)):
                    features[key].append(value)
                elif isinstance(value, str):
                    # Use hash for string features
                    features[key].append(hash(value) % 1000)
        
        return {k: np.array(v) for k, v in features.items() if v}
    
    def detect(
        self,
        baseline_tasks: List[Dict[str, Any]],
        current_tasks: List[Dict[str, Any]]
    ) -> Tuple[Dict[str, DriftDetectionResult], float, str]:
        """
        Detect feature drift.
        
        Args:
            baseline_tasks: Baseline task data
            current_tasks: Current task data
        
        Returns:
            Tuple of (feature results, overall score, drift level)
        """
        baseline_features = self.extract_features(baseline_tasks)
        current_features = self.extract_features(current_tasks)
        
        results = {}
        all_features = set(baseline_features.keys()) | set(current_features.keys())
        
        for feature_name in all_features:
            baseline_data = baseline_features.get(feature_name, np.array([]))
            current_data = current_features.get(feature_name, np.array([]))
            
            if len(baseline_data) > 0 and len(current_data) > 0:
                result = self.detector.detect(baseline_data, current_data)
                results[feature_name] = result
        
        # Compute overall drift
        if results:
            scores = [r.drift_score for r in results.values()]
            avg_score = float(np.mean(scores))
        else:
            avg_score = 0.0
        
        # Determine drift level
        if avg_score < 0.1:
            level = 'none'
        elif avg_score < 0.3:
            level = 'low'
        elif avg_score < 0.5:
            level = 'medium'
        elif avg_score < 0.7:
            level = 'high'
        else:
            level = 'critical'
        
        return results, avg_score, level
