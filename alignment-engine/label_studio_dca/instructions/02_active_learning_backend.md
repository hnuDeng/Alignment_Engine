# 指令 02：主动学习后端模块

## 目标

创建Active Learning模块的基础后端架构，包括模型、API和核心功能。

## 需要创建的文件

1. `label_studio/active_learning/__init__.py`
2. `label_studio/active_learning/apps.py`
3. `label_studio/active_learning/models.py`
4. `label_studio/active_learning/api.py`
5. `label_studio/active_learning/serializers.py`
6. `label_studio/active_learning/urls.py`
7. `label_studio/active_learning/managers.py`
8. `label_studio/active_learning/migrations/__init__.py`

## 详细实现

### 2.1 创建 `__init__.py`

```python
# label_studio/active_learning/__init__.py
default_app_config = 'active_learning.apps.ActiveLearningConfig'
```

### 2.2 创建 `apps.py`

```python
# label_studio/active_learning/apps.py
from django.apps import AppConfig


class ActiveLearningConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'active_learning'
    verbose_name = 'Active Learning'
    
    def ready(self):
        import active_learning.signals  # noqa
```

### 2.3 创建 `models.py`

```python
# label_studio/active_learning/models.py
"""Active Learning models for Data-Centric AI workflow."""

import logging
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


class ActiveLearningStrategy(models.TextChoices):
    """Available active learning strategies."""
    UNCERTAINTY = 'uncertainty', _('Uncertainty Sampling')
    DIVERSITY = 'diversity', _('Diversity Sampling')
    COMMITTEE = 'committee', _('Query by Committee')
    EXPECTED_GRADIENT = 'expected_gradient', _('Expected Gradient Change')
    HYBRID = 'hybrid', _('Hybrid Strategy')
    RANDOM = 'random', _('Random Sampling')


class UncertaintyMethod(models.TextChoices):
    """Uncertainty sampling methods."""
    LEAST_CONFIDENCE = 'least_confidence', _('Least Confidence')
    MARGIN_SAMPLING = 'margin_sampling', _('Margin Sampling')
    ENTROPY = 'entropy', _('Entropy')


class ActiveLearningConfig(models.Model):
    """Configuration for active learning in a project."""
    
    project = models.OneToOneField(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='active_learning_config',
        help_text='Project this configuration belongs to'
    )
    
    ml_backend = models.ForeignKey(
        'ml.MLBackend',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='al_configs',
        help_text='ML backend used for active learning predictions'
    )
    
    strategy = models.CharField(
        max_length=50,
        choices=ActiveLearningStrategy.choices,
        default=ActiveLearningStrategy.UNCERTAINTY,
        help_text='Active learning sampling strategy'
    )
    
    uncertainty_method = models.CharField(
        max_length=50,
        choices=UncertaintyMethod.choices,
        default=UncertaintyMethod.ENTROPY,
        help_text='Method for uncertainty calculation (used with uncertainty strategy)'
    )
    
    batch_size = models.IntegerField(
        default=10,
        help_text='Number of tasks to select in each round'
    )
    
    is_enabled = models.BooleanField(
        default=False,
        help_text='Whether active learning is enabled for this project'
    )
    
    auto_select = models.BooleanField(
        default=False,
        help_text='Automatically select next batch after annotation'
    )
    
    auto_train = models.BooleanField(
        default=False,
        help_text='Automatically trigger training after each round'
    )
    
    min_annotations_for_training = models.IntegerField(
        default=10,
        help_text='Minimum annotations before triggering training'
    )
    
    # Strategy-specific parameters stored as JSON
    strategy_params = models.JSONField(
        default=dict,
        blank=True,
        help_text='Strategy-specific parameters'
    )
    
    # Diversity sampling parameters
    diversity_metric = models.CharField(
        max_length=50,
        default='cosine',
        help_text='Distance metric for diversity sampling'
    )
    
    # Committee parameters
    committee_size = models.IntegerField(
        default=5,
        help_text='Number of models in committee (for QBC strategy)'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_al_configs'
    )
    
    class Meta:
        db_table = 'active_learning_config'
        verbose_name = 'Active Learning Configuration'
        verbose_name_plural = 'Active Learning Configurations'
    
    def __str__(self):
        return f'AL Config for {self.project.title} ({self.strategy})'
    
    def get_strategy_instance(self):
        """Get the strategy instance based on configuration."""
        from active_learning.strategies import get_strategy
        
        return get_strategy(
            strategy_name=self.strategy,
            uncertainty_method=self.uncertainty_method,
            diversity_metric=self.diversity_metric,
            committee_size=self.committee_size,
            **self.strategy_params
        )


class ActiveLearningRound(models.Model):
    """Record of an active learning round."""
    
    config = models.ForeignKey(
        ActiveLearningConfig,
        on_delete=models.CASCADE,
        related_name='rounds',
        help_text='Configuration this round belongs to'
    )
    
    round_number = models.IntegerField(
        help_text='Sequential round number'
    )
    
    selected_tasks = models.ManyToManyField(
        'tasks.Task',
        related_name='al_rounds',
        help_text='Tasks selected in this round'
    )
    
    task_count = models.IntegerField(
        default=0,
        help_text='Number of tasks selected'
    )
    
    strategy_used = models.CharField(
        max_length=50,
        help_text='Strategy used for selection'
    )
    
    selection_scores = models.JSONField(
        default=dict,
        help_text='Selection scores for each task'
    )
    
    # Metrics
    avg_uncertainty = models.FloatField(
        null=True,
        help_text='Average uncertainty of selected tasks'
    )
    
    diversity_score = models.FloatField(
        null=True,
        help_text='Diversity score of selected subset'
    )
    
    # Status
    is_completed = models.BooleanField(
        default=False,
        help_text='Whether all selected tasks are annotated'
    )
    
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When all tasks were annotated'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='al_rounds'
    )
    
    class Meta:
        db_table = 'active_learning_round'
        ordering = ['-round_number']
        unique_together = ['config', 'round_number']
    
    def __str__(self):
        return f'Round {self.round_number} for {self.config.project.title}'
    
    def check_completion(self):
        """Check if all selected tasks are annotated."""
        from tasks.models import Annotation
        
        selected = self.selected_tasks.all()
        for task in selected:
            if not task.annotations.filter(was_cancelled=False).exists():
                return False
        
        self.is_completed = True
        from django.utils.timezone import now
        self.completed_at = now()
        self.save(update_fields=['is_completed', 'completed_at'])
        return True


class TaskSelectionScore(models.Model):
    """Detailed scoring for task selection."""
    
    round = models.ForeignKey(
        ActiveLearningRound,
        on_delete=models.CASCADE,
        related_name='task_scores',
        help_text='Round this score belongs to'
    )
    
    task = models.ForeignKey(
        'tasks.Task',
        on_delete=models.CASCADE,
        related_name='al_scores',
        help_text='Task being scored'
    )
    
    # Scoring components
    uncertainty_score = models.FloatField(
        null=True,
        help_text='Uncertainty score (higher = more uncertain)'
    )
    
    diversity_score = models.FloatField(
        null=True,
        help_text='Diversity score (higher = more diverse)'
    )
    
    committee_disagreement = models.FloatField(
        null=True,
        help_text='Committee disagreement score'
    )
    
    final_score = models.FloatField(
        help_text='Final combined score'
    )
    
    rank = models.IntegerField(
        help_text='Rank in selection (1 = highest priority)'
    )
    
    is_selected = models.BooleanField(
        default=False,
        help_text='Whether this task was selected'
    )
    
    # Prediction details
    prediction_data = models.JSONField(
        default=dict,
        blank=True,
        help_text='Raw prediction data used for scoring'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'active_learning_task_score'
        ordering = ['round', 'rank']
        indexes = [
            models.Index(fields=['round', 'is_selected']),
            models.Index(fields=['task', 'is_selected']),
        ]
    
    def __str__(self):
        return f'Score for Task {self.task_id} in Round {self.round.round_number}'


class ActiveLearningFeedback(models.Model):
    """Feedback from annotators to improve active learning."""
    
    config = models.ForeignKey(
        ActiveLearningConfig,
        on_delete=models.CASCADE,
        related_name='feedbacks'
    )
    
    task = models.ForeignKey(
        'tasks.Task',
        on_delete=models.CASCADE,
        related_name='al_feedbacks'
    )
    
    # Feedback type
    FEEDBACK_TYPES = [
        ('useful', 'Selection was useful'),
        ('not_useful', 'Selection was not useful'),
        ('already_known', 'Task was already well-known'),
        ('too_difficult', 'Task was too difficult'),
        ('too_easy', 'Task was too easy'),
    ]
    
    feedback_type = models.CharField(
        max_length=20,
        choices=FEEDBACK_TYPES
    )
    
    comment = models.TextField(
        blank=True,
        help_text='Optional feedback comment'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    
    class Meta:
        db_table = 'active_learning_feedback'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'Feedback: {self.feedback_type} for Task {self.task_id}'
```

