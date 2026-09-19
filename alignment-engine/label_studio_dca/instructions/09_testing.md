# 指令 09：测试实现

## 目标

为所有新模块编写完整的测试用例，确保代码质量和功能正确性。

## 测试文件结构

```
label_studio/
├── active_learning/
│   └── tests/
│       ├── __init__.py
│       ├── test_models.py
│       ├── test_api.py
│       ├── test_strategies.py
│       └── test_selectors.py
├── data_quality/
│   └── tests/
│       ├── __init__.py
│       ├── test_models.py
│       ├── test_api.py
│       └── test_assessors.py
└── drift_detection/
    └── tests/
        ├── __init__.py
        ├── test_models.py
        ├── test_api.py
        └── test_detectors.py
```

## 详细实现

### 9.1 Active Learning测试

#### `active_learning/tests/test_models.py`

```python
# label_studio/active_learning/tests/test_models.py

from django.test import TestCase
from django.contrib.auth import get_user_model
from projects.models import Project
from active_learning.models import (
    ActiveLearningConfig,
    ActiveLearningRound,
    TaskSelectionScore,
)

User = get_user_model()


class ActiveLearningConfigTest(TestCase):
    """Tests for ActiveLearningConfig model."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass'
        )
        self.project = Project.objects.create(
            title='Test Project',
            created_by=self.user
        )
    
    def test_create_config(self):
        """Test creating active learning config."""
        config = ActiveLearningConfig.objects.create(
            project=self.project,
            strategy='uncertainty',
            batch_size=10,
            is_enabled=True,
            created_by=self.user,
        )
        
        self.assertEqual(config.project, self.project)
        self.assertEqual(config.strategy, 'uncertainty')
        self.assertEqual(config.batch_size, 10)
        self.assertTrue(config.is_enabled)
    
    def test_config_str(self):
        """Test config string representation."""
        config = ActiveLearningConfig.objects.create(
            project=self.project,
            strategy='uncertainty',
            created_by=self.user,
        )
        
        self.assertIn('Test Project', str(config))
        self.assertIn('uncertainty', str(config))
    
    def test_one_config_per_project(self):
        """Test that only one config can exist per project."""
        ActiveLearningConfig.objects.create(
            project=self.project,
            strategy='uncertainty',
            created_by=self.user,
        )
        
        # Attempting to create another should fail
        with self.assertRaises(Exception):
            ActiveLearningConfig.objects.create(
                project=self.project,
                strategy='diversity',
                created_by=self.user,
            )


class ActiveLearningRoundTest(TestCase):
    """Tests for ActiveLearningRound model."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass'
        )
        self.project = Project.objects.create(
            title='Test Project',
            created_by=self.user
        )
        self.config = ActiveLearningConfig.objects.create(
            project=self.project,
            strategy='uncertainty',
            created_by=self.user,
        )
    
    def test_create_round(self):
        """Test creating active learning round."""
        round_obj = ActiveLearningRound.objects.create(
            config=self.config,
            round_number=1,
            task_count=10,
            strategy_used='uncertainty',
            created_by=self.user,
        )
        
        self.assertEqual(round_obj.config, self.config)
        self.assertEqual(round_obj.round_number, 1)
        self.assertEqual(round_obj.task_count, 10)
        self.assertFalse(round_obj.is_completed)
    
    def test_round_ordering(self):
        """Test that rounds are ordered by round number."""
        for i in range(3):
            ActiveLearningRound.objects.create(
                config=self.config,
                round_number=i + 1,
                task_count=10,
                strategy_used='uncertainty',
                created_by=self.user,
            )
        
        rounds = ActiveLearningRound.objects.filter(config=self.config)
        self.assertEqual(rounds[0].round_number, 3)  # Most recent first
```

#### `active_learning/tests/test_api.py`

