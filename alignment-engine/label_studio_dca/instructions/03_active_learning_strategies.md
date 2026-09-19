# 指令 03：主动学习策略实现

## 目标

实现各种主动学习采样策略，包括不确定性采样、多样性采样、委员会查询等。

## 需要创建的文件

1. `label_studio/active_learning/strategies/__init__.py`
2. `label_studio/active_learning/strategies/base.py`
3. `label_studio/active_learning/strategies/uncertainty.py`
4. `label_studio/active_learning/strategies/diversity.py`
5. `label_studio/active_learning/strategies/committee.py`
6. `label_studio/active_learning/strategies/hybrid.py`
7. `label_studio/active_learning/strategies/random.py`
8. `label_studio/active_learning/selectors/__init__.py`
9. `label_studio/active_learning/selectors/task_selector.py`

## 详细实现

### 3.1 创建 `strategies/__init__.py`

```python
# label_studio/active_learning/strategies/__init__.py
"""Active Learning strategies."""

from active_learning.strategies.base import BaseStrategy
from active_learning.strategies.uncertainty import UncertaintySampling
from active_learning.strategies.diversity import DiversitySampling
from active_learning.strategies.committee import QueryByCommittee
from active_learning.strategies.hybrid import HybridStrategy
from active_learning.strategies.random import RandomSampling

__all__ = [
    'BaseStrategy',
    'UncertaintySampling',
    'DiversitySampling',
    'QueryByCommittee',
    'HybridStrategy',
    'RandomSampling',
    'get_strategy',
]

STRATEGY_REGISTRY = {
    'uncertainty': UncertaintySampling,
    'diversity': DiversitySampling,
    'committee': QueryByCommittee,
    'hybrid': HybridStrategy,
    'random': RandomSampling,
}


def get_strategy(strategy_name, **kwargs):
    """
    Factory function to get strategy instance.
    
    Args:
        strategy_name: Name of the strategy
        **kwargs: Strategy-specific parameters
    
    Returns:
        Strategy instance
    """
    if strategy_name not in STRATEGY_REGISTRY:
        raise ValueError(f"Unknown strategy: {strategy_name}. Available: {list(STRATEGY_REGISTRY.keys())}")
    
    strategy_class = STRATEGY_REGISTRY[strategy_name]
    return strategy_class(**kwargs)
```

### 3.2 创建 `strategies/base.py`

```python
# label_studio/active_learning/strategies/base.py
"""Base class for active learning strategies."""

import logging
import numpy as np
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class BaseStrategy(ABC):
    """Base class for all active learning strategies."""
    
    def __init__(self, **kwargs):
        """
        Initialize strategy with parameters.
        
        Args:
            **kwargs: Strategy-specific parameters
        """
        self.params = kwargs
    
    @abstractmethod
    def compute_scores(
        self,
        tasks: List[Dict],
        predictions: Dict[int, List[Dict]],
        **kwargs
    ) -> Dict[int, float]:
        """
        Compute selection scores for tasks.
        
        Args:
            tasks: List of task data dictionaries
            predictions: Dictionary mapping task_id to predictions
            **kwargs: Additional parameters
        
        Returns:
            Dictionary mapping task_id to score (higher = more informative)
        """
        raise NotImplementedError
    
    @abstractmethod
    def select(
        self,
        tasks: List[Dict],
        predictions: Dict[int, List[Dict]],
        batch_size: int,
        **kwargs
    ) -> Tuple[List[int], Dict[int, float]]:
        """
        Select tasks for annotation.
        
        Args:
            tasks: List of task data dictionaries
            predictions: Dictionary mapping task_id to predictions
            batch_size: Number of tasks to select
            **kwargs: Additional parameters
        
        Returns:
            Tuple of (selected_task_ids, all_scores)
        """
        raise NotImplementedError
    
    def _extract_probabilities(self, prediction: Dict) -> Optional[np.ndarray]:
        """
        Extract probability distribution from prediction.
        
        Args:
            prediction: Prediction dictionary
        
        Returns:
            numpy array of probabilities or None
        """
        result = prediction.get('result', [])
        
        for item in result:
            value = item.get('value', {})
            
            # Handle choices with scores
            if 'choices' in value:
                choices = value['choices']
                if isinstance(choices, dict):
                    return np.array(list(choices.values()))
                elif isinstance(choices, list):
                    # Uniform probability for each choice
                    return np.ones(len(choices)) / len(choices)
            
            # Handle numeric scores
            if 'score' in value:
                return np.array([value['score'], 1 - value['score']])
        
        return None
    
    def _get_prediction_for_task(
        self,
        task_id: int,
        predictions: Dict[int, List[Dict]]
    ) -> List[Dict]:
        """
        Get predictions for a specific task.
        
        Args:
            task_id: Task ID
            predictions: All predictions
        
        Returns:
            List of predictions for the task
        """
        return predictions.get(task_id, [])
    
    def _normalize_scores(self, scores: Dict[int, float]) -> Dict[int, float]:
        """
        Normalize scores to [0, 1] range.
        
        Args:
            scores: Dictionary of task_id to score
        
        Returns:
            Normalized scores
        """
        if not scores:
            return scores
        
        values = list(scores.values())
        min_val = min(values)
        max_val = max(values)
        
        if max_val == min_val:
            return {k: 0.5 for k in scores}
        
        return {
            k: (v - min_val) / (max_val - min_val)
            for k, v in scores.items()
        }
```

