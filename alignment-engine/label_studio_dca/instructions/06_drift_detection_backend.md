# 指令 06：漂移检测后端模块

## 目标

创建Data Drift Detection模块的后端架构，实现数据漂移检测、告警和监控功能。

## 需要创建的文件

1. `label_studio/drift_detection/__init__.py`
2. `label_studio/drift_detection/apps.py`
3. `label_studio/drift_detection/models.py`
4. `label_studio/drift_detection/api.py`
5. `label_studio/drift_detection/serializers.py`
6. `label_studio/drift_detection/urls.py`
7. `label_studio/drift_detection/detectors/__init__.py`
8. `label_studio/drift_detection/detectors/base.py`
9. `label_studio/drift_detection/detectors/feature_drift.py`
10. `label_studio/drift_detection/detectors/label_drift.py`
11. `label_studio/drift_detection/detectors/statistical.py`
12. `label_studio/drift_detection/alerts/__init__.py`
13. `label_studio/drift_detection/alerts/alert_manager.py`

## 详细实现

### 6.1 核心模型 (`models.py`)

```python
# label_studio/drift_detection/models.py
"""Drift Detection models."""

import logging
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


class DriftLevel(models.TextChoices):
    """Drift severity levels."""
    NONE = 'none', _('No Drift')
    LOW = 'low', _('Low Drift')
    MEDIUM = 'medium', _('Medium Drift')
    HIGH = 'high', _('High Drift')
    CRITICAL = 'critical', _('Critical Drift')


class AlertStatus(models.TextChoices):
    """Alert status choices."""
    ACTIVE = 'active', _('Active')
    ACKNOWLEDGED = 'acknowledged', _('Acknowledged')
    RESOLVED = 'resolved', _('Resolved')


class DriftBaseline(models.Model):
    """Baseline for drift detection."""
    
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='drift_baselines'
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Baseline statistics
    feature_statistics = models.JSONField(
        default=dict,
        help_text='Feature distribution statistics'
    )
    label_distribution = models.JSONField(
        default=dict,
        help_text='Label distribution statistics'
    )
    
    # Sample information
    sample_count = models.IntegerField(default=0)
    sample_start_date = models.DateTimeField(null=True)
    sample_end_date = models.DateTimeField(null=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    
    class Meta:
        db_table = 'drift_baseline'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'Baseline: {self.name} for {self.project.title}'


class DriftReport(models.Model):
    """Drift detection report."""
    
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='drift_reports'
    )
    baseline = models.ForeignKey(
        DriftBaseline,
        on_delete=models.CASCADE,
        related_name='reports'
    )
    
    # Drift level
    drift_level = models.CharField(
        max_length=10,
        choices=DriftLevel.choices,
        default=DriftLevel.NONE
    )
    
    # Drift scores
    feature_drift_score = models.FloatField(
        null=True,
        help_text='Feature drift score (0-1)'
    )
    label_drift_score = models.FloatField(
        null=True,
        help_text='Label drift score (0-1)'
    )
    overall_drift_score = models.FloatField(
        default=0.0,
        help_text='Overall drift score'
    )
    
    # Detection details
    details = models.JSONField(
        default=dict,
        help_text='Detailed detection results'
    )
    
    # Window information
    window_start = models.DateTimeField()
    window_end = models.DateTimeField()
    task_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'drift_report'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'Drift Report {self.id}: {self.drift_level}'


class DriftAlert(models.Model):
    """Drift alert."""
    
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='drift_alerts'
    )
    report = models.ForeignKey(
        DriftReport,
        on_delete=models.CASCADE,
        related_name='alerts',
        null=True, blank=True
    )
    
    alert_type = models.CharField(max_length=50)
    status = models.CharField(
        max_length=15,
        choices=AlertStatus.choices,
        default=AlertStatus.ACTIVE
    )
    
    message = models.TextField()
    details = models.JSONField(default=dict)
    
    notified_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='drift_alerts',
        blank=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acknowledged_alerts'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'drift_alert'
        ordering = ['-created_at']
    
    def acknowledge(self, user):
        from django.utils.timezone import now
        self.status = AlertStatus.ACKNOWLEDGED
        self.acknowledged_at = now()
        self.acknowledged_by = user
        self.save()
    
    def resolve(self):
        from django.utils.timezone import now
        self.status = AlertStatus.RESOLVED
        self.resolved_at = now()
        self.save()


class DriftMonitorConfig(models.Model):
    """Configuration for drift monitoring."""
    
    project = models.OneToOneField(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='drift_monitor_config'
    )
    
    # Monitoring settings
    is_enabled = models.BooleanField(default=False)
    check_interval_hours = models.IntegerField(
        default=24,
        help_text='How often to check for drift (hours)'
    )
    
    # Thresholds
    feature_drift_threshold = models.FloatField(
        default=0.3,
        help_text='Threshold for feature drift detection'
    )
    label_drift_threshold = models.FloatField(
        default=0.3,
        help_text='Threshold for label drift detection'
    )
    
    # Alert settings
    alert_on_drift = models.BooleanField(default=True)
    notify_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='drift_notifications',
        blank=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'drift_monitor_config'
```