### 2.4 创建 `managers.py`

```python
# label_studio/active_learning/managers.py
"""Custom managers for Active Learning models."""

from django.db import models


class ActiveLearningConfigManager(models.Manager):
    """Manager for ActiveLearningConfig."""
    
    def get_enabled(self, project):
        """Get enabled config for a project."""
        return self.filter(
            project=project,
            is_enabled=True
        ).first()
    
    def get_or_create_default(self, project, user=None):
        """Get or create default config for a project."""
        config, created = self.get_or_create(
            project=project,
            defaults={
                'strategy': 'uncertainty',
                'batch_size': 10,
                'is_enabled': False,
                'created_by': user,
            }
        )
        return config, created


class ActiveLearningRoundManager(models.ObjectManager):
    """Manager for ActiveLearningRound."""
    
    def get_latest(self, config):
        """Get latest round for a config."""
        return self.filter(config=config).order_by('-round_number').first()
    
    def get_pending(self, config):
        """Get rounds that are not yet completed."""
        return self.filter(
            config=config,
            is_completed=False
        ).order_by('-round_number')
    
    def get_completed(self, config, limit=10):
        """Get completed rounds."""
        return self.filter(
            config=config,
            is_completed=True
        ).order_by('-completed_at')[:limit]


class TaskSelectionScoreManager(models.Manager):
    """Manager for TaskSelectionScore."""
    
    def get_selected_tasks(self, round):
        """Get selected tasks for a round."""
        return self.filter(
            round=round,
            is_selected=True
        ).order_by('rank')
    
    def get_top_scores(self, round, limit=10):
        """Get top scoring tasks."""
        return self.filter(
            round=round
        ).order_by('-final_score')[:limit]
```