### 3.3 创建 `strategies/uncertainty.py`

```python
# label_studio/active_learning/strategies/uncertainty.py
"""Uncertainty sampling strategies for active learning."""

import logging
import numpy as np
from typing import List, Dict, Tuple
from .base import BaseStrategy

logger = logging.getLogger(__name__)


class UncertaintySampling(BaseStrategy):
    """
    Uncertainty sampling strategy.
    
    Selects tasks where the model is most uncertain about its predictions.
    """
    
    METHODS = ['least_confidence', 'margin_sampling', 'entropy']
    
    def __init__(self, method: str = 'entropy', **kwargs):
        """
        Initialize uncertainty sampling.
        
        Args:
            method: Uncertainty calculation method
                - 'least_confidence': 1 - max(probability)
                - 'margin_sampling': 1 - (p1 - p2) where p1, p2 are top-2 probabilities
                - 'entropy': Shannon entropy of probability distribution
        """
        super().__init__(**kwargs)
        
        if method not in self.METHODS:
            raise ValueError(f"Unknown method: {method}. Available: {self.METHODS}")
        
        self.method = method
    
    def compute_uncertainty(self, probabilities: np.ndarray) -> float:
        """
        Compute uncertainty score for a probability distribution.
        
        Args:
            probabilities: Probability distribution
        
        Returns:
            Uncertainty score (higher = more uncertain)
        """
        if probabilities is None or len(probabilities) == 0:
            return 1.0  # Maximum uncertainty for no predictions
        
        # Ensure probabilities sum to 1
        probabilities = probabilities / probabilities.sum()
        
        if self.method == 'least_confidence':
            # 1 - maximum probability
            return 1.0 - np.max(probabilities)
        
        elif self.method == 'margin_sampling':
            # 1 - margin between top-2 probabilities
            sorted_probs = np.sort(probabilities)[::-1]
            if len(sorted_probs) >= 2:
                return 1.0 - (sorted_probs[0] - sorted_probs[1])
            return 1.0 - sorted_probs[0]
        
        elif self.method == 'entropy':
            # Shannon entropy
            # Add small epsilon to avoid log(0)
            probs = np.clip(probabilities, 1e-10, 1.0)
            entropy = -np.sum(probs * np.log(probs))
            # Normalize by max entropy
            max_entropy = np.log(len(probabilities))
            if max_entropy > 0:
                return entropy / max_entropy
            return 0.0
        
        else:
            raise ValueError(f"Unknown method: {self.method}")
    
    def compute_task_uncertainty(self, predictions: List[Dict]) -> float:
        """
        Compute uncertainty for a task based on its predictions.
        
        Args:
            predictions: List of predictions for the task
        
        Returns:
            Average uncertainty score
        """
        if not predictions:
            return 1.0  # Maximum uncertainty for no predictions
        
        uncertainties = []
        
        for pred in predictions:
            probabilities = self._extract_probabilities(pred)
            if probabilities is not None:
                uncertainty = self.compute_uncertainty(probabilities)
                uncertainties.append(uncertainty)
        
        if not uncertainties:
            return 1.0
        
        return np.mean(uncertainties)
    
    def compute_scores(
        self,
        tasks: List[Dict],
        predictions: Dict[int, List[Dict]],
        **kwargs
    ) -> Dict[int, float]:
        """
        Compute uncertainty scores for all tasks.
        
        Args:
            tasks: List of task data dictionaries
            predictions: Dictionary mapping task_id to predictions
        
        Returns:
            Dictionary mapping task_id to uncertainty score
        """
        scores = {}
        
        for task in tasks:
            task_id = task['id']
            task_predictions = self._get_prediction_for_task(task_id, predictions)
            uncertainty = self.compute_task_uncertainty(task_predictions)
            scores[task_id] = uncertainty
        
        # Normalize scores
        scores = self._normalize_scores(scores)
        
        logger.debug(
            f'Computed uncertainty scores for {len(tasks)} tasks '
            f'(method: {self.method}, avg: {np.mean(list(scores.values())):.3f})'
        )
        
        return scores
    
    def select(
        self,
        tasks: List[Dict],
        predictions: Dict[int, List[Dict]],
        batch_size: int,
        **kwargs
    ) -> Tuple[List[int], Dict[int, float]]:
        """
        Select most uncertain tasks.
        
        Args:
            tasks: List of task data dictionaries
            predictions: Dictionary mapping task_id to predictions
            batch_size: Number of tasks to select
        
        Returns:
            Tuple of (selected_task_ids, all_scores)
        """
        # Compute scores
        scores = self.compute_scores(tasks, predictions)
        
        # Sort by score (descending) and select top-k
        sorted_tasks = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        selected_ids = [task_id for task_id, _ in sorted_tasks[:batch_size]]
        
        logger.info(
            f'Selected {len(selected_ids)} tasks using uncertainty sampling '
            f'(method: {self.method})'
        )
        
        return selected_ids, scores


class LeastConfidence(UncertaintySampling):
    """Least confidence sampling strategy."""
    
    def __init__(self, **kwargs):
        super().__init__(method='least_confidence', **kwargs)


class MarginSampling(UncertaintySampling):
    """Margin sampling strategy."""
    
    def __init__(self, **kwargs):
        super().__init__(method='margin_sampling', **kwargs)


class EntropySampling(UncertaintySampling):
    """Entropy-based uncertainty sampling strategy."""
    
    def __init__(self, **kwargs):
        super().__init__(method='entropy', **kwargs)
```

