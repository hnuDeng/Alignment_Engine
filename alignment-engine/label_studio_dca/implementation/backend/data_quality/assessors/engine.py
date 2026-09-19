"""
Data Quality Assessment Engine

Comprehensive data quality assessment system for annotation data.
Provides multiple assessment dimensions including:
- Consistency: Measures agreement between annotators
- Completeness: Measures coverage of annotations
- Accuracy: Measures correctness against ground truth
- Timeliness: Measures annotation freshness
- Validity: Measures adherence to annotation guidelines

This module implements the core quality assessment logic used by
the data quality API endpoints.
"""

import logging
import numpy as np
from typing import List, Dict, Tuple, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from scipy import stats
from sklearn.metrics import cohen_kappa_score, f1_score
import warnings

warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)


class QualityDimension(Enum):
    """Enumeration of quality dimensions."""
    CONSISTENCY = "consistency"
    COMPLETENESS = "completeness"
    ACCURACY = "accuracy"
    TIMELINESS = "timeliness"
    VALIDITY = "validity"
    AGREEMENT = "agreement"


@dataclass
class QualityScore:
    """Data class for quality scores."""
    dimension: QualityDimension
    score: float  # 0.0 to 1.0
    details: Dict[str, Any]
    issues: List[str]
    recommendations: List[str]


@dataclass
class AnnotationQualityReport:
    """Comprehensive quality report for annotations."""
    project_id: int
    timestamp: datetime
    overall_score: float
    dimension_scores: Dict[QualityDimension, QualityScore]
    annotator_scores: Dict[int, Dict[str, float]]
    task_scores: Dict[int, Dict[str, float]]
    issues: List[Dict[str, Any]]
    recommendations: List[str]