### 6.2 检测器实现

#### `detectors/base.py`

```python
# label_studio/drift_detection/detectors/base.py
"""Base class for drift detectors."""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import numpy as np

logger = logging.getLogger(__name__)


class DriftDetectionResult:
    """Result of drift detection."""
    
    def __init__(
        self,
        has_drift: bool,
        drift_score: float,
        p_value: Optional[float] = None,
        statistic: Optional[float] = None,
        details: Optional[Dict] = None
    ):
        self.has_drift = has_drift
        self.drift_score = drift_score  # 0-1, higher = more drift
        self.p_value = p_value
        self.statistic = statistic
        self.details = details or {}


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
    
    def _compute_drift_score(self, p_value: float) -> float:
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
```

#### `detectors/statistical.py`

```python
# label_studio/drift_detection/detectors/statistical.py
"""Statistical tests for drift detection."""

import logging
import numpy as np
from scipy import stats
from typing import Optional
from .base import BaseDriftDetector, DriftDetectionResult

logger = logging.getLogger(__name__)


class KSTestDetector(BaseDriftDetector):
    """Kolmogorov-Smirnov test for continuous features."""
    
    def detect(
        self,
        baseline_data: np.ndarray,
        current_data: np.ndarray,
        **kwargs
    ) -> DriftDetectionResult:
        """
        Detect drift using KS test.
        
        Args:
            baseline_data: Baseline values
            current_data: Current values
        
        Returns:
            DriftDetectionResult
        """
        if len(baseline_data) == 0 or len(current_data) == 0:
            return DriftDetectionResult(
                has_drift=False,
                drift_score=0.0,
                details={'message': 'Insufficient data'}
            )
        
        # Perform KS test
        statistic, p_value = stats.ks_2samp(baseline_data, current_data)
        
        has_drift = p_value < self.threshold
        drift_score = self._compute_drift_score(p_value)
        
        return DriftDetectionResult(
            has_drift=has_drift,
            drift_score=drift_score,
            p_value=float(p_value),
            statistic=float(statistic),
            details={
                'test': 'kolmogorov_smirnov',
                'baseline_size': len(baseline_data),
                'current_size': len(current_data),
            }
        )


class ChiSquareDetector(BaseDriftDetector):
    """Chi-square test for categorical features."""
    
    def detect(
        self,
        baseline_data: np.ndarray,
        current_data: np.ndarray,
        **kwargs
    ) -> DriftDetectionResult:
        """
        Detect drift using chi-square test.
        
        Args:
            baseline_data: Baseline category counts
            current_data: Current category counts
        
        Returns:
            DriftDetectionResult
        """
        # Get all unique categories
        all_categories = set(baseline_data) | set(current_data)
        
        if not all_categories:
            return DriftDetectionResult(
                has_drift=False,
                drift_score=0.0,
                details={'message': 'No categories found'}
            )
        
        # Create contingency table
        baseline_counts = {cat: np.sum(baseline_data == cat) for cat in all_categories}
        current_counts = {cat: np.sum(current_data == cat) for cat in all_categories}
        
        observed = np.array([current_counts.get(cat, 0) for cat in all_categories])
        expected = np.array([baseline_counts.get(cat, 0) for cat in all_categories])
        
        # Normalize expected to match observed total
        expected = expected * (observed.sum() / expected.sum()) if expected.sum() > 0 else expected
        
        # Perform chi-square test
        try:
            statistic, p_value = stats.chisquare(observed, expected)
        except Exception as e:
            logger.error(f'Chi-square test failed: {str(e)}')
            return DriftDetectionResult(
                has_drift=False,
                drift_score=0.0,
                details={'error': str(e)}
            )
        
        has_drift = p_value < self.threshold
        drift_score = self._compute_drift_score(p_value)
        
        return DriftDetectionResult(
            has_drift=has_drift,
            drift_score=drift_score,
            p_value=float(p_value),
            statistic=float(statistic),
            details={
                'test': 'chi_square',
                'categories': list(all_categories),
                'baseline_counts': baseline_counts,
                'current_counts': current_counts,
            }
        )


class WassersteinDetector(BaseDriftDetector):
    """Wasserstein distance for distribution drift."""
    
    def detect(
        self,
        baseline_data: np.ndarray,
        current_data: np.ndarray,
        **kwargs
    ) -> DriftDetectionResult:
        """
        Detect drift using Wasserstein distance.
        
        Args:
            baseline_data: Baseline values
            current_data: Current values
        
        Returns:
            DriftDetectionResult
        """
        if len(baseline_data) == 0 or len(current_data) == 0:
            return DriftDetectionResult(
                has_drift=False,
                drift_score=0.0,
                details={'message': 'Insufficient data'}
            )
        
        # Compute Wasserstein distance
        distance = stats.wasserstein_distance(baseline_data, current_data)
        
        # Normalize by data range
        data_range = max(baseline_data.max() - baseline_data.min(), 1e-10)
        normalized_distance = distance / data_range
        
        # Determine drift based on threshold
        has_drift = normalized_distance > self.threshold
        drift_score = min(1.0, normalized_distance)
        
        return DriftDetectionResult(
            has_drift=has_drift,
            drift_score=drift_score,
            statistic=float(distance),
            details={
                'test': 'wasserstein',
                'distance': float(distance),
                'normalized_distance': float(normalized_distance),
            }
        )
```