### 3.4 创建 `strategies/diversity.py`

```python
# label_studio/active_learning/strategies/diversity.py
"""Diversity sampling strategies for active learning."""

import logging
import numpy as np
from typing import List, Dict, Tuple, Optional
from sklearn.metrics.pairwise import cosine_distances, euclidean_distances
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from .base import BaseStrategy

logger = logging.getLogger(__name__)


class DiversitySampling(BaseStrategy):
    """
    Diversity sampling strategy.
    
    Selects diverse tasks to cover the feature space.
    """
    
    METRICS = ['cosine', 'euclidean', 'manhattan']
    
    def __init__(self, metric: str = 'cosine', use_clustering: bool = True, **kwargs):
        """
        Initialize diversity sampling.
        
        Args:
            metric: Distance metric to use
            use_clustering: Whether to use clustering for diversity
        """
        super().__init__(**kwargs)
        
        if metric not in self.METRICS:
            raise ValueError(f"Unknown metric: {metric}. Available: {self.METRICS}")
        
        self.metric = metric
        self.use_clustering = use_clustering
    
    def extract_features(self, tasks: List[Dict]) -> np.ndarray:
        """
        Extract feature vectors from tasks.
        
        Args:
            tasks: List of task data dictionaries
        
        Returns:
            Feature matrix (n_tasks x n_features)
        """
        features = []
        
        for task in tasks:
            task_data = task.get('data', {})
            
            # Extract numerical features
            feature_vector = []
            for key, value in task_data.items():
                if isinstance(value, (int, float)):
                    feature_vector.append(value)
                elif isinstance(value, str):
                    # Simple hash-based feature for strings
                    feature_vector.append(hash(value) % 1000 / 1000)
            
            if not feature_vector:
                feature_vector = [0.0]
            
            features.append(feature_vector)
        
        # Pad to same length
        max_len = max(len(f) for f in features)
        features = [f + [0.0] * (max_len - len(f)) for f in features]
        
        return np.array(features)
    
    def compute_distance(self, features: np.ndarray) -> np.ndarray:
        """
        Compute distance matrix.
        
        Args:
            features: Feature matrix
        
        Returns:
            Distance matrix
        """
        if self.metric == 'cosine':
            return cosine_distances(features)
        elif self.metric == 'euclidean':
            return euclidean_distances(features)
        elif self.metric == 'manhattan':
            # Manhattan distance
            n = len(features)
            distances = np.zeros((n, n))
            for i in range(n):
                for j in range(i + 1, n):
                    d = np.sum(np.abs(features[i] - features[j]))
                    distances[i, j] = d
                    distances[j, i] = d
            return distances
        else:
            raise ValueError(f"Unknown metric: {self.metric}")
    
    def compute_diversity_scores(
        self,
        features: np.ndarray,
        predictions: Dict[int, List[Dict]],
        task_ids: List[int]
    ) -> Dict[int, float]:
        """
        Compute diversity scores for tasks.
        
        Args:
            features: Feature matrix
            predictions: Predictions for tasks
            task_ids: List of task IDs
        
        Returns:
            Dictionary of task_id to diversity score
        """
        n_tasks = len(task_ids)
        
        if n_tasks <= 1:
            return {task_id: 1.0 for task_id in task_ids}
        
        # Compute distance matrix
        distances = self.compute_distance(features)
        
        # Compute diversity score as average distance to other tasks
        scores = {}
        for i, task_id in enumerate(task_ids):
            # Average distance to all other tasks
            avg_distance = np.mean(distances[i])
            scores[task_id] = avg_distance
        
        # Normalize scores
        scores = self._normalize_scores(scores)
        
        return scores
    
    def select_diverse_subset(
        self,
        features: np.ndarray,
        task_ids: List[int],
        batch_size: int
    ) -> List[int]:
        """
        Select diverse subset using greedy farthest-first traversal.
        
        Args:
            features: Feature matrix
            task_ids: List of task IDs
            batch_size: Number of tasks to select
        
        Returns:
            Selected task IDs
        """
        n_tasks = len(task_ids)
        
        if batch_size >= n_tasks:
            return task_ids
        
        # Compute distance matrix
        distances = self.compute_distance(features)
        
        # Greedy farthest-first traversal
        selected_indices = []
        remaining_indices = list(range(n_tasks))
        
        # Start with random task
        first_idx = np.random.randint(n_tasks)
        selected_indices.append(first_idx)
        remaining_indices.remove(first_idx)
        
        while len(selected_indices) < batch_size and remaining_indices:
            # Find task farthest from all selected tasks
            max_min_distance = -1
            best_idx = None
            
            for idx in remaining_indices:
                # Minimum distance to any selected task
                min_distance = min(distances[idx][sel_idx] for sel_idx in selected_indices)
                
                if min_distance > max_min_distance:
                    max_min_distance = min_distance
                    best_idx = idx
            
            if best_idx is not None:
                selected_indices.append(best_idx)
                remaining_indices.remove(best_idx)
        
        return [task_ids[idx] for idx in selected_indices]
    
    def select_diverse_subset_clustering(
        self,
        features: np.ndarray,
        task_ids: List[int],
        batch_size: int
    ) -> List[int]:
        """
        Select diverse subset using clustering.
        
        Args:
            features: Feature matrix
            task_ids: List of task IDs
            batch_size: Number of tasks to select
        
        Returns:
            Selected task IDs
        """
        n_tasks = len(task_ids)
        
        if batch_size >= n_tasks:
            return task_ids
        
        # Reduce dimensionality if needed
        if features.shape[1] > 10:
            pca = PCA(n_components=min(10, n_tasks))
            features = pca.fit_transform(features)
        
        # Cluster tasks
        n_clusters = min(batch_size, n_tasks)
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        cluster_labels = kmeans.fit_predict(features)
        
        # Select one task from each cluster (closest to centroid)
        selected_indices = []
        for cluster_id in range(n_clusters):
            cluster_indices = np.where(cluster_labels == cluster_id)[0]
            
            if len(cluster_indices) == 0:
                continue
            
            # Find task closest to centroid
            centroid = kmeans.cluster_centers_[cluster_id]
            distances = np.linalg.norm(features[cluster_indices] - centroid, axis=1)
            closest_idx = cluster_indices[np.argmin(distances)]
            
            selected_indices.append(closest_idx)
        
        return [task_ids[idx] for idx in selected_indices[:batch_size]]
    
    def compute_scores(
        self,
        tasks: List[Dict],
        predictions: Dict[int, List[Dict]],
        **kwargs
    ) -> Dict[int, float]:
        """
        Compute diversity scores for all tasks.
        
        Args:
            tasks: List of task data dictionaries
            predictions: Dictionary mapping task_id to predictions
        
        Returns:
            Dictionary mapping task_id to diversity score
        """
        if not tasks:
            return {}
        
        task_ids = [task['id'] for task in tasks]
        features = self.extract_features(tasks)
        
        scores = self.compute_diversity_scores(features, predictions, task_ids)
        
        logger.debug(
            f'Computed diversity scores for {len(tasks)} tasks '
            f'(metric: {self.metric}, avg: {np.mean(list(scores.values())):.3f})'
        )
        
        return scores
    
    def select(
        self,
        tasks: List[Dict],
        predictions: Dict[int, List[Dict]],
        batch_size: int,
        **kwargs
    ) -> Tuple[List[int], Dict[int, float]]:
        """
        Select diverse tasks.
        
        Args:
            tasks: List of task data dictionaries
            predictions: Dictionary mapping task_id to predictions
            batch_size: Number of tasks to select
        
        Returns:
            Tuple of (selected_task_ids, all_scores)
        """
        if not tasks:
            return [], {}
        
        task_ids = [task['id'] for task in tasks]
        features = self.extract_features(tasks)
        
        # Select diverse subset
        if self.use_clustering:
            selected_ids = self.select_diverse_subset_clustering(
                features, task_ids, batch_size
            )
        else:
            selected_ids = self.select_diverse_subset(
                features, task_ids, batch_size
            )
        
        # Compute scores for all tasks
        scores = self.compute_diversity_scores(features, predictions, task_ids)
        
        logger.info(
            f'Selected {len(selected_ids)} tasks using diversity sampling '
            f'(metric: {self.metric}, clustering: {self.use_clustering})'
        )
        
        return selected_ids, scores
```