class ConsistencyAssessor:
    """
    Assesses annotation consistency across annotators and time.
    
    Consistency measures whether annotators produce similar annotations
    for similar items, and whether individual annotators are consistent
    over time.
    """
    
    def __init__(self, agreement_threshold: float = 0.7):
        """
        Initialize consistency assessor.
        
        Args:
            agreement_threshold: Minimum agreement score to consider consistent
        """
        self.agreement_threshold = agreement_threshold
    
    def compute_inter_annotator_agreement(
        self,
        annotations: Dict[int, Dict[int, List[str]]]
    ) -> Dict[str, float]:
        """
        Compute inter-annotator agreement metrics.
        
        Args:
            annotations: Nested dict: task_id -> annotator_id -> labels
        
        Returns:
            Dictionary of agreement metrics
        """
        if len(annotations) == 0:
            return {'kappa': 0.0, 'fleiss_kappa': 0.0, 'percent_agreement': 0.0}
        
        # Get all annotators
        all_annotators = set()
        for task_annotations in annotations.values():
            all_annotators.update(task_annotations.keys())
        
        annotators = sorted(all_annotators)
        
        if len(annotators) < 2:
            return {'kappa': 1.0, 'fleiss_kappa': 1.0, 'percent_agreement': 1.0}
        
        # Compute pairwise Cohen's Kappa
        kappa_scores = []
        for i in range(len(annotators)):
            for j in range(i + 1, len(annotators)):
                ann1_labels = []
                ann2_labels = []
                
                for task_id, task_anns in annotations.items():
                    if annotators[i] in task_anns and annotators[j] in task_anns:
                        # Use first label for simplicity
                        label1 = task_anns[annotators[i]][0] if task_anns[annotators[i]] else 'none'
                        label2 = task_anns[annotators[j]][0] if task_anns[annotators[j]] else 'none'
                        ann1_labels.append(label1)
                        ann2_labels.append(label2)
                
                if len(ann1_labels) > 0:
                    try:
                        kappa = cohen_kappa_score(ann1_labels, ann2_labels)
                        kappa_scores.append(kappa)
                    except:
                        kappa_scores.append(0.0)
        
        avg_kappa = np.mean(kappa_scores) if kappa_scores else 0.0
        
        # Compute percent agreement
        agreements = 0
        total = 0
        for task_id, task_anns in annotations.items():
            if len(task_anns) >= 2:
                labels = list(task_anns.values())
                # Check if all annotators agree
                first_label = labels[0][0] if labels[0] else None
                if all(l[0] == first_label for l in labels if l):
                    agreements += 1
                total += 1
        
        percent_agreement = agreements / total if total > 0 else 0.0
        
        return {
            'kappa': float(avg_kappa),
            'percent_agreement': float(percent_agreement),
            'num_annotators': len(annotators),
            'num_tasks': len(annotations)
        }
    
    def compute_intra_annotator_consistency(
        self,
        annotator_annotations: Dict[int, List[Tuple[str, str]]]
    ) -> Dict[int, float]:
        """
        Compute intra-annotator consistency (self-agreement).
        
        Args:
            annotator_annotations: Dict of annotator_id -> list of (label, timestamp)
        
        Returns:
            Dictionary of annotator_id -> consistency score
        """
        consistency_scores = {}
        
        for annotator_id, annotations in annotator_annotations.items():
            if len(annotations) < 2:
                consistency_scores[annotator_id] = 1.0
                continue
            
            # Group by label and check temporal patterns
            label_sequence = [a[0] for a in annotations]
            
            # Compute consistency as inverse of label changes
            changes = sum(1 for i in range(1, len(label_sequence))
                         if label_sequence[i] != label_sequence[i-1])
            max_changes = len(label_sequence) - 1
            
            if max_changes > 0:
                consistency = 1.0 - (changes / max_changes)
            else:
                consistency = 1.0
            
            consistency_scores[annotator_id] = float(consistency)
        
        return consistency_scores
    
    def assess(
        self,
        annotations: Dict[int, Dict[int, List[str]]]
    ) -> QualityScore:
        """
        Run consistency assessment.
        
        Args:
            annotations: Annotation data
        
        Returns:
            QualityScore for consistency
        """
        iaa = self.compute_inter_annotator_agreement(annotations)
        
        issues = []
        recommendations = []
        
        if iaa['kappa'] < self.agreement_threshold:
            issues.append(f"Low inter-annotator agreement (kappa={iaa['kappa']:.2f})")
            recommendations.append("Review annotation guidelines for clarity")
            recommendations.append("Consider additional annotator training")
        
        score = iaa['kappa']
        
        return QualityScore(
            dimension=QualityDimension.CONSISTENCY,
            score=float(np.clip(score, 0, 1)),
            details=iaa,
            issues=issues,
            recommendations=recommendations
        )


class CompletenessAssessor:
    """
    Assesses annotation completeness.
    
    Completeness measures whether all required annotations are present
    and whether the annotation coverage meets project requirements.
    """
    
    def __init__(self, required_coverage: float = 0.95):
        """
        Initialize completeness assessor.
        
        Args:
            required_coverage: Required coverage percentage
        """
        self.required_coverage = required_coverage
    
    def compute_coverage(
        self,
        total_tasks: int,
        annotated_tasks: int,
        required_annotations_per_task: int,
        actual_annotations: Dict[int, int]
    ) -> Dict[str, float]:
        """
        Compute annotation coverage metrics.
        
        Args:
            total_tasks: Total number of tasks
            annotated_tasks: Number of annotated tasks
            required_annotations_per_task: Required annotations per task
            actual_annotations: Dict of task_id -> actual annotation count
        
        Returns:
            Dictionary of coverage metrics
        """
        # Task coverage
        task_coverage = annotated_tasks / total_tasks if total_tasks > 0 else 0.0
        
        # Annotation coverage per task
        annotation_coverages = []
        for task_id, count in actual_annotations.items():
            coverage = min(count / required_annotations_per_task, 1.0)
            annotation_coverages.append(coverage)
        
        avg_annotation_coverage = np.mean(annotation_coverages) if annotation_coverages else 0.0
        
        # Fully annotated tasks
        fully_annotated = sum(1 for c in actual_annotations.values()
                            if c >= required_annotations_per_task)
        full_coverage_rate = fully_annotated / total_tasks if total_tasks > 0 else 0.0
        
        return {
            'task_coverage': float(task_coverage),
            'avg_annotation_coverage': float(avg_annotation_coverage),
            'full_coverage_rate': float(full_coverage_rate),
            'total_tasks': total_tasks,
            'annotated_tasks': annotated_tasks,
            'fully_annotated': fully_annotated
        }
    
    def assess(
        self,
        total_tasks: int,
        annotated_tasks: int,
        required_annotations_per_task: int,
        actual_annotations: Dict[int, int]
    ) -> QualityScore:
        """
        Run completeness assessment.
        
        Returns:
            QualityScore for completeness
        """
        coverage = self.compute_coverage(
            total_tasks, annotated_tasks,
            required_annotations_per_task, actual_annotations
        )
        
        issues = []
        recommendations = []
        
        if coverage['task_coverage'] < self.required_coverage:
            issues.append(f"Low task coverage ({coverage['task_coverage']:.1%})")
            recommendations.append("Prioritize annotation of remaining tasks")
        
        if coverage['full_coverage_rate'] < 0.8:
            issues.append(f"Only {coverage['full_coverage_rate']:.1%} of tasks are fully annotated")
            recommendations.append("Increase annotations per task for better quality")
        
        score = (coverage['task_coverage'] + coverage['avg_annotation_coverage']) / 2
        
        return QualityScore(
            dimension=QualityDimension.COMPLETENESS,
            score=float(np.clip(score, 0, 1)),
            details=coverage,
            issues=issues,
            recommendations=recommendations
        )