#### `detectors/feature_drift.py`

```python
# label_studio/drift_detection/detectors/feature_drift.py
"""Feature drift detector."""

import logging
import numpy as np
from typing import Dict, List, Any, Optional
from collections import defaultdict

from .base import BaseDriftDetector, DriftDetectionResult
from .statistical import KSTestDetector, ChiSquareDetector, WassersteinDetector

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
        elif method == 'chi_square':
            self.detector = ChiSquareDetector(threshold)
        elif method == 'wasserstein':
            self.detector = WassersteinDetector(threshold)
        else:
            raise ValueError(f"Unknown method: {method}")
    
    def extract_features(self, tasks: List[Dict]) -> Dict[str, np.ndarray]:
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
        baseline_tasks: List[Dict],
        current_tasks: List[Dict]
    ) -> Dict[str, DriftDetectionResult]:
        """
        Detect feature drift.
        
        Args:
            baseline_tasks: Baseline task data
            current_tasks: Current task data
        
        Returns:
            Dictionary mapping feature name to detection result
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
        
        return results
    
    def compute_overall_drift(
        self,
        results: Dict[str, DriftDetectionResult]
    ) -> tuple:
        """
        Compute overall drift score and level.
        
        Args:
            results: Dictionary of feature drift results
        
        Returns:
            Tuple of (drift_score, drift_level)
        """
        if not results:
            return 0.0, 'none'
        
        scores = [r.drift_score for r in results.values()]
        avg_score = np.mean(scores)
        
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
        
        return float(avg_score), level
```

