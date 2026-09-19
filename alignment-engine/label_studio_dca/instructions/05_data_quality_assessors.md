# 指令 05：数据质量评估器实现

## 目标

实现各种数据质量评估器，包括一致性评估、标注者间一致性、异常检测等。

## 需要创建的文件

1. `label_studio/data_quality/assessors/__init__.py`
2. `label_studio/data_quality/assessors/base.py`
3. `label_studio/data_quality/assessors/engine.py`
4. `label_studio/data_quality/assessors/consistency.py`
5. `label_studio/data_quality/assessors/agreement.py`
6. `label_studio/data_quality/assessors/outlier.py`
7. `label_studio/data_quality/assessors/bias.py`
8. `label_studio/data_quality/assessors/completeness.py`
9. `label_studio/data_quality/reporters/__init__.py`
10. `label_studio/data_quality/reporters/quality_report.py`

## 详细实现

### 5.1 创建 `assessors/__init__.py`

```python
# label_studio/data_quality/assessors/__init__.py
"""Quality assessors for Data Quality module."""

from data_quality.assessors.engine import QualityAssessmentEngine
from data_quality.assessors.consistency import ConsistencyAssessor
from data_quality.assessors.agreement import AgreementAssessor
from data_quality.assessors.outlier import OutlierAssessor
from data_quality.assessors.bias import BiasAssessor
from data_quality.assessors.completeness import CompletenessAssessor

__all__ = [
    'QualityAssessmentEngine',
    'ConsistencyAssessor',
    'AgreementAssessor',
    'OutlierAssessor',
    'BiasAssessor',
    'CompletenessAssessor',
]
```

### 5.2 创建 `assessors/base.py`

```python
# label_studio/data_quality/assessors/base.py
"""Base class for quality assessors."""

import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from django.db.models import QuerySet

logger = logging.getLogger(__name__)


class QualityIssue:
    """Represents a quality issue found during assessment."""
    
    def __init__(
        self,
        issue_type: str,
        severity: str,
        title: str,
        description: str,
        task_id: Optional[int] = None,
        annotation_id: Optional[int] = None,
        annotator_id: Optional[int] = None,
        details: Optional[Dict] = None
    ):
        self.issue_type = issue_type
        self.severity = severity
        self.title = title
        self.description = description
        self.task_id = task_id
        self.annotation_id = annotation_id
        self.annotator_id = annotator_id
        self.details = details or {}


class AssessmentResult:
    """Result of a quality assessment."""
    
    def __init__(
        self,
        assessor_name: str,
        score: float,
        statistics: Dict[str, Any],
        issues: List[QualityIssue],
        details: Optional[Dict] = None
    ):
        self.assessor_name = assessor_name
        self.score = score  # 0-1, higher is better
        self.statistics = statistics
        self.issues = issues
        self.details = details or {}
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'assessor': self.assessor_name,
            'score': self.score,
            'statistics': self.statistics,
            'issue_count': len(self.issues),
            'issues': [
                {
                    'type': issue.issue_type,
                    'severity': issue.severity,
                    'title': issue.title,
                    'description': issue.description,
                    'task_id': issue.task_id,
                    'annotation_id': issue.annotation_id,
                    'annotator_id': issue.annotator_id,
                    'details': issue.details,
                }
                for issue in self.issues
            ],
            'details': self.details,
        }


class BaseAssessor(ABC):
    """Base class for all quality assessors."""
    
    def __init__(self, project):
        """
        Initialize assessor.
        
        Args:
            project: Project instance
        """
        self.project = project
        self.issues = []
        self.statistics = {}
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Assessor name."""
        raise NotImplementedError
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Assessor description."""
        raise NotImplementedError
    
    @abstractmethod
    def assess(self, include_details: bool = True) -> AssessmentResult:
        """
        Run assessment.
        
        Args:
            include_details: Whether to include detailed statistics
        
        Returns:
            AssessmentResult
        """
        raise NotImplementedError
    
    def add_issue(
        self,
        issue_type: str,
        severity: str,
        title: str,
        description: str,
        task_id: Optional[int] = None,
        annotation_id: Optional[int] = None,
        annotator_id: Optional[int] = None,
        details: Optional[Dict] = None
    ):
        """Add a quality issue."""
        issue = QualityIssue(
            issue_type=issue_type,
            severity=severity,
            title=title,
            description=description,
            task_id=task_id,
            annotation_id=annotation_id,
            annotator_id=annotator_id,
            details=details,
        )
        self.issues.append(issue)
    
    def get_annotations(self, limit: int = None) -> QuerySet:
        """
        Get annotations for the project.
        
        Args:
            limit: Maximum number of annotations to return
        
        Returns:
            QuerySet of annotations
        """
        from tasks.models import Annotation
        
        queryset = Annotation.objects.filter(
            task__project=self.project,
            was_cancelled=False
        ).select_related('task', 'completed_by').order_by('-created_at')
        
        if limit:
            queryset = queryset[:limit]
        
        return queryset
    
    def get_tasks(self) -> QuerySet:
        """Get tasks for the project."""
        from tasks.models import Task
        return Task.objects.filter(project=self.project)
    
    def get_annotators(self) -> List:
        """Get unique annotators for the project."""
        from tasks.models import Annotation
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        
        annotator_ids = Annotation.objects.filter(
            task__project=self.project,
            was_cancelled=False
        ).values_list('completed_by', flat=True).distinct()
        
        return User.objects.filter(id__in=annotator_ids)
```