class AccuracyAssessor:
    """
    Assesses annotation accuracy against ground truth.
    
    Accuracy measures how well annotations match a reference standard
    or ground truth labels.
    """
    
    def __init__(self, metric: str = 'f1'):
        """
        Initialize accuracy assessor.
        
        Args:
            metric: Accuracy metric to use ('f1', 'precision', 'recall', 'exact_match')
        """
        self.metric = metric
    
    def compute_accuracy(
        self,
        predicted: List[str],
        ground_truth: List[str]
    ) -> Dict[str, float]:
        """
        Compute accuracy metrics.
        
        Args:
            predicted: Predicted/annotated labels
            ground_truth: Ground truth labels
        
        Returns:
            Dictionary of accuracy metrics
        """
        if len(predicted) != len(ground_truth):
            raise ValueError("Predicted and ground truth must have same length")
        
        if len(predicted) == 0:
            return {'f1': 0.0, 'precision': 0.0, 'recall': 0.0, 'exact_match': 0.0}
        
        # Exact match
        exact_match = sum(1 for p, g in zip(predicted, ground_truth) if p == g) / len(predicted)
        
        # Get unique labels
        all_labels = sorted(set(predicted + ground_truth))
        
        # Compute F1, precision, recall for each label
        f1_scores = []
        precision_scores = []
        recall_scores = []
        
        for label in all_labels:
            tp = sum(1 for p, g in zip(predicted, ground_truth) if p == label and g == label)
            fp = sum(1 for p, g in zip(predicted, ground_truth) if p == label and g != label)
            fn = sum(1 for p, g in zip(predicted, ground_truth) if p != label and g == label)
            
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
            
            precision_scores.append(precision)
            recall_scores.append(recall)
            f1_scores.append(f1)
        
        return {
            'f1': float(np.mean(f1_scores)),
            'precision': float(np.mean(precision_scores)),
            'recall': float(np.mean(recall_scores)),
            'exact_match': float(exact_match)
        }
    
    def assess(
        self,
        predicted: List[str],
        ground_truth: List[str]
    ) -> QualityScore:
        """
        Run accuracy assessment.
        
        Returns:
            QualityScore for accuracy
        """
        accuracy = self.compute_accuracy(predicted, ground_truth)
        
        issues = []
        recommendations = []
        
        score = accuracy.get(self.metric, accuracy['f1'])
        
        if score < 0.7:
            issues.append(f"Low {self.metric} score ({score:.2f})")
            recommendations.append("Review annotation guidelines")
            recommendations.append("Consider additional annotator training")
        
        return QualityScore(
            dimension=QualityDimension.ACCURACY,
            score=float(np.clip(score, 0, 1)),
            details=accuracy,
            issues=issues,
            recommendations=recommendations
        )