#### `detectors/label_drift.py`

```python
# label_studio/drift_detection/detectors/label_drift.py
"""Label drift detector."""

import logging
import numpy as np
from typing import Dict, List, Any, Optional
from collections import Counter

from .base import BaseDriftDetector, DriftDetectionResult
from .statistical import ChiSquareDetector

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
    
    def extract_labels(self, annotations: List[Dict]) -> Dict[str, int]:
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
        baseline_annotations: List[Dict],
        current_annotations: List[Dict]
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
```

### 6.3 告警管理器 (`alerts/alert_manager.py`)

```python
# label_studio/drift_detection/alerts/alert_manager.py
"""Alert manager for drift detection."""

import logging
from typing import List, Optional
from django.utils.timezone import now

from drift_detection.models import DriftAlert, DriftReport, DriftMonitorConfig

logger = logging.getLogger(__name__)


class AlertManager:
    """Manager for drift alerts."""
    
    def __init__(self, project):
        """
        Initialize alert manager.
        
        Args:
            project: Project instance
        """
        self.project = project
    
    def create_alert(
        self,
        report: DriftReport,
        alert_type: str,
        message: str,
        details: dict = None
    ) -> DriftAlert:
        """
        Create a drift alert.
        
        Args:
            report: Drift report
            alert_type: Type of alert
            message: Alert message
            details: Additional details
        
        Returns:
            DriftAlert instance
        """
        alert = DriftAlert.objects.create(
            project=self.project,
            report=report,
            alert_type=alert_type,
            message=message,
            details=details or {},
        )
        
        # Notify configured users
        config = DriftMonitorConfig.objects.filter(project=self.project).first()
        if config and config.alert_on_drift:
            users = config.notify_users.all()
            alert.notified_users.set(users)
            
            # TODO: Send email/notification
            logger.info(f'Created drift alert for project {self.project.title}: {message}')
        
        return alert
    
    def get_active_alerts(self) -> List[DriftAlert]:
        """Get active alerts."""
        return list(
            DriftAlert.objects.filter(
                project=self.project,
                status='active'
            ).order_by('-created_at')
        )
    
    def acknowledge_alert(self, alert_id: int, user) -> DriftAlert:
        """
        Acknowledge an alert.
        
        Args:
            alert_id: Alert ID
            user: User acknowledging
        
        Returns:
            Updated DriftAlert
        """
        alert = DriftAlert.objects.get(id=alert_id, project=self.project)
        alert.acknowledge(user)
        return alert
    
    def resolve_alert(self, alert_id: int) -> DriftAlert:
        """
        Resolve an alert.
        
        Args:
            alert_id: Alert ID
        
        Returns:
            Updated DriftAlert
        """
        alert = DriftAlert.objects.get(id=alert_id, project=self.project)
        alert.resolve()
        return alert
```

### 6.4 API实现 (`api.py`)