### 3.5 创建 `strategies/committee.py`

```python
# label_studio/active_learning/strategies/committee.py
"""Query by Committee (QBC) strategy for active learning."""

import logging
import numpy as np
from typing import List, Dict, Tuple
from .base import BaseStrategy

logger = logging.getLogger(__name__)


class QueryByCommittee(BaseStrategy):
    """
    Query by Committee strategy.
    
    Uses disagreement among multiple models to select informative tasks.
    """
    
    DISAGREEMENT_METHODS = ['vote_entropy', 'kl_divergence', 'consensus_entropy']
    
    def __init__(
        self,
        committee_size: int = 5,
        disagreement_method: str = 'vote_entropy',
        **kwargs
    ):
        """
        Initialize QBC strategy.
        
        Args:
            committee_size: Number of models in committee
            disagreement_method: Method to compute disagreement
        """
        super().__init__(**kwargs)
        
        self.committee_size = committee_size
        
        if disagreement_method not in self.DISAGREEMENT_METHODS:
            raise ValueError(
                f"Unknown method: {disagreement_method}. "
                f"Available: {self.DISAGREEMENT_METHODS}"
            )
        
        self.disagreement_method = disagreement_method
    
    def compute_vote_entropy(self, predictions: List[Dict]) -> float:
        """
        Compute vote entropy among committee members.
        
        Args:
            predictions: List of predictions from different committee members
        
        Returns:
            Vote entropy score
        """
        if not predictions:
            return 0.0
        
        # Count votes for each class
        votes = {}
        for pred in predictions:
            result = pred.get('result', [])
            for item in result:
                value = item.get('value', {})
                if 'choices' in value:
                    choices = value['choices']
                    if isinstance(choices, list):
                        for choice in choices:
                            votes[choice] = votes.get(choice, 0) + 1
                    elif isinstance(choices, dict):
                        # Use the choice with highest probability
                        max_choice = max(choices.items(), key=lambda x: x[1])[0]
                        votes[max_choice] = votes.get(max_choice, 0) + 1
        
        if not votes:
            return 0.0
        
        # Compute entropy
        total_votes = sum(votes.values())
        entropy = 0.0
        
        for count in votes.values():
            if count > 0:
                prob = count / total_votes
                entropy -= prob * np.log(prob)
        
        # Normalize by max entropy
        max_entropy = np.log(len(votes))
        if max_entropy > 0:
            return entropy / max_entropy
        
        return 0.0
    
    def compute_kl_divergence(self, predictions: List[Dict]) -> float:
        """
        Compute average KL divergence between committee members.
        
        Args:
            predictions: List of predictions from different committee members
        
        Returns:
            Average KL divergence
        """
        if len(predictions) < 2:
            return 0.0
        
        # Extract probability distributions
        distributions = []
        for pred in predictions:
            probs = self._extract_probabilities(pred)
            if probs is not None:
                distributions.append(probs)
        
        if len(distributions) < 2:
            return 0.0
        
        # Compute average distribution
        avg_dist = np.mean(distributions, axis=0)
        
        # Compute KL divergence from each member to average
        kl_divs = []
        for dist in distributions:
            # Add epsilon to avoid log(0)
            dist = np.clip(dist, 1e-10, 1.0)
            avg = np.clip(avg_dist, 1e-10, 1.0)
            
            # KL(P || Q) = sum(P * log(P/Q))
            kl = np.sum(dist * np.log(dist / avg))
            kl_divs.append(kl)
        
        return np.mean(kl_divs)
    
    def compute_consensus_entropy(self, predictions: List[Dict]) -> float:
        """
        Compute entropy of consensus distribution.
        
        Args:
            predictions: List of predictions from different committee members
        
        Returns:
            Consensus entropy score
        """
        if not predictions:
            return 0.0
        
        # Aggregate probability distributions
        all_probs = []
        for pred in predictions:
            probs = self._extract_probabilities(pred)
            if probs is not None:
                all_probs.append(probs)
        
        if not all_probs:
            return 0.0
        
        # Compute consensus (average) distribution
        consensus = np.mean(all_probs, axis=0)
        
        # Compute entropy of consensus
        consensus = np.clip(consensus, 1e-10, 1.0)
        entropy = -np.sum(consensus * np.log(consensus))
        
        # Normalize
        max_entropy = np.log(len(consensus))
        if max_entropy > 0:
            return entropy / max_entropy
        
        return 0.0
    
    def compute_disagreement(self, predictions: List[Dict]) -> float:
        """
        Compute disagreement among committee members.
        
        Args:
            predictions: List of predictions from different committee members
        
        Returns:
            Disagreement score
        """
        if self.disagreement_method == 'vote_entropy':
            return self.compute_vote_entropy(predictions)
        elif self.disagreement_method == 'kl_divergence':
            return self.compute_kl_divergence(predictions)
        elif self.disagreement_method == 'consensus_entropy':
            return self.compute_consensus_entropy(predictions)
        else:
            raise ValueError(f"Unknown method: {self.disagreement_method}")
    
    def compute_scores(
        self,
        tasks: List[Dict],
        predictions: Dict[int, List[Dict]],
        **kwargs
    ) -> Dict[int, float]:
        """
        Compute disagreement scores for all tasks.
        
        Args:
            tasks: List of task data dictionaries
            predictions: Dictionary mapping task_id to predictions
        
        Returns:
            Dictionary mapping task_id to disagreement score
        """
        scores = {}
        
        for task in tasks:
            task_id = task['id']
            task_predictions = self._get_prediction_for_task(task_id, predictions)
            
            # Limit to committee size
            task_predictions = task_predictions[:self.committee_size]
            
            disagreement = self.compute_disagreement(task_predictions)
            scores[task_id] = disagreement
        
        # Normalize scores
        scores = self._normalize_scores(scores)
        
        logger.debug(
            f'Computed QBC scores for {len(tasks)} tasks '
            f'(method: {self.disagreement_method}, '
            f'committee_size: {self.committee_size}, '
            f'avg: {np.mean(list(scores.values())):.3f})'
        )
        
        return scores
    
    def select(
        self,
        tasks: List[Dict],
        predictions: Dict[int, List[Dict]],
        batch_size: int,
        **kwargs
    ) -> Tuple[List[int], Dict[int, float]]:
        """
        Select tasks with highest committee disagreement.
        
        Args:
            tasks: List of task data dictionaries
            predictions: Dictionary mapping task_id to predictions
            batch_size: Number of tasks to select
        
        Returns:
            Tuple of (selected_task_ids, all_scores)
        """
        # Compute scores
        scores = self.compute_scores(tasks, predictions)
        
        # Sort by score (descending) and select top-k
        sorted_tasks = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        selected_ids = [task_id for task_id, _ in sorted_tasks[:batch_size]]
        
        logger.info(
            f'Selected {len(selected_ids)} tasks using QBC '
            f'(method: {self.disagreement_method})'
        )
        
        return selected_ids, scores
```