class TimelinessAssessor:
    """
    Assesses annotation timeliness.
    
    Timeliness measures how quickly annotations are completed
    and whether they are kept up-to-date.
    """
    
    def __init__(self, max_delay_hours: float = 24.0):
        """
        Initialize timeliness assessor.
        
        Args:
            max_delay_hours: Maximum acceptable delay in hours
        """
        self.max_delay_hours = max_delay_hours
    
    def compute_timeliness(
        self,
        task_creation_times: Dict[int, datetime],
        annotation_times: Dict[int, List[datetime]]
    ) -> Dict[str, float]:
        """
        Compute timeliness metrics.
        
        Args:
            task_creation_times: Dict of task_id -> creation time
            annotation_times: Dict of task_id -> list of annotation times
        
        Returns:
            Dictionary of timeliness metrics
        """
        delays = []
        
        for task_id, creation_time in task_creation_times.items():
            if task_id in annotation_times and annotation_times[task_id]:
                first_annotation = min(annotation_times[task_id])
                delay = (first_annotation - creation_time).total_seconds() / 3600
                delays.append(delay)
        
        if not delays:
            return {
                'avg_delay_hours': 0.0,
                'max_delay_hours': 0.0,
                'on_time_rate': 0.0
            }
        
        avg_delay = np.mean(delays)
        max_delay = np.max(delays)
        on_time = sum(1 for d in delays if d <= self.max_delay_hours)
        on_time_rate = on_time / len(delays)
        
        return {
            'avg_delay_hours': float(avg_delay),
            'max_delay_hours': float(max_delay),
            'on_time_rate': float(on_time_rate),
            'num_tasks': len(delays)
        }
    
    def assess(
        self,
        task_creation_times: Dict[int, datetime],
        annotation_times: Dict[int, List[datetime]]
    ) -> QualityScore:
        """
        Run timeliness assessment.
        
        Returns:
            QualityScore for timeliness
        """
        timeliness = self.compute_timeliness(task_creation_times, annotation_times)
        
        issues = []
        recommendations = []
        
        if timeliness['on_time_rate'] < 0.8:
            issues.append(f"Low on-time rate ({timeliness['on_time_rate']:.1%})")
            recommendations.append("Set up annotation deadlines and reminders")
        
        score = timeliness['on_time_rate']
        
        return QualityScore(
            dimension=QualityDimension.TIMELINESS,
            score=float(np.clip(score, 0, 1)),
            details=timeliness,
            issues=issues,
            recommendations=recommendations
        )


