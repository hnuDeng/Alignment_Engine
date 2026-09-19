"""
Tests for Active Learning module.
"""

import unittest
import numpy as np

from backend.active_learning.models import (
    ActiveLearningConfig,
    TaskData,
    StrategyType,
    UncertaintyMethod,
)
from backend.active_learning.strategies import get_strategy
from backend.active_learning.selectors import TaskSelector


class TestUncertaintySampling(unittest.TestCase):
    """Tests for Uncertainty Sampling strategy."""
    
    def setUp(self):
        self.strategy = get_strategy('uncertainty', method='entropy')
    
    def test_compute_uncertainty_uniform(self):
        """Test uncertainty for uniform distribution."""
        probs = np.array([0.5, 0.5])
        uncertainty = self.strategy.compute_uncertainty(probs)
        self.assertAlmostEqual(uncertainty, 1.0, places=2)
    
    def test_compute_uncertainty_certain(self):
        """Test uncertainty for certain prediction."""
        probs = np.array([1.0, 0.0])
        uncertainty = self.strategy.compute_uncertainty(probs)
        self.assertAlmostEqual(uncertainty, 0.0, places=2)
    
    def test_compute_scores(self):
        """Test computing scores for multiple tasks."""
        tasks = [
            {'id': 1, 'data': {}},
            {'id': 2, 'data': {}},
            {'id': 3, 'data': {}},
        ]
        
        predictions = {
            1: [{'result': [{'value': {'choices': {'A': 0.9, 'B': 0.1}}}]}],
            2: [{'result': [{'value': {'choices': {'A': 0.5, 'B': 0.5}}}]}],
            3: [{'result': [{'value': {'choices': {'A': 0.7, 'B': 0.3}}}]}],
        }
        
        scores = self.strategy.compute_scores(tasks, predictions)
        
        self.assertIn(1, scores)
        self.assertIn(2, scores)
        self.assertIn(3, scores)
        
        # Task 2 should have highest uncertainty
        self.assertGreater(scores[2], scores[1])
    
    def test_select(self):
        """Test selecting tasks."""
        tasks = [
            {'id': 1, 'data': {}},
            {'id': 2, 'data': {}},
            {'id': 3, 'data': {}},
        ]
        
        predictions = {
            1: [{'result': [{'value': {'choices': {'A': 0.9, 'B': 0.1}}}]}],
            2: [{'result': [{'value': {'choices': {'A': 0.5, 'B': 0.5}}}]}],
            3: [{'result': [{'value': {'choices': {'A': 0.7, 'B': 0.3}}}]}],
        }
        
        selected, scores = self.strategy.select(tasks, predictions, batch_size=2)
        
        self.assertEqual(len(selected), 2)
        self.assertIn(2, selected)  # Most uncertain should be selected


class TestDiversitySampling(unittest.TestCase):
    """Tests for Diversity Sampling strategy."""
    
    def setUp(self):
        self.strategy = get_strategy('diversity', metric='euclidean')
    
    def test_select_diverse(self):
        """Test selecting diverse tasks."""
        tasks = [
            {'id': 1, 'data': {'x': 0.0, 'y': 0.0}},
            {'id': 2, 'data': {'x': 1.0, 'y': 0.0}},
            {'id': 3, 'data': {'x': 0.0, 'y': 1.0}},
            {'id': 4, 'data': {'x': 1.0, 'y': 1.0}},
        ]
        
        selected, scores = self.strategy.select(tasks, {}, batch_size=2)
        
        self.assertEqual(len(selected), 2)


class TestRandomSampling(unittest.TestCase):
    """Tests for Random Sampling strategy."""
    
    def test_select_random(self):
        """Test random selection."""
        strategy = get_strategy('random', seed=42)
        
        tasks = [
            {'id': i, 'data': {}} for i in range(10)
        ]
        
        selected, scores = strategy.select(tasks, {}, batch_size=3)
        
        self.assertEqual(len(selected), 3)
        self.assertTrue(all(0 <= s <= 1 for s in scores.values()))


class TestTaskSelector(unittest.TestCase):
    """Tests for TaskSelector."""
    
    def setUp(self):
        self.config = ActiveLearningConfig(
            id=1,
            project_id=1,
            strategy=StrategyType.UNCERTAINTY,
            batch_size=5,
            is_enabled=True,
        )
        self.selector = TaskSelector(self.config)
    
    def test_get_candidate_tasks(self):
        """Test getting candidate tasks."""
        tasks = [
            TaskData(id=1, data={'text': 'hello'}, is_labeled=False),
            TaskData(id=2, data={'text': 'world'}, is_labeled=True),
            TaskData(id=3, data={'text': 'foo'}, is_labeled=False),
        ]
        
        candidates = self.selector.get_candidate_tasks(tasks, exclude_annotated=True)
        
        self.assertEqual(len(candidates), 2)
        self.assertTrue(all(not t.is_labeled for t in candidates))
    
    def test_select_tasks(self):
        """Test selecting tasks."""
        tasks = [
            TaskData(id=i, data={'text': f'task {i}'}, is_labeled=False)
            for i in range(10)
        ]
        
        result = self.selector.select_tasks(tasks, batch_size=3)
        
        self.assertEqual(len(result.selected_task_ids), 3)
        self.assertGreater(result.avg_uncertainty, 0)


if __name__ == '__main__':
    unittest.main()