### 5.3 创建 `assessors/engine.py`

```python
# label_studio/data_quality/assessors/engine.py
"""Quality assessment engine that coordinates all assessors."""

import logging
from typing import List, Optional
from django.utils.timezone import now

from data_quality.models import (
    QualityReport,
    QualityIssue as QualityIssueModel,
    QualityReportType,
)
from data_quality.assessors.base import BaseAssessor, AssessmentResult
from data_quality.assessors.consistency import ConsistencyAssessor
from data_quality.assessors.agreement import AgreementAssessor
from data_quality.assessors.outlier import OutlierAssessor
from data_quality.assessors.bias import BiasAssessor
from data_quality.assessors.completeness import CompletenessAssessor

logger = logging.getLogger(__name__)

# Registry of available assessors
ASSESSOR_REGISTRY = {
    'consistency': ConsistencyAssessor,
    'agreement': AgreementAssessor,
    'outlier': OutlierAssessor,
    'bias': BiasAssessor,
    'completeness': CompletenessAssessor,
}


class QualityAssessmentEngine:
    """
    Engine for running quality assessments.
    
    Coordinates multiple assessors and generates consolidated reports.
    """
    
    def __init__(self, project):
        """
        Initialize engine.
        
        Args:
            project: Project instance
        """
        self.project = project
        self.assessors = {}
        self.results = {}
    
    def get_assessor(self, name: str) -> BaseAssessor:
        """
        Get assessor instance by name.
        
        Args:
            name: Assessor name
        
        Returns:
            Assessor instance
        """
        if name not in ASSESSOR_REGISTRY:
            raise ValueError(f"Unknown assessor: {name}. Available: {list(ASSESSOR_REGISTRY.keys())}")
        
        return ASSESSOR_REGISTRY[name](self.project)
    
    def run_assessment(
        self,
        assessors: Optional[List[str]] = None,
        include_details: bool = True,
        user=None
    ) -> QualityReport:
        """
        Run quality assessment.
        
        Args:
            assessors: List of assessor names to run (None for all)
            include_details: Whether to include detailed statistics
            user: User running the assessment
        
        Returns:
            QualityReport instance
        """
        # Determine which assessors to run
        if assessors is None:
            assessors = list(ASSESSOR_REGISTRY.keys())
        
        # Run each assessor
        all_issues = []
        all_statistics = {}
        scores = []
        
        for assessor_name in assessors:
            try:
                assessor = self.get_assessor(assessor_name)
                result = assessor.assess(include_details=include_details)
                
                self.results[assessor_name] = result
                all_issues.extend(result.issues)
                all_statistics[assessor_name] = result.statistics
                scores.append(result.score)
                
                logger.info(
                    f'Assessor {assessor_name} completed: '
                    f'score={result.score:.3f}, issues={len(result.issues)}'
                )
            
            except Exception as e:
                logger.error(f'Error in assessor {assessor_name}: {str(e)}', exc_info=True)
                scores.append(0.0)
                all_statistics[assessor_name] = {'error': str(e)}
        
        # Compute overall score
        overall_score = sum(scores) / len(scores) if scores else 0.0
        
        # Count issues by severity
        issue_count = len(all_issues)
        critical_count = sum(1 for i in all_issues if i.severity == 'critical')
        
        # Count tasks and annotations analyzed
        from tasks.models import Task, Annotation
        tasks_analyzed = Task.objects.filter(project=self.project).count()
        annotations_analyzed = Annotation.objects.filter(
            task__project=self.project,
            was_cancelled=False
        ).count()
        annotators_analyzed = len(self.get_annotators())
        
        # Create report
        report = QualityReport.objects.create(
            project=self.project,
            report_type=QualityReportType.PROJECT,
            overall_score=overall_score,
            consistency_score=self.results.get('consistency', AssessmentResult('', 0, {}, [])).score,
            agreement_score=self.results.get('agreement', AssessmentResult('', 0, {}, [])).score,
            completeness_score=self.results.get('completeness', AssessmentResult('', 0, {}, [])).score,
            statistics=all_statistics,
            issue_count=issue_count,
            critical_issue_count=critical_count,
            tasks_analyzed=tasks_analyzed,
            annotations_analyzed=annotations_analyzed,
            annotators_analyzed=annotators_analyzed,
            created_by=user,
        )
        
        # Create issue records
        issue_objects = []
        for issue in all_issues:
            issue_obj = QualityIssueModel(
                report=report,
                issue_type=issue.issue_type,
                severity=issue.severity,
                title=issue.title,
                description=issue.description,
                task_id=issue.task_id,
                annotation_id=issue.annotation_id,
                annotator_id=issue.annotator_id,
                details=issue.details,
            )
            issue_objects.append(issue_obj)
        
        if issue_objects:
            QualityIssueModel.objects.bulk_create(issue_objects)
        
        logger.info(
            f'Quality assessment completed for project {self.project.title}: '
            f'score={overall_score:.3f}, issues={issue_count}, critical={critical_count}'
        )
        
        return report
    
    def get_annotators(self):
        """Get unique annotators for the project."""
        from tasks.models import Annotation
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        
        annotator_ids = Annotation.objects.filter(
            task__project=self.project,
            was_cancelled=False
        ).values_list('completed_by', flat=True).distinct()
        
        return User.objects.filter(id__in=annotator_ids)
```

