"""
Tests for Data Quality module.
"""

import unittest

from backend.data_quality.assessors.consistency import ConsistencyAssessor
from backend.data_quality.assessors.completeness import CompletenessAssessor
from backend.data_quality.assessors.engine import QualityAssessmentEngine


class TestConsistencyAssessor(unittest.TestCase):
    """Tests for Consistency Assessor."""
    
    def setUp(self):
        self.assessor = ConsistencyAssessor(project_id=1)
    
    def test_consistent_annotations(self):
        """Test with consistent annotations."""
        tasks = [{'id': 1, 'data': {'text': 'hello'}}]
        annotations = [
            {'id': 1, 'task_id': 1, 'annotator_id': 1, 'result': [{'value': {'choices': ['positive']}}]},
            {'id': 2, 'task_id': 1, 'annotator_id': 2, 'result': [{'value': {'choices': ['positive']}}]},
        ]
        
        result = self.assessor.assess(tasks, annotations)
        
        self.assertEqual(result.score, 1.0)
        self.assertEqual(len(result.issues), 0)
    
    def test_inconsistent_annotations(self):
        """Test with inconsistent annotations."""
        tasks = [{'id': 1, 'data': {'text': 'hello'}}]
        annotations = [
            {'id': 1, 'task_id': 1, 'annotator_id': 1, 'result': [{'value': {'choices': ['positive']}}]},
            {'id': 2, 'task_id': 1, 'annotator_id': 2, 'result': [{'value': {'choices': ['negative']}}]},
        ]
        
        result = self.assessor.assess(tasks, annotations)
        
        self.assertLess(result.score, 1.0)
        self.assertGreater(len(result.issues), 0)


class TestCompletenessAssessor(unittest.TestCase):
    """Tests for Completeness Assessor."""
    
    def setUp(self):
        self.assessor = CompletenessAssessor(project_id=1)
    
    def test_complete_coverage(self):
        """Test with complete coverage."""
        tasks = [
            {'id': 1, 'data': {}},
            {'id': 2, 'data': {}},
        ]
        annotations = [
            {'id': 1, 'task_id': 1, 'annotator_id': 1, 'result': [{'value': {'choices': ['positive']}}]},
            {'id': 2, 'task_id': 2, 'annotator_id': 1, 'result': [{'value': {'choices': ['negative']}}]},
        ]
        
        result = self.assessor.assess(tasks, annotations)
        
        self.assertGreater(result.score, 0.8)
    
    def test_incomplete_coverage(self):
        """Test with incomplete coverage."""
        tasks = [
            {'id': 1, 'data': {}},
            {'id': 2, 'data': {}},
            {'id': 3, 'data': {}},
        ]
        annotations = [
            {'id': 1, 'task_id': 1, 'annotator_id': 1, 'result': [{'value': {'choices': ['positive']}}]},
        ]
        
        result = self.assessor.assess(tasks, annotations)
        
        self.assertLess(result.score, 0.5)


class TestQualityAssessmentEngine(unittest.TestCase):
    """Tests for Quality Assessment Engine."""
    
    def setUp(self):
        self.engine = QualityAssessmentEngine(project_id=1)
    
    def test_run_assessment(self):
        """Test running full assessment."""
        tasks = [
            {'id': 1, 'data': {}},
            {'id': 2, 'data': {}},
        ]
        annotations = [
            {'id': 1, 'task_id': 1, 'annotator_id': 1, 'result': [{'value': {'choices': ['positive']}}]},
            {'id': 2, 'task_id': 2, 'annotator_id': 1, 'result': [{'value': {'choices': ['negative']}}]},
        ]
        
        report = self.engine.run_assessment(tasks, annotations)
        
        self.assertIsNotNone(report)
        self.assertGreater(report.overall_score, 0)
        self.assertEqual(report.tasks_analyzed, 2)
        self.assertEqual(report.annotations_analyzed, 2)


if __name__ == '__main__':
    unittest.main()