```python
# label_studio/active_learning/tests/test_api.py

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from projects.models import Project
from active_learning.models import ActiveLearningConfig

User = get_user_model()


class ActiveLearningAPITest(TestCase):
    """Tests for Active Learning API endpoints."""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass',
            email='test@example.com'
        )
        self.client.force_authenticate(user=self.user)
        
        self.project = Project.objects.create(
            title='Test Project',
            created_by=self.user,
            organization=self.user.active_organization,
        )
    
    def test_create_config(self):
        """Test creating active learning config via API."""
        url = reverse('active_learning:al-config-list')
        data = {
            'project': self.project.id,
            'strategy': 'uncertainty',
            'batch_size': 10,
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['strategy'], 'uncertainty')
    
    def test_list_configs(self):
        """Test listing active learning configs."""
        # Create config
        ActiveLearningConfig.objects.create(
            project=self.project,
            strategy='uncertainty',
            created_by=self.user,
        )
        
        url = reverse('active_learning:al-config-list')
        response = self.client.get(url, {'project': self.project.id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_toggle_config(self):
        """Test toggling active learning config."""
        config = ActiveLearningConfig.objects.create(
            project=self.project,
            strategy='uncertainty',
            is_enabled=False,
            created_by=self.user,
        )
        
        url = reverse('active_learning:al-config-toggle', args=[config.id])
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_enabled'])
    
    def test_get_status(self):
        """Test getting active learning status."""
        url = reverse('active_learning:al-status', args=[self.project.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('configured', response.data)
```

#### `active_learning/tests/test_strategies.py`

```python
# label_studio/active_learning/tests/test_strategies.py

from django.test import TestCase
import numpy as np
from active_learning.strategies.uncertainty import UncertaintySampling
from active_learning.strategies.diversity import DiversitySampling
from active_learning.strategies.random import RandomSampling


class UncertaintySamplingTest(TestCase):
    """Tests for UncertaintySampling strategy."""
    
    def setUp(self):
        self.strategy = UncertaintySampling(method='entropy')
    
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
        
        # Task 2 should have highest uncertainty (most uncertain)
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


class DiversitySamplingTest(TestCase):
    """Tests for DiversitySampling strategy."""
    
    def setUp(self):
        self.strategy = DiversitySampling(metric='euclidean')
    
    def test_extract_features(self):
        """Test feature extraction from tasks."""
        tasks = [
            {'data': {'feature1': 1.0, 'feature2': 2.0}},
            {'data': {'feature1': 3.0, 'feature2': 4.0}},
        ]
        
        features = self.strategy.extract_features(tasks)
        
        self.assertEqual(features.shape, (2, 2))
    
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


class RandomSamplingTest(TestCase):
    """Tests for RandomSampling strategy."""
    
    def test_select_random(self):
        """Test random selection."""
        strategy = RandomSampling(seed=42)
        
        tasks = [
            {'id': i, 'data': {}} for i in range(10)
        ]
        
        selected, scores = strategy.select(tasks, {}, batch_size=3)
        
        self.assertEqual(len(selected), 3)
        self.assertTrue(all(0 <= s <= 1 for s in scores.values()))
```

### 9.2 Data Quality测试

#### `data_quality/tests/test_assessors.py`

```python
# label_studio/data_quality/tests/test_assessors.py

from django.test import TestCase
from django.contrib.auth import get_user_model
from projects.models import Project
from tasks.models import Task, Annotation
from data_quality.assessors.consistency import ConsistencyAssessor
from data_quality.assessors.completeness import CompletenessAssessor

User = get_user_model()


class ConsistencyAssessorTest(TestCase):
    """Tests for ConsistencyAssessor."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass'
        )
        self.project = Project.objects.create(
            title='Test Project',
            created_by=self.user,
        )
        self.task = Task.objects.create(
            project=self.project,
            data={'text': 'Test text'},
        )
    
    def test_consistent_annotations(self):
        """Test assessment with consistent annotations."""
        # Create consistent annotations
        for _ in range(3):
            Annotation.objects.create(
                task=self.task,
                project=self.project,
                completed_by=self.user,
                result=[{
                    'value': {'choices': ['positive']},
                    'from_name': 'sentiment',
                    'to_name': 'text',
                    'type': 'choices',
                }],
            )
        
        assessor = ConsistencyAssessor(self.project)
        result = assessor.assess()
        
        self.assertEqual(result.score, 1.0)
        self.assertEqual(len(result.issues), 0)
    
    def test_inconsistent_annotations(self):
        """Test assessment with inconsistent annotations."""
        # Create inconsistent annotations
        Annotation.objects.create(
            task=self.task,
            project=self.project,
            completed_by=self.user,
            result=[{
                'value': {'choices': ['positive']},
                'from_name': 'sentiment',
                'to_name': 'text',
                'type': 'choices',
            }],
        )
        
        user2 = User.objects.create_user(
            username='testuser2',
            password='testpass'
        )
        Annotation.objects.create(
            task=self.task,
            project=self.project,
            completed_by=user2,
            result=[{
                'value': {'choices': ['negative']},
                'from_name': 'sentiment',
                'to_name': 'text',
                'type': 'choices',
            }],
        )
        
        assessor = ConsistencyAssessor(self.project)
        result = assessor.assess()
        
        self.assertLess(result.score, 1.0)
        self.assertGreater(len(result.issues), 0)


class CompletenessAssessorTest(TestCase):
    """Tests for CompletenessAssessor."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass'
        )
        self.project = Project.objects.create(
            title='Test Project',
            created_by=self.user,
            maximum_annotations=2,
        )
    
    def test_complete_coverage(self):
        """Test assessment with complete coverage."""
        # Create tasks with annotations
        for i in range(3):
            task = Task.objects.create(
                project=self.project,
                data={'text': f'Text {i}'},
            )
            for _ in range(2):
                Annotation.objects.create(
                    task=task,
                    project=self.project,
                    completed_by=self.user,
                    result=[{
                        'value': {'choices': ['positive']},
                        'from_name': 'sentiment',
                        'to_name': 'text',
                        'type': 'choices',
                    }],
                )
        
        assessor = CompletenessAssessor(self.project)
        result = assessor.assess()
        
        self.assertGreater(result.score, 0.8)
    
    def test_incomplete_coverage(self):
        """Test assessment with incomplete coverage."""
        # Create tasks without annotations
        for i in range(5):
            Task.objects.create(
                project=self.project,
                data={'text': f'Text {i}'},
            )
        
        assessor = CompletenessAssessor(self.project)
        result = assessor.assess()
        
        self.assertLess(result.score, 0.5)
        self.assertGreater(len(result.issues), 0)
```