### 5.4 创建 `assessors/consistency.py`

```python
# label_studio/data_quality/assessors/consistency.py
"""Consistency assessor for detecting annotation inconsistencies."""

import logging
import numpy as np
from typing import Dict, List, Any
from collections import defaultdict

from data_quality.assessors.base import BaseAssessor, AssessmentResult
from data_quality.utils import extract_label

logger = logging.getLogger(__name__)


class ConsistencyAssessor(BaseAssessor):
    """
    Assessor for annotation consistency.
    
    Detects inconsistencies in annotations, such as:
    - Same task annotated differently by same annotator
    - Conflicting labels for similar data
    """
    
    @property
    def name(self) -> str:
        return 'consistency'
    
    @property
    def description(self) -> str:
        return 'Assesses annotation consistency and detects inconsistencies'
    
    def assess(self, include_details: bool = True) -> AssessmentResult:
        """
        Run consistency assessment.
        
        Returns:
            AssessmentResult with consistency score and issues
        """
        self.issues = []
        self.statistics = {}
        
        # Get all annotations
        annotations = self.get_annotations()
        
        if not annotations.exists():
            return AssessmentResult(
                assessor_name=self.name,
                score=1.0,
                statistics={'message': 'No annotations to assess'},
                issues=[],
            )
        
        # Group annotations by task
        task_annotations = defaultdict(list)
        for ann in annotations:
            task_annotations[ann.task_id].append(ann)
        
        # Check for inconsistencies
        inconsistent_tasks = []
        total_tasks = len(task_annotations)
        
        for task_id, task_anns in task_annotations.items():
            if len(task_anns) < 2:
                continue
            
            # Extract labels from each annotation
            labels = [extract_label({'result': ann.result}) for ann in task_anns]
            unique_labels = set(labels)
            
            # If multiple different labels, it's inconsistent
            if len(unique_labels) > 1:
                inconsistent_tasks.append({
                    'task_id': task_id,
                    'labels': labels,
                    'unique_labels': list(unique_labels),
                    'annotation_count': len(task_anns),
                })
                
                self.add_issue(
                    issue_type='inconsistency',
                    severity='high' if len(unique_labels) > 2 else 'medium',
                    title=f'Inconsistent annotations for task {task_id}',
                    description=f'Task has {len(unique_labels)} different labels: {", ".join(unique_labels)}',
                    task_id=task_id,
                    details={
                        'labels': labels,
                        'unique_labels': list(unique_labels),
                    }
                )
        
        # Compute consistency score
        if total_tasks > 0:
            consistency_rate = 1.0 - (len(inconsistent_tasks) / total_tasks)
        else:
            consistency_rate = 1.0
        
        self.statistics = {
            'total_tasks_with_multiple_annotations': total_tasks,
            'inconsistent_tasks': len(inconsistent_tasks),
            'consistency_rate': consistency_rate,
            'inconsistent_task_ids': [t['task_id'] for t in inconsistent_tasks[:10]],
        }
        
        if include_details:
            self.statistics['inconsistency_details'] = inconsistent_tasks[:20]
        
        return AssessmentResult(
            assessor_name=self.name,
            score=consistency_rate,
            statistics=self.statistics,
            issues=self.issues,
        )
```