### 2.5 创建 `serializers.py`

```python
# label_studio/active_learning/serializers.py
"""Serializers for Active Learning API."""

from rest_framework import serializers
from active_learning.models import (
    ActiveLearningConfig,
    ActiveLearningRound,
    TaskSelectionScore,
    ActiveLearningFeedback,
    ActiveLearningStrategy,
    UncertaintyMethod,
)
from projects.models import Project
from ml.models import MLBackend


class ActiveLearningConfigSerializer(serializers.ModelSerializer):
    """Serializer for ActiveLearningConfig."""
    
    project_title = serializers.CharField(source='project.title', read_only=True)
    ml_backend_title = serializers.CharField(source='ml_backend.title', read_only=True)
    round_count = serializers.IntegerField(source='rounds.count', read_only=True)
    
    class Meta:
        model = ActiveLearningConfig
        fields = [
            'id', 'project', 'project_title', 'ml_backend', 'ml_backend_title',
            'strategy', 'uncertainty_method', 'batch_size', 'is_enabled',
            'auto_select', 'auto_train', 'min_annotations_for_training',
            'strategy_params', 'diversity_metric', 'committee_size',
            'round_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_project(self, value):
        """Validate project exists and user has access."""
        if not Project.objects.filter(pk=value.pk).exists():
            raise serializers.ValidationError("Project does not exist.")
        return value
    
    def validate_ml_backend(self, value):
        """Validate ML backend exists if provided."""
        if value and not MLBackend.objects.filter(pk=value.pk).exists():
            raise serializers.ValidationError("ML backend does not exist.")
        return value
    
    def validate_batch_size(self, value):
        """Validate batch size is positive."""
        if value < 1:
            raise serializers.ValidationError("Batch size must be at least 1.")
        if value > 1000:
            raise serializers.ValidationError("Batch size cannot exceed 1000.")
        return value


class ActiveLearningRoundSerializer(serializers.ModelSerializer):
    """Serializer for ActiveLearningRound."""
    
    config_strategy = serializers.CharField(source='config.strategy', read_only=True)
    project_title = serializers.CharField(source='config.project.title', read_only=True)
    task_ids = serializers.ListField(
        child=serializers.IntegerField(),
        source='selected_tasks.values_list',
        read_only=True
    )
    
    class Meta:
        model = ActiveLearningRound
        fields = [
            'id', 'config', 'config_strategy', 'project_title',
            'round_number', 'task_count', 'strategy_used',
            'selection_scores', 'avg_uncertainty', 'diversity_score',
            'is_completed', 'completed_at', 'created_at',
        ]
        read_only_fields = [
            'id', 'round_number', 'strategy_used', 'selection_scores',
            'avg_uncertainty', 'diversity_score', 'is_completed',
            'completed_at', 'created_at',
        ]


class TaskSelectionScoreSerializer(serializers.ModelSerializer):
    """Serializer for TaskSelectionScore."""
    
    task_data = serializers.JSONField(source='task.data', read_only=True)
    
    class Meta:
        model = TaskSelectionScore
        fields = [
            'id', 'round', 'task', 'task_data', 'uncertainty_score',
            'diversity_score', 'committee_disagreement', 'final_score',
            'rank', 'is_selected', 'prediction_data', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class ActiveLearningFeedbackSerializer(serializers.ModelSerializer):
    """Serializer for ActiveLearningFeedback."""
    
    class Meta:
        model = ActiveLearningFeedback
        fields = [
            'id', 'config', 'task', 'feedback_type', 'comment',
            'created_at', 'created_by',
        ]
        read_only_fields = ['id', 'created_at', 'created_by']


class TaskSelectionRequestSerializer(serializers.Serializer):
    """Serializer for task selection request."""
    
    batch_size = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=1000,
        help_text='Number of tasks to select (overrides config)'
    )
    
    strategy = serializers.ChoiceField(
        choices=ActiveLearningStrategy.choices,
        required=False,
        help_text='Strategy to use (overrides config)'
    )
    
    exclude_annotated = serializers.BooleanField(
        default=True,
        help_text='Exclude already annotated tasks'
    )
    
    exclude_selected = serializers.BooleanField(
        default=True,
        help_text='Exclude tasks selected in previous rounds'
    )


class TaskSelectionResponseSerializer(serializers.Serializer):
    """Serializer for task selection response."""
    
    round_id = serializers.IntegerField()
    round_number = serializers.IntegerField()
    task_ids = serializers.ListField(child=serializers.IntegerField())
    task_scores = serializers.DictField()
    strategy_used = serializers.CharField()
    avg_uncertainty = serializers.FloatField()
    diversity_score = serializers.FloatField()
    selection_summary = serializers.DictField()
```

