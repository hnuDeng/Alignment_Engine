# 指令 04：数据质量评估后端

## 目标

创建Data Quality模块的基础后端架构，包括模型、API和核心功能。

## 需要创建的文件

1. `label_studio/data_quality/__init__.py`
2. `label_studio/data_quality/apps.py`
3. `label_studio/data_quality/models.py`
4. `label_studio/data_quality/api.py`
5. `label_studio/data_quality/serializers.py`
6. `label_studio/data_quality/urls.py`
7. `label_studio/data_quality/managers.py`
8. `label_studio/data_quality/utils.py`
9. `label_studio/data_quality/migrations/__init__.py`

## 详细实现

### 4.1 创建 `__init__.py`

```python
# label_studio/data_quality/__init__.py
default_app_config = 'data_quality.apps.DataQualityConfig'
```

### 4.2 创建 `apps.py`

```python
# label_studio/data_quality/apps.py
from django.apps import AppConfig


class DataQualityConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'data_quality'
    verbose_name = 'Data Quality Assessment'
    
    def ready(self):
        import data_quality.signals  # noqa
```

### 4.3 创建 `models.py`

```python
# label_studio/data_quality/models.py
"""Data Quality assessment models."""

import logging
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


class QualityReportType(models.TextChoices):
    """Types of quality reports."""
    PROJECT = 'project', _('Project Quality')
    ANNOTATOR = 'annotator', _('Annotator Quality')
    TASK = 'task', _('Task Quality')
    LABEL = 'label', _('Label Quality')


class QualityIssueType(models.TextChoices):
    """Types of quality issues."""
    INCONSISTENCY = 'inconsistency', _('标注不一致')
    OUTLIER = 'outlier', _('异常标注')
    BIAS = 'bias', _('标注偏差')
    MISSING = 'missing', _('缺失标注')
    CONFLICT = 'conflict', _('标注冲突')
    LOW_AGREEMENT = 'low_agreement', _('低一致性')
    SPEED_ANOMALY = 'speed_anomaly', _('标注速度异常')


class SeverityLevel(models.TextChoices):
    """Severity levels for quality issues."""
    LOW = 'low', _('Low')
    MEDIUM = 'medium', _('Medium')
    HIGH = 'high', _('High')
    CRITICAL = 'critical', _('Critical')


class QualityReport(models.Model):
    """Data quality assessment report."""
    
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='quality_reports',
        help_text='Project this report belongs to'
    )
    
    report_type = models.CharField(
        max_length=20,
        choices=QualityReportType.choices,
        default=QualityReportType.PROJECT,
        help_text='Type of quality report'
    )
    
    # Overall quality scores (0-1)
    overall_score = models.FloatField(
        default=0.0,
        help_text='Overall quality score (0-1)'
    )
    
    consistency_score = models.FloatField(
        null=True,
        blank=True,
        help_text='Annotation consistency score'
    )
    
    agreement_score = models.FloatField(
        null=True,
        blank=True,
        help_text='Inter-annotator agreement score'
    )
    
    completeness_score = models.FloatField(
        null=True,
        blank=True,
        help_text='Annotation completeness score'
    )
    
    # Detailed statistics
    statistics = models.JSONField(
        default=dict,
        blank=True,
        help_text='Detailed statistics'
    )
    
    # Issues found
    issue_count = models.IntegerField(
        default=0,
        help_text='Number of issues found'
    )
    
    critical_issue_count = models.IntegerField(
        default=0,
        help_text='Number of critical issues'
    )
    
    # Metadata
    tasks_analyzed = models.IntegerField(
        default=0,
        help_text='Number of tasks analyzed'
    )
    
    annotations_analyzed = models.IntegerField(
        default=0,
        help_text='Number of annotations analyzed'
    )
    
    annotators_analyzed = models.IntegerField(
        default=0,
        help_text='Number of annotators analyzed'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quality_reports'
    )
    
    class Meta:
        db_table = 'data_quality_report'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['project', '-created_at']),
            models.Index(fields=['report_type', '-created_at']),
        ]
    
    def __str__(self):
        return f'Quality Report {self.id} for {self.project.title}'


class QualityIssue(models.Model):
    """Individual quality issue found during assessment."""
    
    report = models.ForeignKey(
        QualityReport,
        on_delete=models.CASCADE,
        related_name='issues',
        help_text='Report this issue belongs to'
    )
    
    issue_type = models.CharField(
        max_length=20,
        choices=QualityIssueType.choices,
        help_text='Type of quality issue'
    )
    
    severity = models.CharField(
        max_length=10,
        choices=SeverityLevel.choices,
        default=SeverityLevel.MEDIUM,
        help_text='Severity level'
    )
    
    # Related objects
    task = models.ForeignKey(
        'tasks.Task',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='quality_issues',
        help_text='Related task'
    )
    
    annotation = models.ForeignKey(
        'tasks.Annotation',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='quality_issues',
        help_text='Related annotation'
    )
    
    annotator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quality_issues',
        help_text='Related annotator'
    )
    
    # Issue details
    title = models.CharField(
        max_length=255,
        help_text='Short description of the issue'
    )
    
    description = models.TextField(
        help_text='Detailed description'
    )
    
    details = models.JSONField(
        default=dict,
        blank=True,
        help_text='Additional details'
    )
    
    # Resolution
    is_resolved = models.BooleanField(
        default=False,
        help_text='Whether the issue is resolved'
    )
    
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When the issue was resolved'
    )
    
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_quality_issues',
        help_text='User who resolved the issue'
    )
    
    resolution_notes = models.TextField(
        blank=True,
        help_text='Notes on resolution'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'data_quality_issue'
        ordering = ['-severity', '-created_at']
        indexes = [
            models.Index(fields=['report', 'severity']),
            models.Index(fields=['task', 'issue_type']),
            models.Index(fields=['annotator', 'issue_type']),
            models.Index(fields=['is_resolved', '-created_at']),
        ]
    
    def __str__(self):
        return f'{self.issue_type}: {self.title} ({self.severity})'
    
    def resolve(self, user, notes=''):
        """Mark issue as resolved."""
        from django.utils.timezone import now
        self.is_resolved = True
        self.resolved_at = now()
        self.resolved_by = user
        self.resolution_notes = notes
        self.save(update_fields=[
            'is_resolved', 'resolved_at', 'resolved_by', 'resolution_notes'
        ])


class AnnotatorQualityProfile(models.Model):
    """Quality profile for an annotator in a project."""
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='quality_profiles',
        help_text='Annotator user'
    )
    
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='annotator_profiles',
        help_text='Project'
    )
    
    # Quality metrics
    total_annotations = models.IntegerField(
        default=0,
        help_text='Total number of annotations'
    )
    
    agreement_rate = models.FloatField(
        default=0.0,
        help_text='Agreement rate with other annotators'
    )
    
    avg_annotation_time = models.FloatField(
        default=0.0,
        help_text='Average annotation time in seconds'
    )
    
    quality_score = models.FloatField(
        default=0.0,
        help_text='Overall quality score (0-1)'
    )
    
    consistency_score = models.FloatField(
        default=0.0,
        help_text='Annotation consistency score'
    )
    
    # Statistics
    issue_count = models.IntegerField(
        default=0,
        help_text='Number of quality issues'
    )
    
    critical_issue_count = models.IntegerField(
        default=0,
        help_text='Number of critical issues'
    )
    
    statistics = models.JSONField(
        default=dict,
        blank=True,
        help_text='Detailed statistics'
    )
    
    # Metadata
    first_annotation_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Time of first annotation'
    )
    
    last_annotation_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Time of last annotation'
    )
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'data_quality_annotator_profile'
        unique_together = ['user', 'project']
        indexes = [
            models.Index(fields=['project', 'quality_score']),
            models.Index(fields=['user', 'project']),
        ]
    
    def __str__(self):
        return f'Quality Profile: {self.user.username} in {self.project.title}'


class LabelQualityStats(models.Model):
    """Quality statistics for a specific label."""
    
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='label_quality_stats',
        help_text='Project'
    )
    
    label_name = models.CharField(
        max_length=255,
        help_text='Label name'
    )
    
    label_type = models.CharField(
        max_length=50,
        help_text='Label type (e.g., choices, labels)'
    )
    
    # Usage statistics
    usage_count = models.IntegerField(
        default=0,
        help_text='Number of times this label was used'
    )
    
    unique_annotators = models.IntegerField(
        default=0,
        help_text='Number of unique annotators using this label'
    )
    
    # Quality metrics
    agreement_rate = models.FloatField(
        default=0.0,
        help_text='Agreement rate for this label'
    )
    
    consistency_score = models.FloatField(
        default=0.0,
        help_text='Consistency score for this label'
    )
    
    # Distribution
    usage_percentage = models.FloatField(
        default=0.0,
        help_text='Percentage of total annotations using this label'
    )
    
    statistics = models.JSONField(
        default=dict,
        blank=True,
        help_text='Detailed statistics'
    )
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'data_quality_label_stats'
        unique_together = ['project', 'label_name', 'label_type']
        indexes = [
            models.Index(fields=['project', 'label_name']),
        ]
    
    def __str__(self):
        return f'Label Stats: {self.label_name} in {self.project.title}'


class QualityAssessmentConfig(models.Model):
    """Configuration for quality assessment."""
    
    project = models.OneToOneField(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='quality_config',
        help_text='Project this config belongs to'
    )
    
    # Assessment settings
    auto_assess = models.BooleanField(
        default=False,
        help_text='Automatically run assessment after annotations'
    )
    
    assess_after_count = models.IntegerField(
        default=100,
        help_text='Run assessment after this many new annotations'
    )
    
    # Issue detection thresholds
    low_agreement_threshold = models.FloatField(
        default=0.5,
        help_text='Threshold for low agreement issues'
    )
    
    speed_anomaly_threshold = models.FloatField(
        default=3.0,
        help_text='Standard deviations for speed anomaly detection'
    )
    
    outlier_detection_enabled = models.BooleanField(
        default=True,
        help_text='Enable outlier detection'
    )
    
    # Notification settings
    notify_on_critical = models.BooleanField(
        default=True,
        help_text='Notify on critical issues'
    )
    
    notify_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='quality_notifications',
        help_text='Users to notify'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'data_quality_config'
    
    def __str__(self):
        return f'Quality Config for {self.project.title}'
```