```python
# label_studio/drift_detection/api.py
"""Drift Detection API endpoints."""

import logging
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from core.permissions import ViewClassPermission, all_permissions
from drift_detection.models import (
    DriftBaseline,
    DriftReport,
    DriftAlert,
    DriftMonitorConfig,
)
from drift_detection.serializers import (
    DriftBaselineSerializer,
    DriftReportSerializer,
    DriftAlertSerializer,
    DriftMonitorConfigSerializer,
    DriftDetectionRequestSerializer,
)
from drift_detection.detectors.feature_drift import FeatureDriftDetector
from drift_detection.detectors.label_drift import LabelDriftDetector
from drift_detection.alerts.alert_manager import AlertManager
from projects.models import Project

logger = logging.getLogger(__name__)


class DriftBaselineListAPI(generics.ListCreateAPIView):
    """List and create drift baselines."""
    
    serializer_class = DriftBaselineSerializer
    permission_required = ViewClassPermission(
        GET=all_permissions.projects_view,
        POST=all_permissions.projects_change,
    )
    
    def get_queryset(self):
        project_id = self.request.query_params.get('project')
        if project_id:
            return DriftBaseline.objects.filter(project_id=project_id)
        return DriftBaseline.objects.none()
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class DriftBaselineDetailAPI(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, and delete drift baselines."""
    
    serializer_class = DriftBaselineSerializer
    permission_required = all_permissions.projects_change
    queryset = DriftBaseline.objects.all()


class DriftDetectionAPI(APIView):
    """Run drift detection."""
    
    permission_required = all_permissions.projects_change
    
    @extend_schema(
        tags=['Drift Detection'],
        summary='Run drift detection',
        description='Detect drift between baseline and current data.',
        request=DriftDetectionRequestSerializer,
    )
    def post(self, request, project_pk):
        """Run drift detection for a project."""
        project = get_object_or_404(Project, pk=project_pk)
        
        # Validate request
        serializer = DriftDetectionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        baseline_id = serializer.validated_data.get('baseline_id')
        window_hours = serializer.validated_data.get('window_hours', 24)
        
        # Get baseline
        baseline = get_object_or_404(DriftBaseline, pk=baseline_id, project=project)
        
        try:
            from tasks.models import Task, Annotation
            from django.utils.timezone import now, timedelta
            
            # Get current window tasks
            window_start = now() - timedelta(hours=window_hours)
            current_tasks = Task.objects.filter(
                project=project,
                created_at__gte=window_start
            )
            
            # Get baseline tasks
            baseline_tasks = Task.objects.filter(
                project=project,
                created_at__gte=baseline.sample_start_date,
                created_at__lte=baseline.sample_end_date
            ) if baseline.sample_start_date else Task.objects.filter(project=project)[:baseline.sample_count]
            
            # Detect feature drift
            feature_detector = FeatureDriftDetector(
                threshold=0.05,
                method='ks_test'
            )
            
            baseline_task_data = [
                {'data': t.data} for t in baseline_tasks
            ]
            current_task_data = [
                {'data': t.data} for t in current_tasks
            ]
            
            feature_results = feature_detector.detect(baseline_task_data, current_task_data)
            feature_score, feature_level = feature_detector.compute_overall_drift(feature_results)
            
            # Detect label drift
            label_detector = LabelDriftDetector(threshold=0.05)
            
            baseline_annotations = list(Annotation.objects.filter(
                task__in=baseline_tasks,
                was_cancelled=False
            ).values('result'))
            
            current_annotations = list(Annotation.objects.filter(
                task__in=current_tasks,
                was_cancelled=False
            ).values('result'))
            
            label_result = label_detector.detect(baseline_annotations, current_annotations)
            
            # Compute overall drift
            overall_score = (feature_score + label_result.drift_score) / 2
            drift_level = 'none'
            if overall_score > 0.7:
                drift_level = 'critical'
            elif overall_score > 0.5:
                drift_level = 'high'
            elif overall_score > 0.3:
                drift_level = 'medium'
            elif overall_score > 0.1:
                drift_level = 'low'
            
            # Create report
            report = DriftReport.objects.create(
                project=project,
                baseline=baseline,
                drift_level=drift_level,
                feature_drift_score=feature_score,
                label_drift_score=label_result.drift_score,
                overall_drift_score=overall_score,
                details={
                    'feature_drift': {k: v.details for k, v in feature_results.items()},
                    'label_drift': label_result.details,
                },
                window_start=window_start,
                window_end=now(),
                task_count=current_tasks.count(),
            )
            
            # Create alerts if needed
            alert_manager = AlertManager(project)
            if drift_level in ('high', 'critical'):
                alert_manager.create_alert(
                    report=report,
                    alert_type='feature' if feature_score > label_result.drift_score else 'label',
                    message=f'Significant {drift_level} drift detected (score: {overall_score:.2f})',
                    details={'drift_level': drift_level, 'overall_score': overall_score}
                )
            
            return Response(
                DriftReportSerializer(report).data,
                status=status.HTTP_200_OK
            )
        
        except Exception as e:
            logger.error(f'Error detecting drift: {str(e)}', exc_info=True)
            return Response(
                {'error': f'Failed to detect drift: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DriftReportListAPI(generics.ListAPIView):
    """List drift reports."""
    
    serializer_class = DriftReportSerializer
    permission_required = all_permissions.projects_view
    
    def get_queryset(self):
        project_id = self.kwargs.get('project_pk')
        return DriftReport.objects.filter(project_id=project_id)


class DriftAlertListAPI(generics.ListAPIView):
    """List drift alerts."""
    
    serializer_class = DriftAlertSerializer
    permission_required = all_permissions.projects_view
    
    def get_queryset(self):
        project_id = self.kwargs.get('project_pk')
        return DriftAlert.objects.filter(project_id=project_id)


@api_view(['POST'])
@permission_classes([all_permissions.projects_change])
def acknowledge_alert(request, pk):
    """Acknowledge a drift alert."""
    alert = get_object_or_404(DriftAlert, pk=pk)
    alert.acknowledge(request.user)
    return Response(DriftAlertSerializer(alert).data)


@api_view(['POST'])
@permission_classes([all_permissions.projects_change])
def resolve_alert(request, pk):
    """Resolve a drift alert."""
    alert = get_object_or_404(DriftAlert, pk=pk)
    alert.resolve()
    return Response(DriftAlertSerializer(alert).data)
```

