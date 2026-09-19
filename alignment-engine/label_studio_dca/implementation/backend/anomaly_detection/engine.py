"""
Anomaly detection engine.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from backend.anomaly_detection.detectors import (
    BaseAnomalyDetector,
    IsolationForestDetector,
    LocalOutlierFactorDetector,
    StatisticalDetector,
)

logger = logging.getLogger(__name__)

# Registry of available detectors
DETECTOR_REGISTRY = {
    'isolation_forest': IsolationForestDetector,
    'lof': LocalOutlierFactorDetector,
    'statistical': StatisticalDetector,
}


class AnomalyDetectionEngine:
    """
    Engine for anomaly detection.
    
    Coordinates multiple detectors and generates consolidated results.
    """
    
    def __init__(self, project_id: int):
        """
        Initialize engine.
        
        Args:
            project_id: Project ID
        """
        self.project_id = project_id
        self.results: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
    
    def get_detector(self, name: str, **kwargs) -> BaseAnomalyDetector:
        """
        Get detector instance by name.
        
        Args:
            name: Detector name
            **kwargs: Detector parameters
        
        Returns:
            Detector instance
        """
        if name not in DETECTOR_REGISTRY:
            raise ValueError(
                f"Unknown detector: {name}. "
                f"Available: {list(DETECTOR_REGISTRY.keys())}"
            )
        
        return DETECTOR_REGISTRY[name](**kwargs)
    
    def detect_anomalies(
        self,
        data: np.ndarray,
        detectors: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Detect anomalies using multiple detectors.
        
        Args:
            data: Input data (n_samples, n_features)
            detectors: List of detector names to use (None for all)
            **kwargs: Detector parameters
        
        Returns:
            Detection results
        """
        if detectors is None:
            detectors = list(DETECTOR_REGISTRY.keys())
        
        results = {}
        all_anomalies = np.zeros(len(data), dtype=bool)
        
        for detector_name in detectors:
            try:
                detector = self.get_detector(detector_name, **kwargs)
                scores, is_anomaly = detector.detect(data)
                
                results[detector_name] = {
                    'scores': scores.tolist(),
                    'is_anomaly': is_anomaly.tolist(),
                    'anomaly_count': int(np.sum(is_anomaly)),
                }
                
                all_anomalies |= is_anomaly
                
                logger.info(
                    f'Detector {detector_name}: '
                    f'{np.sum(is_anomaly)} anomalies found'
                )
            except Exception as e:
                logger.error(f'Error in detector {detector_name}: {str(e)}')
                results[detector_name] = {'error': str(e)}
        
        # Compute consensus
        consensus_anomalies = np.zeros(len(data), dtype=bool)
        for detector_name, result in results.items():
            if 'is_anomaly' in result:
                consensus_anomalies |= np.array(result['is_anomaly'])
        
        return {
            'project_id': self.project_id,
            'total_samples': len(data),
            'total_anomalies': int(np.sum(consensus_anomalies)),
            'anomaly_rate': float(np.sum(consensus_anomalies) / len(data)) if len(data) > 0 else 0,
            'detector_results': results,
            'consensus_anomalies': consensus_anomalies.tolist(),
        }