### 4.4 创建 `managers.py`

```python
# label_studio/data_quality/managers.py
"""Custom managers for Data Quality models."""

from django.db import models
from django.utils.timezone import now, timedelta


class QualityReportManager(models.Manager):
    """Manager for QualityReport."""
    
    def get_latest(self, project):
        """Get latest report for a project."""
        return self.filter(project=project).order_by('-created_at').first()
    
    def get_recent(self, project, days=30):
        """Get reports from last N days."""
        cutoff = now() - timedelta(days=days)
        return self.filter(
            project=project,
            created_at__gte=cutoff
        ).order_by('-created_at')
    
    def get_by_type(self, project, report_type):
        """Get reports by type."""
        return self.filter(
            project=project,
            report_type=report_type
        ).order_by('-created_at')


class QualityIssueManager(models.Manager):
    """Manager for QualityIssue."""
    
    def get_unresolved(self, project=None):
        """Get unresolved issues."""
        queryset = self.filter(is_resolved=False)
        if project:
            queryset = queryset.filter(report__project=project)
        return queryset.order_by('-severity', '-created_at')
    
    def get_critical(self, project=None):
        """Get critical issues."""
        queryset = self.filter(severity='critical', is_resolved=False)
        if project:
            queryset = queryset.filter(report__project=project)
        return queryset
    
    def get_by_task(self, task):
        """Get issues for a specific task."""
        return self.filter(task=task).order_by('-severity')
    
    def get_by_annotator(self, annotator, project=None):
        """Get issues for a specific annotator."""
        queryset = self.filter(annotator=annotator)
        if project:
            queryset = queryset.filter(report__project=project)
        return queryset.order_by('-created_at')
    
    def get_statistics(self, project):
        """Get issue statistics for a project."""
        from django.db.models import Count
        
        return self.filter(
            report__project=project
        ).values('issue_type', 'severity').annotate(
            count=Count('id')
        ).order_by('issue_type', 'severity')


class AnnotatorQualityProfileManager(models.Manager):
    """Manager for AnnotatorQualityProfile."""
    
    def get_top_annotators(self, project, limit=10):
        """Get top quality annotators."""
        return self.filter(
            project=project
        ).order_by('-quality_score')[:limit]
    
    def get_low_quality_annotators(self, project, threshold=0.5):
        """Get annotators with low quality scores."""
        return self.filter(
            project=project,
            quality_score__lt=threshold
        ).order_by('quality_score')
    
    def get_or_create_profile(self, user, project):
        """Get or create annotator profile."""
        profile, created = self.get_or_create(
            user=user,
            project=project,
            defaults={
                'quality_score': 0.0,
                'agreement_rate': 0.0,
            }
        )
        return profile, created


class LabelQualityStatsManager(models.Manager):
    """Manager for LabelQualityStats."""
    
    def get_by_project(self, project):
        """Get label stats for a project."""
        return self.filter(project=project).order_by('-usage_count')
    
    def get_low_agreement_labels(self, project, threshold=0.5):
        """Get labels with low agreement."""
        return self.filter(
            project=project,
            agreement_rate__lt=threshold
        ).order_by('agreement_rate')
    
    def get_unused_labels(self, project):
        """Get labels that are rarely used."""
        return self.filter(
            project=project,
            usage_count__lte=5
        ).order_by('usage_count')
```