class DataQualityEngine:
    """
    Main data quality assessment engine.
    
    Coordinates multiple quality assessors to produce comprehensive
    quality reports.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize quality engine.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        
        # Initialize assessors
        self.consistency_assessor = ConsistencyAssessor(
            agreement_threshold=self.config.get('agreement_threshold', 0.7)
        )
        self.completeness_assessor = CompletenessAssessor(
            required_coverage=self.config.get('required_coverage', 0.95)
        )
        self.accuracy_assessor = AccuracyAssessor(
            metric=self.config.get('accuracy_metric', 'f1')
        )
        self.timeliness_assessor = TimelinessAssessor(
            max_delay_hours=self.config.get('max_delay_hours', 24.0)
        )
    
    def assess_project(
        self,
        project_id: int,
        annotations: Dict[int, Dict[int, List[str]]],
        total_tasks: int,
        required_annotations_per_task: int,
        ground_truth: Optional[Dict[int, str]] = None,
        task_creation_times: Optional[Dict[int, datetime]] = None
    ) -> AnnotationQualityReport:
        """
        Run comprehensive quality assessment for a project.
        
        Args:
            project_id: Project ID
            annotations: Annotation data
            total_tasks: Total number of tasks
            required_annotations_per_task: Required annotations per task
            ground_truth: Ground truth labels (optional)
            task_creation_times: Task creation times (optional)
        
        Returns:
            AnnotationQualityReport
        """
        dimension_scores = {}
        all_issues = []
        all_recommendations = []
        
        # Consistency assessment
        consistency_score = self.consistency_assessor.assess(annotations)
        dimension_scores[QualityDimension.CONSISTENCY] = consistency_score
        all_issues.extend(consistency_score.issues)
        all_recommendations.extend(consistency_score.recommendations)
        
        # Completeness assessment
        annotated_tasks = len(annotations)
        actual_annotations = {
            task_id: sum(len(labels) for labels in task_anns.values())
            for task_id, task_anns in annotations.items()
        }
        completeness_score = self.completeness_assessor.assess(
            total_tasks, annotated_tasks,
            required_annotations_per_task, actual_annotations
        )
        dimension_scores[QualityDimension.COMPLETENESS] = completeness_score
        all_issues.extend(completeness_score.issues)
        all_recommendations.extend(completeness_score.recommendations)
        
        # Accuracy assessment (if ground truth provided)
        if ground_truth:
            predicted = []
            truth = []
            for task_id, gt_label in ground_truth.items():
                if task_id in annotations:
                    # Use majority vote as prediction
                    all_labels = []
                    for ann_labels in annotations[task_id].values():
                        all_labels.extend(ann_labels)
                    if all_labels:
                        majority = Counter(all_labels).most_common(1)[0][0]
                        predicted.append(majority)
                        truth.append(gt_label)
            
            if predicted:
                accuracy_score = self.accuracy_assessor.assess(predicted, truth)
                dimension_scores[QualityDimension.ACCURACY] = accuracy_score
                all_issues.extend(accuracy_score.issues)
                all_recommendations.extend(accuracy_score.recommendations)
        
        # Timeliness assessment (if creation times provided)
        if task_creation_times:
            annotation_times = {}  # Would need actual annotation timestamps
            timeliness_score = self.timeliness_assessor.assess(
                task_creation_times, annotation_times
            )
            dimension_scores[QualityDimension.TIMELINESS] = timeliness_score
            all_issues.extend(timeliness_score.issues)
            all_recommendations.extend(timeliness_score.recommendations)
        
        # Compute overall score
        scores = [s.score for s in dimension_scores.values()]
        overall_score = np.mean(scores) if scores else 0.0
        
        # Compute per-annotator scores
        annotator_scores = self._compute_annotator_scores(annotations)
        
        # Compute per-task scores
        task_scores = self._compute_task_scores(annotations, required_annotations_per_task)
        
        return AnnotationQualityReport(
            project_id=project_id,
            timestamp=datetime.now(),
            overall_score=float(overall_score),
            dimension_scores=dimension_scores,
            annotator_scores=annotator_scores,
            task_scores=task_scores,
            issues=[{'message': issue, 'severity': 'warning'} for issue in all_issues],
            recommendations=list(set(all_recommendations))
        )
    
    def _compute_annotator_scores(
        self,
        annotations: Dict[int, Dict[int, List[str]]]
    ) -> Dict[int, Dict[str, float]]:
        """Compute quality scores per annotator."""
        annotator_scores = defaultdict(lambda: {'count': 0, 'agreement': 0.0})
        
        for task_id, task_anns in annotations.items():
            for annotator_id, labels in task_anns.items():
                annotator_scores[annotator_id]['count'] += len(labels)
        
        return dict(annotator_scores)
    
    def _compute_task_scores(
        self,
        annotations: Dict[int, Dict[int, List[str]]],
        required_per_task: int
    ) -> Dict[int, Dict[str, float]]:
        """Compute quality scores per task."""
        task_scores = {}
        
        for task_id, task_anns in annotations.items():
            total_labels = sum(len(labels) for labels in task_anns.values())
            num_annotators = len(task_anns)
            
            task_scores[task_id] = {
                'annotation_count': total_labels,
                'annotator_count': num_annotators,
                'completeness': min(total_labels / required_per_task, 1.0) if required_per_task > 0 else 1.0
            }
        
        return task_scores