### 9.3 Drift Detection测试

#### `drift_detection/tests/test_detectors.py`

```python
# label_studio/drift_detection/tests/test_detectors.py

from django.test import TestCase
import numpy as np
from drift_detection.detectors.statistical import (
    KSTestDetector,
    ChiSquareDetector,
    WassersteinDetector,
)
from drift_detection.detectors.feature_drift import FeatureDriftDetector


class KSTestDetectorTest(TestCase):
    """Tests for KSTestDetector."""
    
    def test_no_drift(self):
        """Test detection with no drift."""
        detector = KSTestDetector(threshold=0.05)
        
        # Same distribution
        baseline = np.random.normal(0, 1, 1000)
        current = np.random.normal(0, 1, 1000)
        
        result = detector.detect(baseline, current)
        
        self.assertFalse(result.has_drift)
        self.assertLess(result.drift_score, 0.3)
    
    def test_with_drift(self):
        """Test detection with drift."""
        detector = KSTestDetector(threshold=0.05)
        
        # Different distributions
        baseline = np.random.normal(0, 1, 1000)
        current = np.random.normal(3, 1, 1000)  # Shifted mean
        
        result = detector.detect(baseline, current)
        
        self.assertTrue(result.has_drift)
        self.assertGreater(result.drift_score, 0.5)


class FeatureDriftDetectorTest(TestCase):
    """Tests for FeatureDriftDetector."""
    
    def test_detect_feature_drift(self):
        """Test feature drift detection."""
        detector = FeatureDriftDetector(threshold=0.05)
        
        baseline_tasks = [
            {'data': {'feature1': i, 'feature2': i * 2}}
            for i in range(100)
        ]
        
        current_tasks = [
            {'data': {'feature1': i + 10, 'feature2': i * 2 + 20}}
            for i in range(100)
        ]
        
        results = detector.detect(baseline_tasks, current_tasks)
        
        self.assertIn('feature1', results)
        self.assertIn('feature2', results)
```

### 9.4 运行测试

```bash
# 运行所有测试
python label_studio/manage.py test active_learning data_quality drift_detection

# 运行特定模块测试
python label_studio/manage.py test active_learning
python label_studio/manage.py test data_quality
python label_studio/manage.py test drift_detection

# 运行特定测试文件
python label_studio/manage.py test active_learning.tests.test_strategies

# 运行并显示覆盖率
coverage run label_studio/manage.py test active_learning data_quality drift_detection
coverage report
coverage html  # 生成HTML报告
```

## 验证检查点

- [ ] 所有测试文件创建成功
- [ ] 模型测试通过
- [ ] API测试通过
- [ ] 策略测试通过
- [ ] 评估器测试通过
- [ ] 检测器测试通过
- [ ] 测试覆盖率达到80%以上

## 下一步

执行 `10_documentation.md` 编写项目文档。