### 5.5 创建 `assessors/agreement.py`

```python
# label_studio/data_quality/assessors/agreement.py
"""Agreement assessor for computing inter-annotator agreement."""

import logging
import numpy as np
from typing import Dict, List, Any
from collections import defaultdict
from itertools import combinations

from data_quality.assessors.base import BaseAssessor, AssessmentResult
from data_quality.utils import extract_label, compute_cohens_kappa

logger = logging.getLogger(__name__)


class AgreementAssessor(BaseAssessor):
    """
    Assessor for inter-annotator agreement.
    
    Computes agreement metrics including:
    - Pairwise agreement rates
    - Cohen's Kappa
    - Fleiss' Kappa (for multiple annotators)
    """
    
    @property
    def name(self) -> str:
        return 'agreement'
    
    @property
    def description(self) -> str:
        return 'Assesses inter-annotator agreement'
    
    def assess(self, include_details: bool = True) -> AssessmentResult:
        """
        Run agreement assessment.
        
        Returns:
            AssessmentResult with agreement score and issues
        """
        self.issues = []
        self.statistics = {}
        
        # Get annotations grouped by task
        annotations = self.get_annotations()
        
        if not annotations.exists():
            return AssessmentResult(
                assessor_name=self.name,
                score=1.0,
                statistics={'message': 'No annotations to assess'},
                issues=[],
            )
        
        # Group by task and annotator
        task_annotator_labels = defaultdict(dict)
        for ann in annotations:
            label = extract_label({'result': ann.result})
            task_annotator_labels[ann.task_id][ann.completed_by_id] = label
        
        # Compute pairwise agreement
        annotator_pairs = defaultdict(list)
        annotator_labels = defaultdict(list)
        
        for task_id, annotator_labels_dict in task_annotator_labels.items():
            annotators = list(annotator_labels_dict.keys())
            
            # Pairwise comparisons
            for a1, a2 in combinations(annotators, 2):
                label1 = annotator_labels_dict[a1]
                label2 = annotator_labels_dict[a2]
                
                agreement = 1.0 if label1 == label2 else 0.0
                annotator_pairs[(a1, a2)].append(agreement)
            
            # Collect per-annotator labels
            for annotator_id, label in annotator_labels_dict.items():
                annotator_labels[annotator_id].append(label)
        
        # Compute agreement rates
        pair_agreements = {}
        for (a1, a2), agreements in annotator_pairs.items():
            pair_agreements[(a1, a2)] = {
                'agreement_rate': np.mean(agreements),
                'task_count': len(agreements),
            }
        
        # Compute overall agreement
        all_agreement_rates = [v['agreement_rate'] for v in pair_agreements.values()]
        overall_agreement = np.mean(all_agreement_rates) if all_agreement_rates else 1.0
        
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
            'total_annotators': len(annotator_labels),
            'total_pairs': len(pair_agreements),
            'overall_agreement_rate': overall_agreement,
            'low_agreement_pairs': len(low_agreement_pairs),
            'pair_agreements': {
                f'{a1}_{a2}': stats
                for (a1, a2), stats in list(pair_agreements.items())[:20]
            },
        }
        
        if include_details:
            self.statistics['low_agreement_details'] = low_agreement_pairs[:10]
        
        return AssessmentResult(
            assessor_name=self.name,
            score=overall_agreement,
            statistics=self.statistics,
            issues=self.issues,
        )
```

### 5.6 创建 `assessors/outlier.py`