### 4.5 创建 `serializers.py`

```python
# label_studio/data_quality/serializers.py
"""Serializers for Data Quality API."""

from rest_framework import serializers
from data_quality.models import (
    QualityReport,
    QualityIssue,
    AnnotatorQualityProfile,
    LabelQualityStats,
    QualityAssessmentConfig,
    QualityReportType,
    QualityIssueType,
    SeverityLevel,
)


class QualityReportSerializer(serializers.ModelSerializer):
    """Serializer for QualityReport."""
    
    project_title = serializers.CharField(source='project.title', read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = QualityReport
        fields = [
            'id', 'project', 'project_title', 'report_type',
            'overall_score', 'consistency_score', 'agreement_score',
            'completeness_score', 'statistics', 'issue_count',
            'critical_issue_count', 'tasks_analyzed', 'annotations_analyzed',
            'annotators_analyzed', 'created_at', 'created_by',
            'created_by_username',
        ]
        read_only_fields = [
            'id', 'overall_score', 'consistency_score', 'agreement_score',
            'completeness_score', 'statistics', 'issue_count',
            'critical_issue_count', 'tasks_analyzed', 'annotations_analyzed',
            'annotators_analyzed', 'created_at',
        ]


class QualityIssueSerializer(serializers.ModelSerializer):
    """Serializer for QualityIssue."""
    
    task_id = serializers.IntegerField(source='task.id', read_only=True)
    annotator_username = serializers.CharField(source='annotator.username', read_only=True)
    resolved_by_username = serializers.CharField(source='resolved_by.username', read_only=True)
    
    class Meta:
        model = QualityIssue
        fields = [
            'id', 'report', 'issue_type', 'severity', 'task', 'task_id',
            'annotation', 'annotator', 'annotator_username', 'title',
            'description', 'details', 'is_resolved', 'resolved_at',
            'resolved_by', 'resolved_by_username', 'resolution_notes',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class QualityIssueResolveSerializer(serializers.Serializer):
    """Serializer for resolving quality issues."""
    
    notes = serializers.CharField(
        required=False,
        default='',
        help_text='Resolution notes'
    )


class AnnotatorQualityProfileSerializer(serializers.ModelSerializer):
    """Serializer for AnnotatorQualityProfile."""
    
    username = serializers.CharField(source='user.username', read_only=True)
    project_title = serializers.CharField(source='project.title', read_only=True)
    
    class Meta:
        model = AnnotatorQualityProfile
        fields = [
            'id', 'user', 'username', 'project', 'project_title',
            'total_annotations', 'agreement_rate', 'avg_annotation_time',
            'quality_score', 'consistency_score', 'issue_count',
            'critical_issue_count', 'statistics', 'first_annotation_at',
            'last_annotation_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'total_annotations', 'agreement_rate', 'avg_annotation_time',
            'quality_score', 'consistency_score', 'issue_count',
            'critical_issue_count', 'statistics', 'first_annotation_at',
            'last_annotation_at', 'updated_at',
        ]


class LabelQualityStatsSerializer(serializers.ModelSerializer):
    """Serializer for LabelQualityStats."""
    
    project_title = serializers.CharField(source='project.title', read_only=True)
    
    class Meta:
        model = LabelQualityStats
        fields = [
            'id', 'project', 'project_title', 'label_name', 'label_type',
            'usage_count', 'unique_annotators', 'agreement_rate',
            'consistency_score', 'usage_percentage', 'statistics',
            'updated_at',
        ]
        read_only_fields = fields


class QualityAssessmentConfigSerializer(serializers.ModelSerializer):
    """Serializer for QualityAssessmentConfig."""
    
    class Meta:
        model = QualityAssessmentConfig
        fields = [
            'id', 'project', 'auto_assess', 'assess_after_count',
            'low_agreement_threshold', 'speed_anomaly_threshold',
            'outlier_detection_enabled', 'notify_on_critical',
            'notify_users', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class QualityAssessmentRequestSerializer(serializers.Serializer):
    """Serializer for quality assessment request."""
    
    assessors = serializers.ListField(
        child=serializers.ChoiceField(
            choices=['consistency', 'agreement', 'outlier', 'bias', 'completeness']
        ),
        required=False,
        help_text='Specific assessors to run'
    )
    
    include_details = serializers.BooleanField(
        default=True,
        help_text='Include detailed statistics'
    )
    
    notify_on_critical = serializers.BooleanField(
        default=True,
        help_text='Send notifications for critical issues'
    )


class QualityDashboardSerializer(serializers.Serializer):
    """Serializer for quality dashboard data."""
    
    project_id = serializers.IntegerField()
    project_title = serializers.CharField()
    
    # Summary
    overall_score = serializers.FloatField()
    total_issues = serializers.IntegerField()
    critical_issues = serializers.IntegerField()
    resolved_issues = serializers.IntegerField()
    
    # Scores
    consistency_score = serializers.FloatField()
    agreement_score = serializers.FloatField()
    completeness_score = serializers.FloatField()
    
    # Trends
    score_trend = serializers.ListField(
        child=serializers.FloatField()
    )
    
    # Top issues
    top_issues = QualityIssueSerializer(many=True)
    
    # Annotator stats
    annotator_stats = AnnotatorQualityProfileSerializer(many=True)
    
    # Label stats
    label_stats = LabelQualityStatsSerializer(many=True)
```