### 2.6 创建 `api.py`

```python
# label_studio/active_learning/api.py
"""Active Learning API endpoints."""

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
from active_learning.models import (
    ActiveLearningConfig,
    ActiveLearningRound,
    TaskSelectionScore,
    ActiveLearningFeedback,
)
from active_learning.serializers import (
    ActiveLearningConfigSerializer,
    ActiveLearningRoundSerializer,
    TaskSelectionScoreSerializer,
    ActiveLearningFeedbackSerializer,
    TaskSelectionRequestSerializer,
    TaskSelectionResponseSerializer,
)
from active_learning.selectors import TaskSelector
from projects.models import Project

logger = logging.getLogger(__name__)


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Active Learning'],
        summary='List Active Learning configurations',
        description='Get all active learning configurations for a project.',
        parameters=[
            OpenApiParameter(
                name='project',
                type=OpenApiTypes.INT,
                location='query',
                description='Project ID',
                required=True,
            ),
        ],
    ),
)
@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Active Learning'],
        summary='Create Active Learning configuration',
        description='Create a new active learning configuration for a project.',
        request=ActiveLearningConfigSerializer,
    ),
)
class ActiveLearningConfigListAPI(generics.ListCreateAPIView):
    """List and create active learning configurations."""
    
    serializer_class = ActiveLearningConfigSerializer
    permission_required = ViewClassPermission(
        GET=all_permissions.projects_view,
        POST=all_permissions.projects_change,
    )
    
    def get_queryset(self):
        project_id = self.request.query_params.get('project')
        if project_id:
            return ActiveLearningConfig.objects.filter(project_id=project_id)
        return ActiveLearningConfig.objects.none()
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Active Learning'],
        summary='Get Active Learning configuration',
        description='Get details of a specific active learning configuration.',
    ),
)
@method_decorator(
    name='put',
    decorator=extend_schema(
        tags=['Active Learning'],
        summary='Update Active Learning configuration',
        description='Update an active learning configuration.',
        request=ActiveLearningConfigSerializer,
    ),
)
@method_decorator(
    name='patch',
    decorator=extend_schema(
        tags=['Active Learning'],
        summary='Partial update Active Learning configuration',
        description='Partially update an active learning configuration.',
        request=ActiveLearningConfigSerializer,
    ),
)
@method_decorator(
    name='delete',
    decorator=extend_schema(
        tags=['Active Learning'],
        summary='Delete Active Learning configuration',
        description='Delete an active learning configuration.',
    ),
)
class ActiveLearningConfigDetailAPI(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, and delete active learning configurations."""
    
    serializer_class = ActiveLearningConfigSerializer
    permission_required = all_permissions.projects_change
    queryset = ActiveLearningConfig.objects.all()


class TaskSelectionAPI(APIView):
    """Select tasks using active learning strategy."""
    
    permission_required = all_permissions.projects_change
    
    @extend_schema(
        tags=['Active Learning'],
        summary='Select tasks for annotation',
        description='Select the next batch of tasks using active learning.',
        request=TaskSelectionRequestSerializer,
        responses={200: TaskSelectionResponseSerializer},
    )
    def post(self, request, pk):
        """
        Select tasks for annotation using active learning.
        
        This endpoint uses the configured strategy to select the most
        informative tasks for annotation.
        """
        config = get_object_or_404(ActiveLearningConfig, pk=pk)
        
        # Check permissions
        if not config.project.has_permission(request.user):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Validate request
        serializer = TaskSelectionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Get parameters
        batch_size = serializer.validated_data.get('batch_size', config.batch_size)
        strategy_name = serializer.validated_data.get('strategy', config.strategy)
        exclude_annotated = serializer.validated_data.get('exclude_annotated', True)
        exclude_selected = serializer.validated_data.get('exclude_selected', True)
        
        try:
            # Create task selector
            selector = TaskSelector(config)
            
            # Select tasks
            result = selector.select_tasks(
                batch_size=batch_size,
                strategy_name=strategy_name,
                exclude_annotated=exclude_annotated,
                exclude_selected=exclude_selected,
                user=request.user,
            )
            
            return Response(result, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f'Error selecting tasks: {str(e)}', exc_info=True)
            return Response(
                {'error': f'Failed to select tasks: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ActiveLearningRoundListAPI(generics.ListAPIView):
    """List active learning rounds."""
    
    serializer_class = ActiveLearningRoundSerializer
    permission_required = all_permissions.projects_view
    
    def get_queryset(self):
        config_id = self.kwargs.get('config_pk')
        return ActiveLearningRound.objects.filter(config_id=config_id)


class ActiveLearningRoundDetailAPI(generics.RetrieveAPIView):
    """Get active learning round details."""
    
    serializer_class = ActiveLearningRoundSerializer
    permission_required = all_permissions.projects_view
    queryset = ActiveLearningRound.objects.all()


class TaskSelectionScoreListAPI(generics.ListAPIView):
    """List task selection scores for a round."""
    
    serializer_class = TaskSelectionScoreSerializer
    permission_required = all_permissions.projects_view
    
    def get_queryset(self):
        round_id = self.kwargs.get('round_pk')
        return TaskSelectionScore.objects.filter(round_id=round_id)


class ActiveLearningFeedbackCreateAPI(generics.CreateAPIView):
    """Create feedback for active learning."""
    
    serializer_class = ActiveLearningFeedbackSerializer
    permission_required = all_permissions.projects_change
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


@api_view(['POST'])
@permission_classes([all_permissions.projects_change])
def toggle_active_learning(request, pk):
    """Toggle active learning for a project."""
    config = get_object_or_404(ActiveLearningConfig, pk=pk)
    config.is_enabled = not config.is_enabled
    config.save(update_fields=['is_enabled'])
    
    return Response({
        'id': config.id,
        'is_enabled': config.is_enabled,
        'message': f'Active learning {"enabled" if config.is_enabled else "disabled"}'
    })


@api_view(['GET'])
@permission_classes([all_permissions.projects_view])
def active_learning_status(request, project_pk):
    """Get active learning status for a project."""
    project = get_object_or_404(Project, pk=project_pk)
    
    config = ActiveLearningConfig.objects.filter(project=project).first()
    
    if not config:
        return Response({
            'configured': False,
            'is_enabled': False,
        })
    
    latest_round = ActiveLearningRound.objects.filter(
        config=config
    ).order_by('-round_number').first()
    
    return Response({
        'configured': True,
        'is_enabled': config.is_enabled,
        'strategy': config.strategy,
        'total_rounds': config.rounds.count(),
        'latest_round': ActiveLearningRoundSerializer(latest_round).data if latest_round else None,
        'pending_tasks': TaskSelectionScore.objects.filter(
            round__config=config,
            is_selected=True,
            round__is_completed=False
        ).count(),
    })
```