```python
# label_studio/data_quality/assessors/outlier.py
"""Outlier assessor for detecting anomalous annotations."""

import logging
import numpy as np
from typing import Dict, List, Any
from collections import defaultdict

from data_quality.assessors.base import BaseAssessor, AssessmentResult
from data_quality.utils import (
    extract_label,
    compute_annotation_time_statistics,
    detect_speed_anomalies,
)

logger = logging.getLogger(__name__)


class OutlierAssessor(BaseAssessor):
    """
    Assessor for detecting outlier annotations.
    
    Detects:
    - Speed anomalies (too fast or too slow)
    - Label distribution anomalies
    - Pattern anomalies
    """
    
    @property
    def name(self) -> str:
        return 'outlier'
    
    @property
    def description(self) -> str:
        return 'Detects outlier annotations'
    
    def assess(self, include_details: bool = True) -> AssessmentResult:
        """
        Run outlier assessment.
        
        Returns:
            AssessmentResult with outlier score and issues
        """
        self.issues = []
        self.statistics = {}
        
        annotations = list(self.get_annotations())
        
        if not annotations:
            return AssessmentResult(
                assessor_name=self.name,
                score=1.0,
                statistics={'message': 'No annotations to assess'},
                issues=[],
            )
        
        # Detect speed anomalies
        speed_anomalies = detect_speed_anomalies(annotations, threshold=3.0)
        
        for anomaly in speed_anomalies:
            annotation = anomaly['annotation']
            
            self.add_issue(
                issue_type='speed_anomaly',
                severity='high' if anomaly['z_score'] > 5 else 'medium',
                title=f'Speed anomaly detected',
                description=(
                    f'Annotation completed in {anomaly["time"]:.1f}s '
                    f'(mean: {anomaly["mean"]:.1f}s, z-score: {anomaly["z_score"]:.2f})'
                ),
                task_id=annotation.task_id,
                annotation_id=annotation.id,
                annotator_id=annotation.completed_by_id,
                details={
                    'time': anomaly['time'],
                    'mean': anomaly['mean'],
                    'std': anomaly['std'],
                    'z_score': anomaly['z_score'],
                }
            )
        
        # Detect label distribution anomalies per annotator
        annotator_labels = defaultdict(list)
        for ann in annotations:
            label = extract_label({'result': ann.result})
            annotator_labels[ann.completed_by_id].append(label)
        
        # Compute overall label distribution
        all_labels = []
        for labels in annotator_labels.values():
            all_labels.extend(labels)
        
        overall_dist = defaultdict(int)
        for label in all_labels:
            overall_dist[label] += 1
        
        total_labels = len(all_labels)
        
        # Check each annotator's distribution
        distribution_anomalies = []
        for annotator_id, labels in annotator_labels.items():
            annotator_dist = defaultdict(int)
            for label in labels:
                annotator_dist[label] += 1
            
            # Compare with overall distribution
            max_diff = 0
            for label in overall_dist:
                overall_pct = overall_dist[label] / total_labels
                annotator_pct = annotator_dist.get(label, 0) / len(labels)
                diff = abs(overall_pct - annotator_pct)
                max_diff = max(max_diff, diff)
            
            if max_diff > 0.3:  # Threshold for distribution anomaly
                distribution_anomalies.append({
                    'annotator_id': annotator_id,
                    'max_difference': max_diff,
                    'label_count': len(labels),
                })
                
                self.add_issue(
                    issue_type='outlier',
                    severity='medium',
                    title=f'Label distribution anomaly for annotator {annotator_id}',
                    description=f'Max distribution difference: {max_diff:.2%}',
                    annotator_id=annotator_id,
                    details={
                        'max_difference': max_diff,
                        'annotator_distribution': dict(annotator_dist),
                        'overall_distribution': dict(overall_dist),
                    }
                )
        
        # Compute outlier score
        total_issues = len(speed_anomalies) + len(distribution_anomalies)
        total_annotations = len(annotations)
        
        outlier_rate = total_issues / total_annotations if total_annotations > 0 else 0
        outlier_score = max(0, 1.0 - outlier_rate)
        
        self.statistics = {
            'total_annotations': total_annotations,
            'speed_anomalies': len(speed_anomalies),
            'distribution_anomalies': len(distribution_anomalies),
            'total_outliers': total_issues,
            'outlier_rate': outlier_rate,
            'time_statistics': compute_annotation_time_statistics(annotations),
        }
        
        return AssessmentResult(
            assessor_name=self.name,
            score=outlier_score,
            statistics=self.statistics,
            issues=self.issues,
        )
```

### 5.7 创建 `assessors/bias.py`