### 4.6 创建 `api.py`

```python
# label_studio/data_quality/api.py
"""Data Quality API endpoints."""

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
from data_quality.models import (
    QualityReport,
    QualityIssue,
    AnnotatorQualityProfile,
    LabelQualityStats,
    QualityAssessmentConfig,
)
from data_quality.serializers import (
    QualityReportSerializer,
    QualityIssueSerializer,
    QualityIssueResolveSerializer,
    AnnotatorQualityProfileSerializer,
    LabelQualityStatsSerializer,
    QualityAssessmentConfigSerializer,
    QualityAssessmentRequestSerializer,
    QualityDashboardSerializer,
)
from data_quality.assessors import QualityAssessmentEngine
from projects.models import Project

logger = logging.getLogger(__name__)


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Data Quality'],
        summary='List quality reports',
        description='Get all quality reports for a project.',
        parameters=[
            OpenApiParameter(
                name='project',
                type=OpenApiTypes.INT,
                location='query',
                description='Project ID',
                required=True,
            ),
            OpenApiParameter(
                name='report_type',
                type=OpenApiTypes.STR,
                location='query',
                description='Filter by report type',
            ),
        ],
    ),
)
class QualityReportListAPI(generics.ListAPIView):
    """List quality reports."""
    
    serializer_class = QualityReportSerializer
    permission_required = ViewClassPermission(
        GET=all_permissions.projects_view,
    )
    
    def get_queryset(self):
        project_id = self.request.query_params.get('project')
        report_type = self.request.query_params.get('report_type')
        
        queryset = QualityReport.objects.all()
        
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        
        if report_type:
            queryset = queryset.filter(report_type=report_type)
        
        return queryset.order_by('-created_at')


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Data Quality'],
        summary='Get quality report',
        description='Get details of a specific quality report.',
    ),
)
class QualityReportDetailAPI(generics.RetrieveAPIView):
    """Get quality report details."""
    
    serializer_class = QualityReportSerializer
    permission_required = all_permissions.projects_view
    queryset = QualityReport.objects.all()


class QualityAssessmentAPI(APIView):
    """Run quality assessment."""
    
    permission_required = all_permissions.projects_change
    
    @extend_schema(
        tags=['Data Quality'],
        summary='Run quality assessment',
        description='Trigger quality assessment for a project.',
        request=QualityAssessmentRequestSerializer,
        responses={200: QualityReportSerializer},
    )
    def post(self, request, project_pk):
        """Run quality assessment for a project."""
        project = get_object_or_404(Project, pk=project_pk)
        
        # Check permissions
        if not project.has_permission(request.user):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Validate request
        serializer = QualityAssessmentRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        assessors = serializer.validated_data.get('assessors')
        include_details = serializer.validated_data.get('include_details', True)
        
        try:
            # Run assessment
            engine = QualityAssessmentEngine(project)
            report = engine.run_assessment(
                assessors=assessors,
                include_details=include_details,
                user=request.user,
            )
            
            # Serialize response
            report_serializer = QualityReportSerializer(report)
            
            return Response(
                report_serializer.data,
                status=status.HTTP_200_OK
            )
        
        except Exception as e:
            logger.error(f'Error running quality assessment: {str(e)}', exc_info=True)
            return Response(
                {'error': f'Failed to run assessment: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Data Quality'],
        summary='List quality issues',
        description='Get all quality issues for a project.',
        parameters=[
            OpenApiParameter(
                name='project',
                type=OpenApiTypes.INT,
                location='query',
                description='Project ID',
            ),
            OpenApiParameter(
                name='severity',
                type=OpenApiTypes.STR,
                location='query',
                description='Filter by severity',
            ),
            OpenApiParameter(
                name='is_resolved',
                type=OpenApiTypes.BOOL,
                location='query',
                description='Filter by resolution status',
            ),
        ],
    ),
)
class QualityIssueListAPI(generics.ListAPIView):
    """List quality issues."""
    
    serializer_class = QualityIssueSerializer
    permission_required = all_permissions.projects_view
    
    def get_queryset(self):
        queryset = QualityIssue.objects.all()
        
        project_id = self.request.query_params.get('project')
        severity = self.request.query_params.get('severity')
        is_resolved = self.request.query_params.get('is_resolved')
        
        if project_id:
            queryset = queryset.filter(report__project_id=project_id)
        
        if severity:
            queryset = queryset.filter(severity=severity)
        
        if is_resolved is not None:
            queryset = queryset.filter(is_resolved=is_resolved.lower() == 'true')
        
        return queryset.order_by('-severity', '-created_at')


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Data Quality'],
        summary='Get quality issue',
        description='Get details of a specific quality issue.',
    ),
)
class QualityIssueDetailAPI(generics.RetrieveAPIView):
    """Get quality issue details."""
    
    serializer_class = QualityIssueSerializer
    permission_required = all_permissions.projects_view
    queryset = QualityIssue.objects.all()


class QualityIssueResolveAPI(APIView):
    """Resolve a quality issue."""
    
    permission_required = all_permissions.projects_change
    
    @extend_schema(
        tags=['Data Quality'],
        summary='Resolve quality issue',
        description='Mark a quality issue as resolved.',
        request=QualityIssueResolveSerializer,
    )
    def post(self, request, pk):
        """Resolve a quality issue."""
        issue = get_object_or_404(QualityIssue, pk=pk)
        
        serializer = QualityIssueResolveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        notes = serializer.validated_data.get('notes', '')
        
        issue.resolve(request.user, notes)
        
        return Response(
            QualityIssueSerializer(issue).data,
            status=status.HTTP_200_OK
        )


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Data Quality'],
        summary='List annotator profiles',
        description='Get quality profiles for annotators.',
    ),
)
class AnnotatorProfileListAPI(generics.ListAPIView):
    """List annotator quality profiles."""
    
    serializer_class = AnnotatorQualityProfileSerializer
    permission_required = all_permissions.projects_view
    
    def get_queryset(self):
        project_id = self.kwargs.get('project_pk')
        return AnnotatorQualityProfile.objects.filter(
            project_id=project_id
        ).order_by('-quality_score')


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Data Quality'],
        summary='Get annotator profile',
        description='Get quality profile for a specific annotator.',
    ),
)
class AnnotatorProfileDetailAPI(generics.RetrieveAPIView):
    """Get annotator quality profile."""
    
    serializer_class = AnnotatorQualityProfileSerializer
    permission_required = all_permissions.projects_view
    queryset = AnnotatorQualityProfile.objects.all()


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Data Quality'],
        summary='List label statistics',
        description='Get quality statistics for labels.',
    ),
)
class LabelStatsListAPI(generics.ListAPIView):
    """List label quality statistics."""
    
    serializer_class = LabelQualityStatsSerializer
    permission_required = all_permissions.projects_view
    
    def get_queryset(self):
        project_id = self.kwargs.get('project_pk')
        return LabelQualityStats.objects.filter(
            project_id=project_id
        ).order_by('-usage_count')


@api_view(['GET'])
@permission_classes([all_permissions.projects_view])
def quality_dashboard(request, project_pk):
    """Get quality dashboard data."""
    project = get_object_or_404(Project, pk=project_pk)
    
    # Get latest report
    latest_report = QualityReport.objects.filter(
        project=project
    ).order_by('-created_at').first()
    
    if not latest_report:
        return Response({
            'project_id': project.id,
            'project_title': project.title,
            'overall_score': 0.0,
            'total_issues': 0,
            'critical_issues': 0,
            'resolved_issues': 0,
            'consistency_score': 0.0,
            'agreement_score': 0.0,
            'completeness_score': 0.0,
            'score_trend': [],
            'top_issues': [],
            'annotator_stats': [],
            'label_stats': [],
        })
    
    # Get issues
    issues = QualityIssue.objects.filter(
        report=latest_report
    ).order_by('-severity')[:10]
    
    # Get annotator profiles
    annotator_profiles = AnnotatorQualityProfile.objects.filter(
        project=project
    ).order_by('-quality_score')[:10]
    
    # Get label stats
    label_stats = LabelQualityStats.objects.filter(
        project=project
    ).order_by('-usage_count')[:10]
    
    # Get score trend (last 10 reports)
    recent_reports = QualityReport.objects.filter(
        project=project
    ).order_by('-created_at')[:10]
    score_trend = [r.overall_score for r in recent_reports]
    
    return Response({
        'project_id': project.id,
        'project_title': project.title,
        'overall_score': latest_report.overall_score,
        'total_issues': latest_report.issue_count,
        'critical_issues': latest_report.critical_issue_count,
        'resolved_issues': QualityIssue.objects.filter(
            report=latest_report,
            is_resolved=True
        ).count(),
        'consistency_score': latest_report.consistency_score or 0.0,
        'agreement_score': latest_report.agreement_score or 0.0,
        'completeness_score': latest_report.completeness_score or 0.0,
        'score_trend': score_trend,
        'top_issues': QualityIssueSerializer(issues, many=True).data,
        'annotator_stats': AnnotatorQualityProfileSerializer(annotator_profiles, many=True).data,
        'label_stats': LabelQualityStatsSerializer(label_stats, many=True).data,
    })


@api_view(['GET'])
@permission_classes([all_permissions.projects_view])
def quality_summary(request, project_pk):
    """Get quality summary for a project."""
    project = get_object_or_404(Project, pk=project_pk)
    
    # Get issue statistics
    from django.db.models import Count
    issue_stats = QualityIssue.objects.filter(
        report__project=project,
        is_resolved=False
    ).values('severity').annotate(count=Count('id'))
    
    # Get annotator count
    annotator_count = AnnotatorQualityProfile.objects.filter(
        project=project
    ).count()
    
    # Get label count
    label_count = LabelQualityStats.objects.filter(
        project=project
    ).count()
    
    return Response({
        'project_id': project.id,
        'project_title': project.title,
        'issue_stats': {item['severity']: item['count'] for item in issue_stats},
        'annotator_count': annotator_count,
        'label_count': label_count,
        'has_config': QualityAssessmentConfig.objects.filter(project=project).exists(),
    })
```

