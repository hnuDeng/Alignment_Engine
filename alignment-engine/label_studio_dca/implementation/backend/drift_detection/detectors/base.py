"""
Base class for drift detectors.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import numpy as np

from backend.drift_detection.models import DriftDetectionResult

logger = logging.getLogger(__name__)


class BaseDriftDetector(ABC):
    """Base class for drift detectors."""
    
    def __init__(self, threshold: float = 0.05):
        """
        Initialize detector.
        
        Args:
            threshold: Significance threshold for drift detection
        """
        self.threshold = threshold
    
    @abstractmethod
    def detect(
        self,
        baseline_data: np.ndarray,
        current_data: np.ndarray,
        **kwargs
    ) -> DriftDetectionResult:
        """
        Detect drift between baseline and current data.
        
        Args:
            baseline_data: Baseline data distribution
            current_data: Current data distribution
        
        Returns:
            DriftDetectionResult
        """
        raise NotImplementedError
    
    def _compute_drift_score(self, p_value: Optional[float]) -> float:
        """
        Convert p-value to drift score.
        
        Args:
            p_value: Statistical p-value
        
        Returns:
            Drift score (0-1)
        """
        if p_value is None:
            return 0.5
        # Lower p-value = more drift
        return max(0, 1.0 - p_value)