```python
# label_studio/data_quality/assessors/bias.py
"""Bias assessor for detecting annotation biases."""

import logging
import numpy as np
from typing import Dict, List, Any
from collections import defaultdict

from data_quality.assessors.base import BaseAssessor, AssessmentResult
from data_quality.utils import extract_label, compute_label_distribution

logger = logging.getLogger(__name__)


class BiasAssessor(BaseAssessor):
    """
    Assessor for detecting annotation biases.
    
    Detects:
    - Label imbalance
    - Annotator bias towards specific labels
    - Systematic biases
    """
    
    @property
    def name(self) -> str:
        return 'bias'
    
    @property
    def description(self) -> str:
        return 'Detects annotation biases'
    
    def assess(self, include_details: bool = True) -> AssessmentResult:
        """
        Run bias assessment.
        
        Returns:
            AssessmentResult with bias score and issues
        """
        self.issues = []
        self.statistics = {}
        
        annotations = list(self.get_annotations())
        
        if not annotations:
            return AssessmentResult(
                assessor_name=self.name,
                score=1.0,
                statistics={'message': 'No annotations to assess'},
                issues=[],
            )
        
        # Compute overall label distribution
        all_labels = []
        annotator_labels = defaultdict(list)
        
        for ann in annotations:
            label = extract_label({'result': ann.result})
            all_labels.append(label)
            annotator_labels[ann.completed_by_id].append(label)
        
        label_dist = compute_label_distribution(annotations)
        total_annotations = len(all_labels)
        
        # Check for severe imbalance
        if label_dist:
            max_count = max(label_dist.values())
            min_count = min(label_dist.values())
            
            imbalance_ratio = max_count / min_count if min_count > 0 else float('inf')
            
            if imbalance_ratio > 10:
                dominant_label = max(label_dist.items(), key=lambda x: x[1])[0]
                
                self.add_issue(
                    issue_type='bias',
                    severity='high' if imbalance_ratio > 50 else 'medium',
                    title='Severe label imbalance detected',
                    description=(
                        f'Label "{dominant_label}" appears {imbalance_ratio:.1f}x '
                        f'more often than the least common label'
                    ),
                    details={
                        'imbalance_ratio': imbalance_ratio,
                        'label_distribution': label_dist,
                        'dominant_label': dominant_label,
                    }
                )
        
        # Check for annotator bias
        biased_annotators = []
        for annotator_id, labels in annotator_labels.items():
            annotator_dist = defaultdict(int)
            for label in labels:
                annotator_dist[label] += 1
            
            # Check if annotator has extreme preference
            if annotator_dist:
                max_label = max(annotator_dist.items(), key=lambda x: x[1])
                max_pct = max_label[1] / len(labels)
                
                if max_pct > 0.9 and len(labels) > 10:
                    biased_annotators.append({
                        'annotator_id': annotator_id,
                        'preferred_label': max_label[0],
                        'percentage': max_pct,
                        'total_annotations': len(labels),
                    })
                    
                    self.add_issue(
                        issue_type='bias',
                        severity='medium',
                        title=f'Annotator {annotator_id} shows label bias',
                        description=(
                            f'Annotator uses label "{max_label[0]}" for '
                            f'{max_pct:.1%} of annotations'
                        ),
                        annotator_id=annotator_id,
                        details={
                            'preferred_label': max_label[0],
                            'percentage': max_pct,
                            'distribution': dict(annotator_dist),
                        }
                    )
        
        # Compute bias score
        bias_issues = len(biased_annotators)
        if imbalance_ratio > 10:
            bias_issues += 1
        
        bias_rate = bias_issues / (len(annotator_labels) + 1) if annotator_labels else 0
        bias_score = max(0, 1.0 - bias_rate)
        
        self.statistics = {
            'total_annotations': total_annotations,
            'unique_labels': len(label_dist),
            'label_distribution': label_dist,
            'imbalance_ratio': imbalance_ratio if label_dist else 1.0,
            'biased_annotators': len(biased_annotators),
            'annotator_count': len(annotator_labels),
        }
        
        if include_details:
            self.statistics['biased_annotator_details'] = biased_annotators[:10]
        
        return AssessmentResult(
            assessor_name=self.name,
            score=bias_score,
            statistics=self.statistics,
            issues=self.issues,
        )
```

### 5.8 创建 `assessors/completeness.py`