### 4.7 创建 `urls.py`

```python
# label_studio/data_quality/urls.py
"""URL configuration for Data Quality API."""

from django.urls import path
from data_quality import api

app_name = 'data_quality'

urlpatterns = [
    # Reports
    path(
        'api/data-quality/reports/',
        api.QualityReportListAPI.as_view(),
        name='quality-report-list'
    ),
    path(
        'api/data-quality/reports/<int:pk>/',
        api.QualityReportDetailAPI.as_view(),
        name='quality-report-detail'
    ),
    
    # Assessment
    path(
        'api/data-quality/projects/<int:project_pk>/assess/',
        api.QualityAssessmentAPI.as_view(),
        name='quality-assess'
    ),
    
    # Issues
    path(
        'api/data-quality/issues/',
        api.QualityIssueListAPI.as_view(),
        name='quality-issue-list'
    ),
    path(
        'api/data-quality/issues/<int:pk>/',
        api.QualityIssueDetailAPI.as_view(),
        name='quality-issue-detail'
    ),
    path(
        'api/data-quality/issues/<int:pk>/resolve/',
        api.QualityIssueResolveAPI.as_view(),
        name='quality-issue-resolve'
    ),
    
    # Annotator profiles
    path(
        'api/data-quality/projects/<int:project_pk>/annotators/',
        api.AnnotatorProfileListAPI.as_view(),
        name='annotator-profile-list'
    ),
    path(
        'api/data-quality/annotators/<int:pk>/',
        api.AnnotatorProfileDetailAPI.as_view(),
        name='annotator-profile-detail'
    ),
    
    # Label statistics
    path(
        'api/data-quality/projects/<int:project_pk>/labels/',
        api.LabelStatsListAPI.as_view(),
        name='label-stats-list'
    ),
    
    # Dashboard
    path(
        'api/data-quality/projects/<int:project_pk>/dashboard/',
        api.quality_dashboard,
        name='quality-dashboard'
    ),
    path(
        'api/data-quality/projects/<int:project_pk>/summary/',
        api.quality_summary,
        name='quality-summary'
    ),
]
```