### 3.6 创建 `strategies/hybrid.py`

```python
# label_studio/active_learning/strategies/hybrid.py
"""Hybrid strategy combining multiple active learning strategies."""

import logging
import numpy as np
from typing import List, Dict, Tuple
from .base import BaseStrategy
from .uncertainty import UncertaintySampling
from .diversity import DiversitySampling
from .committee import QueryByCommittee

logger = logging.getLogger(__name__)


class HybridStrategy(BaseStrategy):
    """
    Hybrid strategy combining multiple active learning strategies.
    
    Combines uncertainty, diversity, and committee disagreement scores.
    """
    
    def __init__(
        self,
        uncertainty_weight: float = 0.4,
        diversity_weight: float = 0.3,
        committee_weight: float = 0.3,
        uncertainty_method: str = 'entropy',
        diversity_metric: str = 'cosine',
        committee_size: int = 5,
        **kwargs
    ):
        """
        Initialize hybrid strategy.
        
        Args:
            uncertainty_weight: Weight for uncertainty component
            diversity_weight: Weight for diversity component
            committee_weight: Weight for committee component
            uncertainty_method: Method for uncertainty sampling
            diversity_metric: Metric for diversity sampling
            committee_size: Size of committee for QBC
        """
        super().__init__(**kwargs)
        
        # Validate weights sum to 1
        total_weight = uncertainty_weight + diversity_weight + committee_weight
        if abs(total_weight - 1.0) > 0.01:
            raise ValueError(f"Weights must sum to 1.0, got {total_weight}")
        
        self.uncertainty_weight = uncertainty_weight
        self.diversity_weight = diversity_weight
        self.committee_weight = committee_weight
        
        # Initialize sub-strategies
        self.uncertainty_strategy = UncertaintySampling(method=uncertainty_method)
        self.diversity_strategy = DiversitySampling(metric=diversity_metric)
        self.committee_strategy = QueryByCommittee(committee_size=committee_size)
    
    def compute_scores(
        self,
        tasks: List[Dict],
        predictions: Dict[int, List[Dict]],
        **kwargs
    ) -> Dict[int, float]:
        """
        Compute combined scores from all strategies.
        
        Args:
            tasks: List of task data dictionaries
            predictions: Dictionary mapping task_id to predictions
        
        Returns:
            Dictionary mapping task_id to combined score
        """
        # Compute scores from each strategy
        uncertainty_scores = self.uncertainty_strategy.compute_scores(tasks, predictions)
        diversity_scores = self.diversity_strategy.compute_scores(tasks, predictions)
        committee_scores = self.committee_strategy.compute_scores(tasks, predictions)
        
        # Combine scores with weights
        combined_scores = {}
        
        for task in tasks:
            task_id = task['id']
            
            unc_score = uncertainty_scores.get(task_id, 0.0)
            div_score = diversity_scores.get(task_id, 0.0)
            com_score = committee_scores.get(task_id, 0.0)
            
            combined = (
                self.uncertainty_weight * unc_score +
                self.diversity_weight * div_score +
                self.committee_weight * com_score
            )
            
            combined_scores[task_id] = combined
        
        # Normalize combined scores
        combined_scores = self._normalize_scores(combined_scores)
        
        logger.debug(
            f'Computed hybrid scores for {len(tasks)} tasks '
            f'(weights: unc={self.uncertainty_weight}, '
            f'div={self.diversity_weight}, com={self.committee_weight})'
        )
        
        return combined_scores
    
    def select(
        self,
        tasks: List[Dict],
        predictions: Dict[int, List[Dict]],
        batch_size: int,
        **kwargs
    ) -> Tuple[List[int], Dict[int, float]]:
        """
        Select tasks using hybrid strategy.
        
        Args:
            tasks: List of task data dictionaries
            predictions: Dictionary mapping task_id to predictions
            batch_size: Number of tasks to select
        
        Returns:
            Tuple of (selected_task_ids, all_scores)
        """
        # Compute combined scores
        scores = self.compute_scores(tasks, predictions)
        
        # Sort by score (descending) and select top-k
        sorted_tasks = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        selected_ids = [task_id for task_id, _ in sorted_tasks[:batch_size]]
        
        logger.info(
            f'Selected {len(selected_ids)} tasks using hybrid strategy '
            f'(weights: unc={self.uncertainty_weight}, '
            f'div={self.diversity_weight}, com={self.committee_weight})'
        )
        
        return selected_ids, scores
```