```python
# label_studio/data_quality/assessors/completeness.py
"""Completeness assessor for checking annotation coverage."""

import logging
from typing import Dict, List, Any

from data_quality.assessors.base import BaseAssessor, AssessmentResult

logger = logging.getLogger(__name__)


class CompletenessAssessor(BaseAssessor):
    """
    Assessor for annotation completeness.
    
    Checks:
    - Task coverage (how many tasks are annotated)
    - Annotation density (annotations per task)
    - Missing annotations
    """
    
    @property
    def name(self) -> str:
        return 'completeness'
    
    @property
    def description(self) -> str:
        return 'Assesses annotation completeness'
    
    def assess(self, include_details: bool = True) -> AssessmentResult:
        """
        Run completeness assessment.
        
        Returns:
            AssessmentResult with completeness score and issues
        """
        self.issues = []
        self.statistics = {}
        
        tasks = self.get_tasks()
        total_tasks = tasks.count()
        
        if total_tasks == 0:
            return AssessmentResult(
                assessor_name=self.name,
                score=1.0,
                statistics={'message': 'No tasks to assess'},
                issues=[],
            )
        
        # Count annotated tasks
        annotated_tasks = tasks.filter(total_annotations__gt=0).count()
        unannotated_tasks = total_tasks - annotated_tasks
        
        # Compute coverage
        coverage = annotated_tasks / total_tasks if total_tasks > 0 else 0
        
        # Check for low coverage
        if coverage < 0.5:
            self.add_issue(
                issue_type='missing',
                severity='high' if coverage < 0.2 else 'medium',
                title='Low annotation coverage',
                description=f'Only {coverage:.1%} of tasks have annotations',
                details={
                    'total_tasks': total_tasks,
                    'annotated_tasks': annotated_tasks,
                    'unannotated_tasks': unannotated_tasks,
                    'coverage': coverage,
                }
            )
        
        # Check annotation density
        from tasks.models import Annotation
        total_annotations = Annotation.objects.filter(
            task__project=self.project,
            was_cancelled=False
        ).count()
        
        avg_annotations_per_task = total_annotations / annotated_tasks if annotated_tasks > 0 else 0
        
        # Check for tasks with insufficient annotations
        project = self.project
        expected_overlap = getattr(project, 'maximum_annotations', 1)
        
        insufficient_tasks = tasks.filter(
            total_annotations__gt=0,
            total_annotations__lt=expected_overlap
        ).count()
        
        if insufficient_tasks > 0:
            insufficient_rate = insufficient_tasks / annotated_tasks if annotated_tasks > 0 else 0
            
            self.add_issue(
                issue_type='missing',
                severity='medium' if insufficient_rate > 0.3 else 'low',
                title=f'{insufficient_tasks} tasks have insufficient annotations',
                description=(
                    f'{insufficient_rate:.1%} of annotated tasks have fewer '
                    f'than the expected {expected_overlap} annotations'
                ),
                details={
                    'insufficient_tasks': insufficient_tasks,
                    'expected_overlap': expected_overlap,
                    'insufficient_rate': insufficient_rate,
                }
            )
        
        # Compute completeness score
        completeness_score = coverage * 0.7 + min(1.0, avg_annotations_per_task / expected_overlap) * 0.3
        
        self.statistics = {
            'total_tasks': total_tasks,
            'annotated_tasks': annotated_tasks,
            'unannotated_tasks': unannotated_tasks,
            'coverage': coverage,
            'total_annotations': total_annotations,
            'avg_annotations_per_task': avg_annotations_per_task,
            'expected_overlap': expected_overlap,
            'insufficient_tasks': insufficient_tasks,
        }
        
        return AssessmentResult(
            assessor_name=self.name,
            score=completeness_score,
            statistics=self.statistics,
            issues=self.issues,
        )
```

### 5.9 创建 `reporters/__init__.py`

```python
# label_studio/data_quality/reporters/__init__.py
"""Report generators for Data Quality module."""

from data_quality.reporters.quality_report import QualityReportGenerator

__all__ = ['QualityReportGenerator']
```

### 5.10 创建 `reporters/quality_report.py`