### 4.8 创建 `utils.py`

```python
# label_studio/data_quality/utils.py
"""Utility functions for Data Quality module."""

import logging
import numpy as np
from typing import List, Dict, Any, Optional
from collections import Counter
from sklearn.metrics import cohen_kappa_score

logger = logging.getLogger(__name__)


def compute_cohens_kappa(annotations1: List[Dict], annotations2: List[Dict]) -> float:
    """
    Compute Cohen's Kappa between two annotators.
    
    Args:
        annotations1: Annotations from first annotator
        annotations2: Annotations from second annotator
    
    Returns:
        Kappa score
    """
    if len(annotations1) != len(annotations2):
        raise ValueError("Annotations must have same length")
    
    if not annotations1:
        return 0.0
    
    # Extract labels
    labels1 = [extract_label(a) for a in annotations1]
    labels2 = [extract_label(a) for a in annotations2]
    
    try:
        kappa = cohen_kappa_score(labels1, labels2)
        return float(kappa)
    except Exception as e:
        logger.error(f'Error computing kappa: {str(e)}')
        return 0.0


def extract_label(annotation: Dict) -> str:
    """
    Extract label from annotation result.
    
    Args:
        annotation: Annotation dictionary
    
    Returns:
        Label string
    """
    result = annotation.get('result', [])
    
    for item in result:
        value = item.get('value', {})
        
        # Handle choices
        if 'choices' in value:
            choices = value['choices']
            if isinstance(choices, list) and choices:
                return choices[0]
            elif isinstance(choices, dict):
                return max(choices.items(), key=lambda x: x[1])[0]
        
        # Handle labels
        if 'labels' in value:
            labels = value['labels']
            if isinstance(labels, list) and labels:
                return labels[0]
    
    return 'unknown'


def compute_annotation_time_statistics(annotations: List[Dict]) -> Dict[str, float]:
    """
    Compute annotation time statistics.
    
    Args:
        annotations: List of annotations with timing data
    
    Returns:
        Dictionary with statistics
    """
    times = []
    
    for annotation in annotations:
        lead_time = annotation.get('lead_time')
        if lead_time and lead_time > 0:
            times.append(lead_time)
    
    if not times:
        return {
            'mean': 0.0,
            'std': 0.0,
            'min': 0.0,
            'max': 0.0,
            'median': 0.0,
        }
    
    return {
        'mean': float(np.mean(times)),
        'std': float(np.std(times)),
        'min': float(np.min(times)),
        'max': float(np.max(times)),
        'median': float(np.median(times)),
    }


def detect_speed_anomalies(
    annotations: List[Dict],
    threshold: float = 3.0
) -> List[Dict]:
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
    
    for annotation in annotations:
        lead_time = annotation.get('lead_time')
        if lead_time and lead_time > 0:
            times.append(lead_time)
            valid_annotations.append(annotation)
    
    if len(times) < 3:
        return []
    
    mean_time = np.mean(times)
    std_time = np.std(times)
    
    if std_time == 0:
        return []
    
    anomalies = []
    for i, (time, annotation) in enumerate(zip(times, valid_annotations)):
        z_score = abs(time - mean_time) / std_time
        if z_score > threshold:
            anomalies.append({
                'annotation': annotation,
                'time': time,
                'z_score': z_score,
                'mean': mean_time,
                'std': std_time,
            })
    
    return anomalies


def compute_label_distribution(annotations: List[Dict]) -> Dict[str, int]:
    """
    Compute label distribution from annotations.
    
    Args:
        annotations: List of annotations
    
    Returns:
        Dictionary mapping label to count
    """
    label_counts = Counter()
    
    for annotation in annotations:
        label = extract_label(annotation)
        if label != 'unknown':
            label_counts[label] += 1
    
    return dict(label_counts)


def compute_agreement_matrix(
    annotators: List[str],
    tasks: List[Dict],
    annotations: Dict[int, Dict[str, Dict]]
) -> Dict[str, Dict[str, float]]:
    """
    Compute pairwise agreement matrix between annotators.
    
    Args:
        annotators: List of annotator IDs
        tasks: List of tasks
        annotations: Nested dict: task_id -> annotator_id -> annotation
    
    Returns:
        Nested dict: annotator1 -> annotator2 -> agreement
    """
    matrix = {a1: {a2: 0.0 for a2 in annotators} for a1 in annotators}
    
    for a1 in annotators:
        for a2 in annotators:
            if a1 == a2:
                matrix[a1][a2] = 1.0
                continue
            
            agreements = []
            for task in tasks:
                task_id = task['id']
                
                if task_id not in annotations:
                    continue
                
                ann1 = annotations[task_id].get(a1)
                ann2 = annotations[task_id].get(a2)
                
                if ann1 and ann2:
                    label1 = extract_label(ann1)
                    label2 = extract_label(ann2)
                    agreements.append(1.0 if label1 == label2 else 0.0)
            
            if agreements:
                matrix[a1][a2] = float(np.mean(agreements))
    
    return matrix
```