### 6.5 序列化器 (`serializers.py`)

```python
# label_studio/drift_detection/serializers.py
"""Serializers for Drift Detection API."""

from rest_framework import serializers
from drift_detection.models import (
    DriftBaseline,
    DriftReport,
    DriftAlert,
    DriftMonitorConfig,
)


class DriftBaselineSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriftBaseline
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'created_by']


class DriftReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriftReport
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class DriftAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriftAlert
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class DriftMonitorConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriftMonitorConfig
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class DriftDetectionRequestSerializer(serializers.Serializer):
    baseline_id = serializers.IntegerField(required=True)
    window_hours = serializers.IntegerField(required=False, default=24)
```

### 6.6 URL配置 (`urls.py`)

```python
# label_studio/drift_detection/urls.py
"""URL configuration for Drift Detection API."""

from django.urls import path
from drift_detection import api

app_name = 'drift_detection'

urlpatterns = [
    path(
        'api/drift/baselines/',
        api.DriftBaselineListAPI.as_view(),
        name='baseline-list'
    ),
    path(
        'api/drift/baselines/<int:pk>/',
        api.DriftBaselineDetailAPI.as_view(),
        name='baseline-detail'
    ),
    path(
        'api/drift/projects/<int:project_pk>/detect/',
        api.DriftDetectionAPI.as_view(),
        name='detect'
    ),
    path(
        'api/drift/projects/<int:project_pk>/reports/',
        api.DriftReportListAPI.as_view(),
        name='report-list'
    ),
    path(
        'api/drift/projects/<int:project_pk>/alerts/',
        api.DriftAlertListAPI.as_view(),
        name='alert-list'
    ),
    path(
        'api/drift/alerts/<int:pk>/acknowledge/',
        api.acknowledge_alert,
        name='alert-acknowledge'
    ),
    path(
        'api/drift/alerts/<int:pk>/resolve/',
        api.resolve_alert,
        name='alert-resolve'
    ),
]
```

## 验证检查点

- [ ] 所有漂移检测模型创建成功
- [ ] 统计检验检测器正常工作
- [ ] 特征漂移检测器正常工作
- [ ] 标签漂移检测器正常工作
- [ ] 告警管理器正常工作
- [ ] API端点可访问

## 下一步

执行 `07_frontend_base.md` 创建前端基础架构。