```python
# label_studio/data_quality/reporters/quality_report.py
"""Quality report generator."""

import logging
from typing import Dict, Any, List
from datetime import timedelta
from django.utils.timezone import now
from django.db.models import Count, Avg, Q

from data_quality.models import (
    QualityReport,
    QualityIssue,
    AnnotatorQualityProfile,
    LabelQualityStats,
)
from tasks.models import Task, Annotation

logger = logging.getLogger(__name__)


class QualityReportGenerator:
    """
    Generator for quality reports.
    
    Generates comprehensive quality reports with statistics and visualizations.
    """
    
    def __init__(self, project):
        """
        Initialize generator.
        
        Args:
            project: Project instance
        """
        self.project = project
    
    def generate_summary(self) -> Dict[str, Any]:
        """
        Generate quality summary.
        
        Returns:
            Dictionary with summary data
        """
        # Get latest report
        latest_report = QualityReport.objects.filter(
            project=self.project
        ).order_by('-created_at').first()
        
        if not latest_report:
            return {
                'has_report': False,
                'message': 'No quality reports available',
            }
        
        # Get issue counts
        issue_counts = QualityIssue.objects.filter(
            report=latest_report
        ).values('severity').annotate(count=Count('id'))
        
        issue_stats = {item['severity']: item['count'] for item in issue_counts}
        
        # Get recent trend
        recent_reports = QualityReport.objects.filter(
            project=self.project
        ).order_by('-created_at')[:10]
        
        score_trend = [
            {
                'date': report.created_at.isoformat(),
                'score': report.overall_score,
            }
            for report in recent_reports
        ]
        
        return {
            'has_report': True,
            'project_id': self.project.id,
            'project_title': self.project.title,
            'overall_score': latest_report.overall_score,
            'consistency_score': latest_report.consistency_score,
            'agreement_score': latest_report.agreement_score,
            'completeness_score': latest_report.completeness_score,
            'issue_stats': issue_stats,
            'total_issues': latest_report.issue_count,
            'critical_issues': latest_report.critical_issue_count,
            'tasks_analyzed': latest_report.tasks_analyzed,
            'annotations_analyzed': latest_report.annotations_analyzed,
            'annotators_analyzed': latest_report.annotators_analyzed,
            'score_trend': score_trend,
            'last_updated': latest_report.created_at.isoformat(),
        }
    
    def generate_annotator_report(self, user_id: int) -> Dict[str, Any]:
        """
        Generate report for a specific annotator.
        
        Args:
            user_id: User ID
        
        Returns:
            Dictionary with annotator report
        """
        profile = AnnotatorQualityProfile.objects.filter(
            user_id=user_id,
            project=self.project
        ).first()
        
        if not profile:
            return {
                'has_profile': False,
                'message': 'No quality profile available',
            }
        
        # Get annotator's issues
        issues = QualityIssue.objects.filter(
            report__project=self.project,
            annotator_id=user_id
        ).order_by('-created_at')[:20]
        
        # Get annotation statistics
        annotations = Annotation.objects.filter(
            task__project=self.project,
            completed_by_id=user_id,
            was_cancelled=False
        )
        
        total_annotations = annotations.count()
        
        # Time statistics
        from data_quality.utils import compute_annotation_time_statistics
        time_stats = compute_annotation_time_statistics(list(annotations))
        
        return {
            'has_profile': True,
            'user_id': user_id,
            'username': profile.user.username,
            'quality_score': profile.quality_score,
            'agreement_rate': profile.agreement_rate,
            'consistency_score': profile.consistency_score,
            'total_annotations': profile.total_annotations,
            'avg_annotation_time': profile.avg_annotation_time,
            'issue_count': profile.issue_count,
            'critical_issue_count': profile.critical_issue_count,
            'time_statistics': time_stats,
            'recent_issues': [
                {
                    'type': issue.issue_type,
                    'severity': issue.severity,
                    'title': issue.title,
                    'created_at': issue.created_at.isoformat(),
                }
                for issue in issues
            ],
            'first_annotation': profile.first_annotation_at.isoformat() if profile.first_annotation_at else None,
            'last_annotation': profile.last_annotation_at.isoformat() if profile.last_annotation_at else None,
        }
    
    def generate_label_report(self) -> List[Dict[str, Any]]:
        """
        Generate report for labels.
        
        Returns:
            List of label statistics
        """
        label_stats = LabelQualityStats.objects.filter(
            project=self.project
        ).order_by('-usage_count')
        
        return [
            {
                'label_name': stat.label_name,
                'label_type': stat.label_type,
                'usage_count': stat.usage_count,
                'usage_percentage': stat.usage_percentage,
                'unique_annotators': stat.unique_annotators,
                'agreement_rate': stat.agreement_rate,
                'consistency_score': stat.consistency_score,
            }
            for stat in label_stats
        ]
    
    def generate_comparison_report(self, days: int = 30) -> Dict[str, Any]:
        """
        Generate comparison report over time.
        
        Args:
            days: Number of days to compare
        
        Returns:
            Dictionary with comparison data
        """
        cutoff = now() - timedelta(days=days)
        
        # Get reports
        recent_reports = QualityReport.objects.filter(
            project=self.project,
            created_at__gte=cutoff
        ).order_by('created_at')
        
        if recent_reports.count() < 2:
            return {
                'has_comparison': False,
                'message': 'Not enough reports for comparison',
            }
        
        first_report = recent_reports.first()
        last_report = recent_reports.last()
        
        # Compute changes
        score_change = last_report.overall_score - first_report.overall_score
        issue_change = last_report.issue_count - first_report.issue_count
        
        return {
            'has_comparison': True,
            'period_days': days,
            'report_count': recent_reports.count(),
            'score_change': score_change,
            'issue_change': issue_change,
            'current_score': last_report.overall_score,
            'previous_score': first_report.overall_score,
            'current_issues': last_report.issue_count,
            'previous_issues': first_report.issue_count,
            'trend': 'improving' if score_change > 0 else 'declining' if score_change < 0 else 'stable',
        }
```

## 验证检查点

- [ ] 所有评估器文件创建成功
- [ ] QualityAssessmentEngine正常工作
- [ ] 各评估器的assess方法返回正确格式
- [ ] 质量问题正确记录到数据库
- [ ] 报告生成功能正常

## 下一步

执行 `06_drift_detection_backend.md` 创建漂移检测后端模块。