### 4.9 创建 `signals.py`

```python
# label_studio/data_quality/signals.py
"""Signals for Data Quality module."""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from tasks.models import Annotation
from data_quality.models import QualityAssessmentConfig, QualityReport

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Annotation)
def auto_quality_assessment(sender, instance, created, **kwargs):
    """Trigger automatic quality assessment if configured."""
    if not created:
        return
    
    project = instance.task.project
    
    # Check if auto-assessment is enabled
    config = QualityAssessmentConfig.objects.filter(
        project=project,
        auto_assess=True
    ).first()
    
    if not config:
        return
    
    # Count recent annotations
    from django.utils.timezone import now, timedelta
    recent_count = Annotation.objects.filter(
        task__project=project,
        created_at__gte=now() - timedelta(hours=1)
    ).count()
    
    # Trigger assessment if threshold reached
    if recent_count >= config.assess_after_count:
        from data_quality.assessors import QualityAssessmentEngine
        
        try:
            engine = QualityAssessmentEngine(project)
            engine.run_assessment()
            logger.info(f'Auto quality assessment triggered for project {project.title}')
        except Exception as e:
            logger.error(f'Error in auto quality assessment: {str(e)}')
```

## 验证检查点

- [ ] 所有模型文件创建成功
- [ ] 数据库迁移生成成功：`python manage.py makemigrations data_quality`
- [ ] 数据库迁移执行成功：`python manage.py migrate`
- [ ] API端点可访问
- [ ] 序列化器正常工作
- [ ] 信号处理器正确连接

## 下一步

执行 `05_data_quality_assessors.md` 实现具体的数据质量评估器。