### 2.7 创建 `urls.py`

```python
# label_studio/active_learning/urls.py
"""URL configuration for Active Learning API."""

from django.urls import path
from active_learning import api

app_name = 'active_learning'

urlpatterns = [
    # Configuration endpoints
    path(
        'api/active-learning/configs/',
        api.ActiveLearningConfigListAPI.as_view(),
        name='al-config-list'
    ),
    path(
        'api/active-learning/configs/<int:pk>/',
        api.ActiveLearningConfigDetailAPI.as_view(),
        name='al-config-detail'
    ),
    path(
        'api/active-learning/configs/<int:pk>/toggle/',
        api.toggle_active_learning,
        name='al-config-toggle'
    ),
    
    # Task selection endpoint
    path(
        'api/active-learning/configs/<int:pk>/select/',
        api.TaskSelectionAPI.as_view(),
        name='al-task-select'
    ),
    
    # Rounds endpoints
    path(
        'api/active-learning/configs/<int:config_pk>/rounds/',
        api.ActiveLearningRoundListAPI.as_view(),
        name='al-round-list'
    ),
    path(
        'api/active-learning/rounds/<int:pk>/',
        api.ActiveLearningRoundDetailAPI.as_view(),
        name='al-round-detail'
    ),
    
    # Scores endpoints
    path(
        'api/active-learning/rounds/<int:round_pk>/scores/',
        api.TaskSelectionScoreListAPI.as_view(),
        name='al-score-list'
    ),
    
    # Feedback endpoint
    path(
        'api/active-learning/feedback/',
        api.ActiveLearningFeedbackCreateAPI.as_view(),
        name='al-feedback-create'
    ),
    
    # Status endpoint
    path(
        'api/active-learning/projects/<int:project_pk>/status/',
        api.active_learning_status,
        name='al-status'
    ),
]
```

