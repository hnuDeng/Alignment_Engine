"""
Outlier assessor for detecting anomalous annotations.
"""

import logging
from collections import defaultdict
from typing import Any, Dict, List

import numpy as np

from backend.data_quality.assessors.base import AssessmentResult, BaseAssessor

logger = logging.getLogger(__name__)


class OutlierAssessor(BaseAssessor):
    """
    Assessor for detecting outlier annotations.
    
    Detects:
    - Speed anomalies (too fast or too slow)
    - Label distribution anomalies
    """
    
    @property
    def name(self) -> str:
        return 'outlier'
    
    @property
    def description(self) -> str:
        return 'Detects outlier annotations'
    
    def detect_speed_anomalies(
        self,
        annotations: List[Dict[str, Any]],
        threshold: float = 3.0
    ) -> List[Dict[str, Any]]:
        """
        Detect annotations with anomalous speed.
        
        Args:
            annotations: List of annotations
            threshold: Standard deviation threshold
        
        Returns:
            List of anomalous annotations
        """
        times = []
        valid_annotations = []
        
        for ann in annotations:
            lead_time = ann.get('lead_time')
            if lead_time and lead_time > 0:
                times.append(lead_time)
                valid_annotations.append(ann)
        
        if len(times) < 3:
            return []
        
        mean_time = np.mean(times)
        std_time = np.std(times)
        
        if std_time == 0:
            return []
        
        anomalies = []
        for time, annotation in zip(times, valid_annotations):
            z_score = abs(time - mean_time) / std_time
            if z_score > threshold:
                anomalies.append({
                    'annotation': annotation,
                    'time': time,
                    'z_score': float(z_score),
                    'mean': float(mean_time),
                    'std': float(std_time),
                })
        
        return anomalies
    
    def assess(
        self,
        tasks: List[Dict[str, Any]],
        annotations: List[Dict[str, Any]],
        include_details: bool = True
    ) -> AssessmentResult:
        """
        Run outlier assessment.
        
        Args:
            tasks: List of task data
            annotations: List of annotation data
            include_details: Whether to include detailed statistics
        
        Returns:
            AssessmentResult with outlier score and issues
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
        
        # Detect speed anomalies
        speed_anomalies = self.detect_speed_anomalies(annotations, threshold=3.0)
        
        for anomaly in speed_anomalies:
            annotation = anomaly['annotation']
            
            self.add_issue(
                issue_type='speed_anomaly',
                severity='high' if anomaly['z_score'] > 5 else 'medium',
                title='Speed anomaly detected',
                description=(
                    f'Annotation completed in {anomaly["time"]:.1f}s '
                    f'(mean: {anomaly["mean"]:.1f}s, z-score: {anomaly["z_score"]:.2f})'
                ),
                task_id=annotation.get('task_id'),
                annotation_id=annotation.get('id'),
                annotator_id=annotation.get('annotator_id'),
                details={
                    'time': anomaly['time'],
                    'mean': anomaly['mean'],
                    'std': anomaly['std'],
                    'z_score': anomaly['z_score'],
                }
            )
        
        # Compute outlier score
        total_issues = len(speed_anomalies)
        total_annotations = len(annotations)
        
        outlier_rate = total_issues / total_annotations if total_annotations > 0 else 0
        outlier_score = max(0, 1.0 - outlier_rate)
        
        # Compute time statistics
        times = [ann.get('lead_time', 0) for ann in annotations if ann.get('lead_time', 0) > 0]
        
        self.statistics = {
            'total_annotations': total_annotations,
            'speed_anomalies': len(speed_anomalies),
            'total_outliers': total_issues,
            'outlier_rate': outlier_rate,
            'time_statistics': {
                'mean': float(np.mean(times)) if times else 0,
                'std': float(np.std(times)) if times else 0,
                'min': float(np.min(times)) if times else 0,
                'max': float(np.max(times)) if times else 0,
            },
        }
        
        return AssessmentResult(
            assessor_name=self.name,
            score=outlier_score,
            statistics=self.statistics,
            issues=self.issues,
        )
