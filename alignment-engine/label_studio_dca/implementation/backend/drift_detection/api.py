"""
Drift Detection API interfaces.
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

import numpy as np

from backend.drift_detection.models import (
    DriftBaseline,
    DriftReport,
    DriftAlert,
    DriftMonitorConfig,
    DriftLevel,
    AlertType,
    AlertStatus,
)
from backend.drift_detection.detectors import (
    FeatureDriftDetector,
    LabelDriftDetector,
)

logger = logging.getLogger(__name__)


class DriftDetectionAPI:
    """
    API interface for Drift Detection module.
    """
    
    def __init__(self):
        """Initialize API."""
        self.baselines: Dict[int, DriftBaseline] = {}
        self.reports: Dict[int, DriftReport] = {}
        self.alerts: Dict[int, DriftAlert] = {}
        self.configs: Dict[int, DriftMonitorConfig] = {}
        self._next_baseline_id = 1
        self._next_report_id = 1
        self._next_alert_id = 1
    
    def create_baseline(
        self,
        project_id: int,
        name: str,
        tasks: List[Dict[str, Any]],
        annotations: List[Dict[str, Any]],
        description: str = '',
        user_id: Optional[int] = None
    ) -> DriftBaseline:
        """
        Create a drift baseline.
        
        Args:
            project_id: Project ID
            name: Baseline name
            tasks: Task data for baseline
            annotations: Annotation data for baseline
            description: Baseline description
            user_id: User creating the baseline
        
        Returns:
            Created DriftBaseline
        """
        # Compute feature statistics
        feature_detector = FeatureDriftDetector()
        features = feature_detector.extract_features(tasks)
        
        feature_statistics = {}
        for feature_name, values in features.items():
            feature_statistics[feature_name] = {
                'mean': float(np.mean(values)),
                'std': float(np.std(values)),
                'min': float(np.min(values)),
                'max': float(np.max(values)),
            }
        
        # Compute label distribution
        label_detector = LabelDriftDetector()
        label_distribution = label_detector.extract_labels(annotations)
        
        baseline = DriftBaseline(
            id=self._next_baseline_id,
            project_id=project_id,
            name=name,
            description=description,
            feature_statistics=feature_statistics,
            label_distribution=label_distribution,
            sample_count=len(tasks),
            created_by=user_id,
        )
        
        self.baselines[baseline.id] = baseline
        self._next_baseline_id += 1
        
        logger.info(f'Created drift baseline {baseline.id} for project {project_id}')
        
        return baseline
    
    def get_baseline(self, baseline_id: int) -> Optional[DriftBaseline]:
        """Get baseline by ID."""
        return self.baselines.get(baseline_id)
    
    def list_baselines(self, project_id: Optional[int] = None) -> List[DriftBaseline]:
        """List baselines."""
        baselines = list(self.baselines.values())
        
        if project_id is not None:
            baselines = [b for b in baselines if b.project_id == project_id]
        
        return baselines
    
    def run_detection(
        self,
        project_id: int,
        baseline_id: int,
        current_tasks: List[Dict[str, Any]],
        current_annotations: List[Dict[str, Any]],
        window_hours: int = 24
    ) -> Optional[DriftReport]:
        """
        Run drift detection.
        
        Args:
            project_id: Project ID
            baseline_id: Baseline ID
            current_tasks: Current task data
            current_annotations: Current annotation data
            window_hours: Time window in hours
        
        Returns:
            DriftReport or None
        """
        baseline = self.baselines.get(baseline_id)
        if not baseline:
            logger.error(f'Baseline {baseline_id} not found')
            return None
        
        # Detect feature drift
        feature_detector = FeatureDriftDetector()
        
        # Create baseline tasks from statistics
        baseline_tasks = [
            {'data': {name: stats['mean'] for name, stats in baseline.feature_statistics.items()}}
        ]
        
        feature_results, feature_score, feature_level = feature_detector.detect(
            baseline_tasks, current_tasks
        )
        
        # Detect label drift
        label_detector = LabelDriftDetector()
        
        # Create baseline annotations from distribution
        baseline_annotations = [
            {'result': [{'value': {'choices': [label]}}]}
            for label, count in baseline.label_distribution.items()
            for _ in range(count)
        ]
        
        label_result = label_detector.detect(baseline_annotations, current_annotations)
        
        # Compute overall drift
        overall_score = (feature_score + label_result.drift_score) / 2
        
        # Determine drift level
        if overall_score > 0.7:
            drift_level = DriftLevel.CRITICAL
        elif overall_score > 0.5:
            drift_level = DriftLevel.HIGH
        elif overall_score > 0.3:
            drift_level = DriftLevel.MEDIUM
        elif overall_score > 0.1:
            drift_level = DriftLevel.LOW
        else:
            drift_level = DriftLevel.NONE
        
        # Create report
        now = datetime.now()
        report = DriftReport(
            id=self._next_report_id,
            project_id=project_id,
            baseline_id=baseline_id,
            drift_level=drift_level,
            feature_drift_score=feature_score,
            label_drift_score=label_result.drift_score,
            overall_drift_score=overall_score,
            details={
                'feature_drift': {k: v.details for k, v in feature_results.items()},
                'label_drift': label_result.details,
            },
            window_start=now - timedelta(hours=window_hours),
            window_end=now,
            task_count=len(current_tasks),
        )
        
        self.reports[report.id] = report
        self._next_report_id += 1
        
        # Create alert if needed
        if drift_level in (DriftLevel.HIGH, DriftLevel.CRITICAL):
            self.create_alert(
                project_id=project_id,
                report_id=report.id,
                alert_type=AlertType.FEATURE if feature_score > label_result.drift_score else AlertType.LABEL,
                message=f'Significant {drift_level.value} drift detected (score: {overall_score:.2f})',
            )
        
        logger.info(
            f'Drift detection completed for project {project_id}: '
            f'level={drift_level.value}, score={overall_score:.3f}'
        )
        
        return report
    
    def create_alert(
        self,
        project_id: int,
        report_id: Optional[int],
        alert_type: AlertType,
        message: str
    ) -> DriftAlert:
        """Create a drift alert."""
        alert = DriftAlert(
            id=self._next_alert_id,
            project_id=project_id,
            report_id=report_id,
            alert_type=alert_type,
            message=message,
        )
        
        self.alerts[alert.id] = alert
        self._next_alert_id += 1
        
        return alert
    
    def get_alerts(
        self,
        project_id: Optional[int] = None,
        status: Optional[str] = None
    ) -> List[DriftAlert]:
        """Get alerts."""
        alerts = list(self.alerts.values())
        
        if project_id is not None:
            alerts = [a for a in alerts if a.project_id == project_id]
        
        if status is not None:
            alerts = [a for a in alerts if a.status.value == status]
        
        return alerts
    
    def acknowledge_alert(self, alert_id: int, user_id: int) -> Optional[DriftAlert]:
        """Acknowledge an alert."""
        alert = self.alerts.get(alert_id)
        if alert:
            alert.acknowledge(user_id)
        return alert
    
    def resolve_alert(self, alert_id: int) -> Optional[DriftAlert]:
        """Resolve an alert."""
        alert = self.alerts.get(alert_id)
        if alert:
            alert.resolve()
        return alert
    
    def get_reports(self, project_id: Optional[int] = None) -> List[DriftReport]:
        """Get reports."""
        reports = list(self.reports.values())
        
        if project_id is not None:
            reports = [r for r in reports if r.project_id == project_id]
        
        return sorted(reports, key=lambda r: r.created_at, reverse=True)


# Global API instance
drift_detection_api = DriftDetectionAPI()