### 2.8 创建 `signals.py`

```python
# label_studio/active_learning/signals.py
"""Signals for Active Learning module."""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from tasks.models import Annotation
from active_learning.models import ActiveLearningConfig, ActiveLearningRound

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Annotation)
def check_round_completion(sender, instance, created, **kwargs):
    """Check if active learning round is completed after annotation."""
    if not created:
        return
    
    task = instance.task
    project = task.project
    
    # Find active config for this project
    config = ActiveLearningConfig.objects.filter(
        project=project,
        is_enabled=True,
        auto_select=True
    ).first()
    
    if not config:
        return
    
    # Find latest incomplete round
    latest_round = ActiveLearningRound.objects.filter(
        config=config,
        is_completed=False
    ).first()
    
    if not latest_round:
        return
    
    # Check if this task was in the round
    if not latest_round.selected_tasks.filter(pk=task.pk).exists():
        return
    
    # Check completion
    if latest_round.check_completion():
        logger.info(f'Active learning round {latest_round.round_number} completed for project {project.title}')
        
        # Auto-select next batch if enabled
        if config.auto_select:
            from active_learning.selectors import TaskSelector
            selector = TaskSelector(config)
            try:
                selector.select_tasks(batch_size=config.batch_size)
                logger.info(f'Auto-selected next batch for project {project.title}')
            except Exception as e:
                logger.error(f'Failed to auto-select tasks: {str(e)}')


@receiver(post_save, sender=Annotation)
def trigger_training(sender, instance, created, **kwargs):
    """Trigger training if enough annotations collected."""
    if not created:
        return
    
    project = instance.task.project
    
    config = ActiveLearningConfig.objects.filter(
        project=project,
        is_enabled=True,
        auto_train=True
    ).first()
    
    if not config or not config.ml_backend:
        return
    
    # Count annotations since last training
    from django.utils.timezone import now, timedelta
    from tasks.models import Annotation as AnnotationModel
    
    recent_annotations = AnnotationModel.objects.filter(
        task__project=project,
        created_at__gte=now() - timedelta(hours=1)
    ).count()
    
    if recent_annotations >= config.min_annotations_for_training:
        try:
            config.ml_backend.train()
            logger.info(f'Triggered training for project {project.title}')
        except Exception as e:
            logger.error(f'Failed to trigger training: {str(e)}')
```

## 验证检查点

- [ ] 所有模型文件创建成功
- [ ] 数据库迁移生成成功：`python manage.py makemigrations active_learning`
- [ ] 数据库迁移执行成功：`python manage.py migrate`
- [ ] API端点可访问
- [ ] 序列化器正常工作
- [ ] 信号处理器正确连接

## 下一步

执行 `03_active_learning_strategies.md` 实现具体的主动学习策略。