### 3.7 创建 `strategies/random.py`

```python
# label_studio/active_learning/strategies/random.py
"""Random sampling strategy for active learning (baseline)."""

import logging
import random
from typing import List, Dict, Tuple
from .base import BaseStrategy

logger = logging.getLogger(__name__)


class RandomSampling(BaseStrategy):
    """
    Random sampling strategy.
    
    Randomly selects tasks. This serves as a baseline for comparison.
    """
    
    def __init__(self, seed: int = None, **kwargs):
        """
        Initialize random sampling.
        
        Args:
            seed: Random seed for reproducibility
        """
        super().__init__(**kwargs)
        self.seed = seed
    
    def compute_scores(
        self,
        tasks: List[Dict],
        predictions: Dict[int, List[Dict]],
        **kwargs
    ) -> Dict[int, float]:
        """
        Compute random scores for all tasks.
        
        Args:
            tasks: List of task data dictionaries
            predictions: Dictionary mapping task_id to predictions
        
        Returns:
            Dictionary mapping task_id to random score
        """
        if self.seed is not None:
            random.seed(self.seed)
        
        scores = {}
        for task in tasks:
            task_id = task['id']
            scores[task_id] = random.random()
        
        return scores
    
    def select(
        self,
        tasks: List[Dict],
        predictions: Dict[int, List[Dict]],
        batch_size: int,
        **kwargs
    ) -> Tuple[List[int], Dict[int, float]]:
        """
        Randomly select tasks.
        
        Args:
            tasks: List of task data dictionaries
            predictions: Dictionary mapping task_id to predictions
            batch_size: Number of tasks to select
        
        Returns:
            Tuple of (selected_task_ids, all_scores)
        """
        if self.seed is not None:
            random.seed(self.seed)
        
        task_ids = [task['id'] for task in tasks]
        
        # Randomly select tasks
        batch_size = min(batch_size, len(task_ids))
        selected_ids = random.sample(task_ids, batch_size)
        
        # Compute scores (random)
        scores = self.compute_scores(tasks, predictions)
        
        logger.info(f'Selected {len(selected_ids)} tasks randomly')
        
        return selected_ids, scores
```

