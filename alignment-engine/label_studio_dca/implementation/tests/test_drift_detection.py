"""
Tests for Drift Detection module.
"""

import unittest
import numpy as np

from backend.drift_detection.detectors.statistical import (
    KSTestDetector,
    ChiSquareDetector,
    WassersteinDetector,
)
from backend.drift_detection.detectors.feature_drift import FeatureDriftDetector
from backend.drift_detection.detectors.label_drift import LabelDriftDetector


class TestKSTestDetector(unittest.TestCase):
    """Tests for KS Test Detector."""
    
    def setUp(self):
        self.detector = KSTestDetector(threshold=0.05)
    
    def test_no_drift(self):
        """Test detection with no drift."""
        baseline = np.random.normal(0, 1, 1000)
        current = np.random.normal(0, 1, 1000)
        
        result = self.detector.detect(baseline, current)
        
        self.assertFalse(result.has_drift)
        self.assertLess(result.drift_score, 0.3)
    
    def test_with_drift(self):
        """Test detection with drift."""
        baseline = np.random.normal(0, 1, 1000)
        current = np.random.normal(3, 1, 1000)
        
        result = self.detector.detect(baseline, current)
        
        self.assertTrue(result.has_drift)
        self.assertGreater(result.drift_score, 0.5)


class TestWassersteinDetector(unittest.TestCase):
    """Tests for Wasserstein Detector."""
    
    def setUp(self):
        self.detector = WassersteinDetector(threshold=0.05)
    
    def test_no_drift(self):
        """Test detection with no drift."""
        baseline = np.random.normal(0, 1, 1000)
        current = np.random.normal(0, 1, 1000)
        
        result = self.detector.detect(baseline, current)
        
        self.assertFalse(result.has_drift)
    
    def test_with_drift(self):
        """Test detection with drift."""
        baseline = np.random.normal(0, 1, 1000)
        current = np.random.normal(3, 1, 1000)
        
        result = self.detector.detect(baseline, current)
        
        self.assertTrue(result.has_drift)


class TestFeatureDriftDetector(unittest.TestCase):
    """Tests for Feature Drift Detector."""
    
    def setUp(self):
        self.detector = FeatureDriftDetector(threshold=0.05)
    
    def test_detect_feature_drift(self):
        """Test feature drift detection."""
        baseline_tasks = [
            {'data': {'feature1': i, 'feature2': i * 2}}
            for i in range(100)
        ]
        
        current_tasks = [
            {'data': {'feature1': i + 10, 'feature2': i * 2 + 20}}
            for i in range(100)
        ]
        
        results, score, level = self.detector.detect(baseline_tasks, current_tasks)
        
        self.assertIn('feature1', results)
        self.assertIn('feature2', results)
        self.assertGreater(score, 0)


class TestLabelDriftDetector(unittest.TestCase):
    """Tests for Label Drift Detector."""
    
    def setUp(self):
        self.detector = LabelDriftDetector(threshold=0.05)
    
    def test_no_label_drift(self):
        """Test with no label drift."""
        baseline = [
            {'result': [{'value': {'choices': ['positive']}}]}
            for _ in range(50)
        ] + [
            {'result': [{'value': {'choices': ['negative']}}]}
            for _ in range(50)
        ]
        
        current = [
            {'result': [{'value': {'choices': ['positive']}}]}
            for _ in range(48)
        ] + [
            {'result': [{'value': {'choices': ['negative']}}]}
            for _ in range(52)
        ]
        
        result = self.detector.detect(baseline, current)
        
        self.assertFalse(result.has_drift)
    
    def test_with_label_drift(self):
        """Test with label drift."""
        baseline = [
            {'result': [{'value': {'choices': ['positive']}}]}
            for _ in range(80)
        ] + [
            {'result': [{'value': {'choices': ['negative']}}]}
            for _ in range(20)
        ]
        
        current = [
            {'result': [{'value': {'choices': ['positive']}}]}
            for _ in range(20)
        ] + [
            {'result': [{'value': {'choices': ['negative']}}]}
            for _ in range(80)
        ]
        
        result = self.detector.detect(baseline, current)
        
        self.assertTrue(result.has_drift)
        self.assertGreater(result.drift_score, 0.5)


if __name__ == '__main__':
    unittest.main()