### 3.8 创建 `selectors/__init__.py`

```python
# label_studio/active_learning/selectors/__init__.py
"""Task selectors for active learning."""

from active_learning.selectors.task_selector import TaskSelector

__all__ = ['TaskSelector']
```

### 3.9 创建 `selectors/task_selector.py`

```python
# label_studio/active_learning/selectors/task_selector.py
"""Task selector for active learning."""

import logging
from typing import List, Dict, Optional
from django.db import transaction
from django.utils.timezone import now

from active_learning.models import (
    ActiveLearningConfig,
    ActiveLearningRound,
    TaskSelectionScore,
)
from active_learning.strategies import get_strategy
from tasks.models import Task
from projects.models import Project

logger = logging.getLogger(__name__)


class TaskSelector:
    """
    Task selector for active learning.
    
    Handles the selection of tasks for annotation using configured strategies.
    """
    
    def __init__(self, config: ActiveLearningConfig):
        """
        Initialize task selector.
        
        Args:
            config: ActiveLearningConfig instance
        """
        self.config = config
        self.project = config.project
        self.strategy = config.get_strategy_instance()
    
    def get_candidate_tasks(
        self,
        exclude_annotated: bool = True,
        exclude_selected: bool = True
    ) -> List[Task]:
        """
        Get candidate tasks for selection.
        
        Args:
            exclude_annotated: Whether to exclude annotated tasks
            exclude_selected: Whether to exclude previously selected tasks
        
        Returns:
            List of candidate tasks
        """
        queryset = Task.objects.filter(project=self.project)
        
        if exclude_annotated:
            # Exclude tasks that have annotations
            queryset = queryset.filter(total_annotations=0)
        
        if exclude_selected:
            # Exclude tasks selected in previous incomplete rounds
            selected_task_ids = TaskSelectionScore.objects.filter(
                round__config=self.config,
                is_selected=True,
                round__is_completed=False
            ).values_list('task_id', flat=True)
            
            queryset = queryset.exclude(id__in=selected_task_ids)
        
        return list(queryset)
    
    def get_predictions(self, tasks: List[Task]) -> Dict[int, List[Dict]]:
        """
        Get predictions for tasks from ML backend.
        
        Args:
            tasks: List of tasks
        
        Returns:
            Dictionary mapping task_id to predictions
        """
        predictions = {}
        
        if not self.config.ml_backend:
            logger.warning('No ML backend configured for active learning')
            return predictions
        
        try:
            # Get predictions from ML backend
            for task in tasks:
                task_predictions = task.predictions.filter(
                    model_version=self.config.ml_backend.model_version
                ).order_by('-created_at')
                
                if task_predictions.exists():
                    predictions[task.id] = [
                        {
                            'result': pred.result,
                            'score': pred.score,
                            'model_version': pred.model_version,
                        }
                        for pred in task_predictions
                    ]
        
        except Exception as e:
            logger.error(f'Error getting predictions: {str(e)}')
        
        return predictions
    
    def prepare_task_data(self, tasks: List[Task]) -> List[Dict]:
        """
        Prepare task data for strategy.
        
        Args:
            tasks: List of tasks
        
        Returns:
            List of task data dictionaries
        """
        return [
            {
                'id': task.id,
                'data': task.data,
                'meta': task.meta,
                'total_annotations': task.total_annotations,
                'total_predictions': task.total_predictions,
            }
            for task in tasks
        ]
    
    @transaction.atomic
    def select_tasks(
        self,
        batch_size: int = None,
        strategy_name: str = None,
        exclude_annotated: bool = True,
        exclude_selected: bool = True,
        user=None
    ) -> Dict:
        """
        Select tasks for annotation.
        
        Args:
            batch_size: Number of tasks to select (overrides config)
            strategy_name: Strategy to use (overrides config)
            exclude_annotated: Whether to exclude annotated tasks
            exclude_selected: Whether to exclude previously selected tasks
            user: User performing the selection
        
        Returns:
            Dictionary with selection results
        """
        # Use config values if not specified
        batch_size = batch_size or self.config.batch_size
        
        # Get strategy
        if strategy_name:
            strategy = get_strategy(strategy_name)
        else:
            strategy = self.strategy
        
        # Get candidate tasks
        candidates = self.get_candidate_tasks(
            exclude_annotated=exclude_annotated,
            exclude_selected=exclude_selected
        )
        
        if not candidates:
            logger.warning('No candidate tasks available for selection')
            return {
                'round_id': None,
                'round_number': 0,
                'task_ids': [],
                'task_scores': {},
                'strategy_used': strategy_name or self.config.strategy,
                'avg_uncertainty': 0.0,
                'diversity_score': 0.0,
                'selection_summary': {'message': 'No tasks available'},
            }
        
        # Prepare task data
        task_data = self.prepare_task_data(candidates)
        
        # Get predictions
        predictions = self.get_predictions(candidates)
        
        # Select tasks
        selected_ids, scores = strategy.select(
            tasks=task_data,
            predictions=predictions,
            batch_size=batch_size,
        )
        
        # Create round
        round_number = self.config.rounds.count() + 1
        round_obj = ActiveLearningRound.objects.create(
            config=self.config,
            round_number=round_number,
            task_count=len(selected_ids),
            strategy_used=strategy_name or self.config.strategy,
            selection_scores=scores,
            created_by=user,
        )
        
        # Add selected tasks to round
        selected_tasks = Task.objects.filter(id__in=selected_ids)
        round_obj.selected_tasks.set(selected_tasks)
        
        # Create task scores
        task_score_objects = []
        for rank, task_id in enumerate(selected_ids, 1):
            task_score = TaskSelectionScore(
                round=round_obj,
                task_id=task_id,
                final_score=scores.get(task_id, 0.0),
                rank=rank,
                is_selected=True,
            )
            task_score_objects.append(task_score)
        
        TaskSelectionScore.objects.bulk_create(task_score_objects)
        
        # Compute metrics
        avg_uncertainty = np.mean([scores.get(tid, 0) for tid in selected_ids]) if selected_ids else 0
        
        logger.info(
            f'Selected {len(selected_ids)} tasks in round {round_number} '
            f'for project {self.project.title}'
        )
        
        return {
            'round_id': round_obj.id,
            'round_number': round_number,
            'task_ids': selected_ids,
            'task_scores': {tid: scores.get(tid, 0) for tid in selected_ids},
            'strategy_used': strategy_name or self.config.strategy,
            'avg_uncertainty': float(avg_uncertainty),
            'diversity_score': 0.0,  # TODO: compute diversity score
            'selection_summary': {
                'total_candidates': len(candidates),
                'selected': len(selected_ids),
                'avg_score': float(np.mean(list(scores.values()))) if scores else 0,
            },
        }
```

## 验证检查点

- [ ] 所有策略文件创建成功
- [ ] 策略注册表正确配置
- [ ] TaskSelector功能正常
- [ ] 各策略的compute_scores方法工作正常
- [ ] 各策略的select方法返回正确格式
- [ ] 混合策略正确组合各子策略分数

## 下一步

执行 `04_data_quality_backend.md` 创建数据质量评估后端模块。
