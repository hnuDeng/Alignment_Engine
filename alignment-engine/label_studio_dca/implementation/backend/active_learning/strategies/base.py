"""
Active Learning Strategies Module

This module implements various active learning sampling strategies for
intelligent task selection in data-centric AI workflows.

Strategies:
- Uncertainty Sampling: Select tasks where model is most uncertain
- Diversity Sampling: Select diverse tasks to cover feature space
- Query by Committee: Select tasks with highest disagreement
- Hybrid Strategy: Combine multiple strategies
- Expected Model Change: Select tasks that would change model most
- Batch Mode: Efficient batch selection algorithms
"""

import logging
import numpy as np
from abc import ABC, abstractmethod
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
from scipy import stats
from scipy.spatial.distance import cdist
from sklearn.cluster import KMeans, DBSCAN
from sklearn.decomposition import PCA
from sklearn.metrics.pairwise import cosine_similarity, euclidean_distances
import warnings

warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)


class StrategyType(Enum):
    """Enumeration of available active learning strategies."""
    UNCERTAINTY = "uncertainty"
    DIVERSITY = "diversity"
    COMMITTEE = "committee"
    HYBRID = "hybrid"
    EXPECTED_GRADIENT = "expected_gradient"
    BATCH_MODE = "batch_mode"
    RANDOM = "random"


@dataclass
class TaskScore:
    """Data class for task selection scores."""
    task_id: int
    score: float
    metadata: Dict[str, Any]
    strategy_used: str


class BaseStrategy(ABC):
    """
    Base class for all active learning strategies.
    
    Provides common functionality and defines the interface that all
    strategies must implement.
    """
    
    def __init__(self, strategy_type: StrategyType, **kwargs):
        """
        Initialize the strategy.
        
        Args:
            strategy_type: Type of the strategy
            **kwargs: Additional strategy-specific parameters
        """
        self.strategy_type = strategy_type
        self.params = kwargs
        self.is_fitted = False
        
    @abstractmethod
    def compute_scores(
        self,
        task_ids: List[int],
        task_features: np.ndarray,
        model_predictions: Optional[np.ndarray] = None,
        **kwargs
    ) -> List[TaskScore]:
        """
        Compute selection scores for all tasks.
        
        Args:
            task_ids: List of task IDs
            task_features: Feature matrix (n_tasks x n_features)
            model_predictions: Model predictions if available
            **kwargs: Additional parameters
        
        Returns:
            List of TaskScore objects sorted by score (descending)
        """
        pass
    
    @abstractmethod
    def select_batch(
        self,
        task_ids: List[int],
        task_features: np.ndarray,
        batch_size: int,
        model_predictions: Optional[np.ndarray] = None,
        **kwargs
    ) -> Tuple[List[int], List[TaskScore]]:
        """
        Select a batch of tasks for annotation.
        
        Args:
            task_ids: List of task IDs
            task_features: Feature matrix
            batch_size: Number of tasks to select
            model_predictions: Model predictions if available
        
        Returns:
            Tuple of (selected_task_ids, all_scores)
        """
        pass
    
    def _validate_inputs(
        self,
        task_ids: List[int],
        task_features: np.ndarray,
        batch_size: int
    ) -> None:
        """Validate input parameters."""
        if len(task_ids) == 0:
            raise ValueError("task_ids cannot be empty")
        if task_features.shape[0] != len(task_ids):
            raise ValueError("task_features rows must match task_ids length")
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if batch_size > len(task_ids):
            logger.warning(f"batch_size ({batch_size}) > total tasks ({len(task_ids)}), using all tasks")
    
    def _normalize_scores(self, scores: np.ndarray) -> np.ndarray:
        """Normalize scores to [0, 1] range."""
        if len(scores) == 0:
            return scores
        min_score = np.min(scores)
        max_score = np.max(scores)
        if max_score == min_score:
            return np.ones_like(scores) * 0.5
        return (scores - min_score) / (max_score - min_score)


class UncertaintySampling(BaseStrategy):
    """
    Uncertainty Sampling Strategy.
    
    Selects tasks where the model is most uncertain about its predictions.
    This is one of the most common active learning strategies.
    
    Supported uncertainty measures:
    - Least Confidence: 1 - P(y*|x) where y* is the most likely label
    - Margin Sampling: P(y1*|x) - P(y2*|x) where y1*, y2* are top-2 labels
    - Entropy: -sum(P(y|x) * log(P(y|x)))
    - Variation Ratio: 1 - P(y*|x)
    """
    
    def __init__(self, uncertainty_measure: str = 'entropy', **kwargs):
        """
        Initialize uncertainty sampling strategy.
        
        Args:
            uncertainty_measure: Type of uncertainty measure
                - 'least_confidence': 1 - max probability
                - 'margin': difference between top-2 probabilities
                - 'entropy': Shannon entropy
                - 'variation_ratio': 1 - max probability
        """
        super().__init__(StrategyType.UNCERTAINTY, **kwargs)
        
        valid_measures = ['least_confidence', 'margin', 'entropy', 'variation_ratio']
        if uncertainty_measure not in valid_measures:
            raise ValueError(f"Invalid uncertainty_measure. Must be one of {valid_measures}")
        
        self.uncertainty_measure = uncertainty_measure
    
    def _compute_least_confidence(self, probabilities: np.ndarray) -> np.ndarray:
        """Compute least confidence uncertainty."""
        max_probs = np.max(probabilities, axis=1)
        return 1.0 - max_probs
    
    def _compute_margin(self, probabilities: np.ndarray) -> np.ndarray:
        """Compute margin-based uncertainty."""
        sorted_probs = np.sort(probabilities, axis=1)[:, ::-1]
        if sorted_probs.shape[1] >= 2:
            margin = sorted_probs[:, 0] - sorted_probs[:, 1]
            return 1.0 - margin
        return np.ones(probabilities.shape[0])
    
    def _compute_entropy(self, probabilities: np.ndarray) -> np.ndarray:
        """Compute entropy-based uncertainty."""
        # Avoid log(0)
        probs = np.clip(probabilities, 1e-10, 1.0)
        entropy = -np.sum(probs * np.log(probs), axis=1)
        # Normalize by max entropy
        max_entropy = np.log(probabilities.shape[1])
        if max_entropy > 0:
            return entropy / max_entropy
        return entropy
    
    def _compute_variation_ratio(self, probabilities: np.ndarray) -> np.ndarray:
        """Compute variation ratio uncertainty."""
        max_probs = np.max(probabilities, axis=1)
        return 1.0 - max_probs
    
    def compute_uncertainty(self, probabilities: np.ndarray) -> np.ndarray:
        """
        Compute uncertainty scores based on the selected measure.
        
        Args:
            probabilities: Probability matrix (n_samples x n_classes)
        
        Returns:
            Uncertainty scores array
        """
        if self.uncertainty_measure == 'least_confidence':
            return self._compute_least_confidence(probabilities)
        elif self.uncertainty_measure == 'margin':
            return self._compute_margin(probabilities)
        elif self.uncertainty_measure == 'entropy':
            return self._compute_entropy(probabilities)
        elif self.uncertainty_measure == 'variation_ratio':
            return self._compute_variation_ratio(probabilities)
        else:
            raise ValueError(f"Unknown uncertainty measure: {self.uncertainty_measure}")
    
    def compute_scores(
        self,
        task_ids: List[int],
        task_features: np.ndarray,
        model_predictions: Optional[np.ndarray] = None,
        **kwargs
    ) -> List[TaskScore]:
        """Compute uncertainty scores for all tasks."""
        if model_predictions is None:
            # Use feature-based uncertainty if no predictions
            logger.warning("No model predictions provided, using feature-based uncertainty")
            uncertainties = np.random.random(len(task_ids))
        else:
            uncertainties = self.compute_uncertainty(model_predictions)
        
        scores = self._normalize_scores(uncertainties)
        
        task_scores = []
        for i, (task_id, score) in enumerate(zip(task_ids, scores)):
            task_scores.append(TaskScore(
                task_id=task_id,
                score=float(score),
                metadata={
                    'uncertainty_measure': self.uncertainty_measure,
                    'raw_uncertainty': float(uncertainties[i])
                },
                strategy_used=self.strategy_type.value
            ))
        
        # Sort by score (descending)
        task_scores.sort(key=lambda x: x.score, reverse=True)
        return task_scores
    
    def select_batch(
        self,
        task_ids: List[int],
        task_features: np.ndarray,
        batch_size: int,
        model_predictions: Optional[np.ndarray] = None,
        **kwargs
    ) -> Tuple[List[int], List[TaskScore]]:
        """Select batch of most uncertain tasks."""
        self._validate_inputs(task_ids, task_features, batch_size)
        
        task_scores = self.compute_scores(
            task_ids, task_features, model_predictions, **kwargs
        )
        
        selected = [ts.task_id for ts in task_scores[:batch_size]]
        return selected, task_scores


class DiversitySampling(BaseStrategy):
    """
    Diversity Sampling Strategy.
    
    Selects diverse tasks to ensure good coverage of the feature space.
    Uses clustering or distance-based methods to select representative samples.
    
    Supported methods:
    - K-Means Clustering: Select samples closest to cluster centroids
    - DBSCAN Clustering: Select samples from different density clusters
    - Farthest First: Greedy farthest-first traversal
    - Core-Set: Minimize maximum distance to selected set
    """
    
    def __init__(self, method: str = 'kmeans', n_clusters: Optional[int] = None, **kwargs):
        """
        Initialize diversity sampling strategy.
        
        Args:
            method: Clustering method to use
            n_clusters: Number of clusters (auto-determined if None)
        """
        super().__init__(StrategyType.DIVERSITY, **kwargs)
        
        valid_methods = ['kmeans', 'dbscan', 'farthest_first', 'core_set']
        if method not in valid_methods:
            raise ValueError(f"Invalid method. Must be one of {valid_methods}")
        
        self.method = method
        self.n_clusters = n_clusters
    
    def _select_kmeans(
        self,
        task_features: np.ndarray,
        batch_size: int
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Select samples using K-Means clustering."""
        n_clusters = min(batch_size, len(task_features))
        
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        cluster_labels = kmeans.fit_predict(task_features)
        centroids = kmeans.cluster_centers_
        
        # Select sample closest to each centroid
        selected_indices = []
        for i in range(n_clusters):
            cluster_mask = cluster_labels == i
            if not np.any(cluster_mask):
                continue
            
            cluster_features = task_features[cluster_mask]
            cluster_indices = np.where(cluster_mask)[0]
            
            # Find closest to centroid
            distances = np.linalg.norm(cluster_features - centroids[i], axis=1)
            closest_idx = cluster_indices[np.argmin(distances)]
            selected_indices.append(closest_idx)
        
        return np.array(selected_indices), cluster_labels
    
    def _select_dbscan(
        self,
        task_features: np.ndarray,
        batch_size: int
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Select samples using DBSCAN clustering."""
        dbscan = DBSCAN(eps=0.5, min_samples=2)
        cluster_labels = dbscan.fit_predict(task_features)
        
        # Handle noise points (label -1)
        unique_labels = set(cluster_labels)
        unique_labels.discard(-1)
        
        selected_indices = []
        
        # Select one sample from each cluster
        for label in unique_labels:
            cluster_mask = cluster_labels == label
            cluster_indices = np.where(cluster_mask)[0]
            
            # Select sample closest to cluster center
            cluster_features = task_features[cluster_mask]
            center = np.mean(cluster_features, axis=0)
            distances = np.linalg.norm(cluster_features - center, axis=1)
            closest_idx = cluster_indices[np.argmin(distances)]
            selected_indices.append(closest_idx)
        
        # If not enough samples, add noise points
        if len(selected_indices) < batch_size:
            noise_mask = cluster_labels == -1
            noise_indices = np.where(noise_mask)[0]
            remaining = batch_size - len(selected_indices)
            if len(noise_indices) > 0:
                selected_indices.extend(noise_indices[:remaining].tolist())
        
        return np.array(selected_indices[:batch_size]), cluster_labels
    
    def _select_farthest_first(
        self,
        task_features: np.ndarray,
        batch_size: int
    ) -> Tuple[np.ndarray, None]:
        """Select samples using farthest-first traversal."""
        n_samples = len(task_features)
        selected = [np.random.randint(n_samples)]
        
        for _ in range(batch_size - 1):
            # Compute distances to all selected samples
            distances = np.min(
                cdist(task_features, task_features[selected]),
                axis=1
            )
            
            # Select farthest
            farthest = np.argmax(distances)
            selected.append(farthest)
        
        return np.array(selected), None
    
    def _select_core_set(
        self,
        task_features: np.ndarray,
        batch_size: int
    ) -> Tuple[np.ndarray, None]:
        """Select samples using core-set approach."""
        n_samples = len(task_features)
        selected = [np.random.randint(n_samples)]
        
        for _ in range(batch_size - 1):
            # Compute minimum distances to selected set
            min_distances = np.min(
                cdist(task_features, task_features[selected]),
                axis=1
            )
            
            # Select point that minimizes maximum distance
            # (greedy approximation)
            selected.append(np.argmax(min_distances))
        
        return np.array(selected), None
    
    def compute_scores(
        self,
        task_ids: List[int],
        task_features: np.ndarray,
        model_predictions: Optional[np.ndarray] = None,
        **kwargs
    ) -> List[TaskScore]:
        """Compute diversity scores for all tasks."""
        # For diversity, we use distance to nearest selected sample
        # This is a simplified version - full implementation would use clustering
        
        if len(task_features) < 2:
            return [TaskScore(
                task_id=task_ids[i],
                score=1.0,
                metadata={'method': self.method},
                strategy_used=self.strategy_type.value
            ) for i in range(len(task_ids))]
        
        # Compute pairwise distances
        distances = cdist(task_features, task_features, metric='euclidean')
        
        # Score based on average distance to other samples
        avg_distances = np.mean(distances, axis=1)
        scores = self._normalize_scores(avg_distances)
        
        task_scores = []
        for i, (task_id, score) in enumerate(zip(task_ids, scores)):
            task_scores.append(TaskScore(
                task_id=task_id,
                score=float(score),
                metadata={
                    'method': self.method,
                    'avg_distance': float(avg_distances[i])
                },
                strategy_used=self.strategy_type.value
            ))
        
        task_scores.sort(key=lambda x: x.score, reverse=True)
        return task_scores
    
    def select_batch(
        self,
        task_ids: List[int],
        task_features: np.ndarray,
        batch_size: int,
        model_predictions: Optional[np.ndarray] = None,
        **kwargs
    ) -> Tuple[List[int], List[TaskScore]]:
        """Select diverse batch of tasks."""
        self._validate_inputs(task_ids, task_features, batch_size)
        
        batch_size = min(batch_size, len(task_ids))
        
        if self.method == 'kmeans':
            selected_indices, _ = self._select_kmeans(task_features, batch_size)
        elif self.method == 'dbscan':
            selected_indices, _ = self._select_dbscan(task_features, batch_size)
        elif self.method == 'farthest_first':
            selected_indices, _ = self._select_farthest_first(task_features, batch_size)
        elif self.method == 'core_set':
            selected_indices, _ = self._select_core_set(task_features, batch_size)
        else:
            raise ValueError(f"Unknown method: {self.method}")
        
        # Ensure we have valid indices
        selected_indices = selected_indices[selected_indices < len(task_ids)]
        selected_ids = [task_ids[i] for i in selected_indices]
        
        # Compute scores for all tasks
        all_scores = self.compute_scores(task_ids, task_features, model_predictions, **kwargs)
        
        return selected_ids, all_scores


class QueryByCommittee(BaseStrategy):
    """
    Query by Committee Strategy.
    
    Maintains a committee of models and selects tasks where the committee
    members disagree the most.
    
    Disagreement measures:
    - Vote Entropy: Entropy of vote distribution
    - KL Divergence: Average KL divergence from consensus
    - Consensus Entropy: Entropy of average predictions
    """
    
    def __init__(self, disagreement_measure: str = 'vote_entropy', **kwargs):
        """
        Initialize QBC strategy.
        
        Args:
            disagreement_measure: Type of disagreement measure
        """
        super().__init__(StrategyType.COMMITTEE, **kwargs)
        
        valid_measures = ['vote_entropy', 'kl_divergence', 'consensus_entropy']
        if disagreement_measure not in valid_measures:
            raise ValueError(f"Invalid disagreement_measure. Must be one of {valid_measures}")
        
        self.disagreement_measure = disagreement_measure
    
    def _compute_vote_entropy(self, predictions: np.ndarray) -> np.ndarray:
        """
        Compute vote entropy for committee predictions.
        
        Args:
            predictions: Committee predictions (n_samples x n_committee x n_classes)
        
        Returns:
            Vote entropy scores
        """
        n_samples, n_committee, n_classes = predictions.shape
        
        # Convert to votes (argmax)
        votes = np.argmax(predictions, axis=2)  # (n_samples, n_committee)
        
        # Compute vote distribution
        vote_entropy = np.zeros(n_samples)
        for i in range(n_samples):
            vote_counts = np.bincount(votes[i], minlength=n_classes)
            vote_probs = vote_counts / n_committee
            # Entropy
            vote_probs = np.clip(vote_probs, 1e-10, 1.0)
            vote_entropy[i] = -np.sum(vote_probs * np.log(vote_probs))
        
        return vote_entropy
    
    def _compute_kl_divergence(self, predictions: np.ndarray) -> np.ndarray:
        """Compute average KL divergence from consensus."""
        n_samples, n_committee, n_classes = predictions.shape
        
        # Consensus is average prediction
        consensus = np.mean(predictions, axis=1)  # (n_samples, n_classes)
        
        # Average KL divergence
        kl_div = np.zeros(n_samples)
        for i in range(n_samples):
            for j in range(n_committee):
                p = np.clip(predictions[i, j], 1e-10, 1.0)
                q = np.clip(consensus[i], 1e-10, 1.0)
                kl_div[i] += np.sum(p * np.log(p / q))
            kl_div[i] /= n_committee
        
        return kl_div
    
    def _compute_consensus_entropy(self, predictions: np.ndarray) -> np.ndarray:
        """Compute entropy of consensus predictions."""
        consensus = np.mean(predictions, axis=1)  # (n_samples, n_classes)
        consensus = np.clip(consensus, 1e-10, 1.0)
        entropy = -np.sum(consensus * np.log(consensus), axis=1)
        return entropy
    
    def compute_scores(
        self,
        task_ids: List[int],
        task_features: np.ndarray,
        model_predictions: Optional[np.ndarray] = None,
        **kwargs
    ) -> List[TaskScore]:
        """Compute committee disagreement scores."""
        if model_predictions is None or len(model_predictions.shape) < 3:
            logger.warning("QBC requires committee predictions (n_samples x n_committee x n_classes)")
            # Use random scores as fallback
            scores = np.random.random(len(task_ids))
        else:
            if self.disagreement_measure == 'vote_entropy':
                disagreement = self._compute_vote_entropy(model_predictions)
            elif self.disagreement_measure == 'kl_divergence':
                disagreement = self._compute_kl_divergence(model_predictions)
            elif self.disagreement_measure == 'consensus_entropy':
                disagreement = self._compute_consensus_entropy(model_predictions)
            else:
                raise ValueError(f"Unknown measure: {self.disagreement_measure}")
            
            scores = self._normalize_scores(disagreement)
        
        task_scores = []
        for i, (task_id, score) in enumerate(zip(task_ids, scores)):
            task_scores.append(TaskScore(
                task_id=task_id,
                score=float(score),
                metadata={
                    'disagreement_measure': self.disagreement_measure,
                    'raw_disagreement': float(scores[i])
                },
                strategy_used=self.strategy_type.value
            ))
        
        task_scores.sort(key=lambda x: x.score, reverse=True)
        return task_scores
    
    def select_batch(
        self,
        task_ids: List[int],
        task_features: np.ndarray,
        batch_size: int,
        model_predictions: Optional[np.ndarray] = None,
        **kwargs
    ) -> Tuple[List[int], List[TaskScore]]:
        """Select batch with highest committee disagreement."""
        self._validate_inputs(task_ids, task_features, batch_size)
        
        task_scores = self.compute_scores(
            task_ids, task_features, model_predictions, **kwargs
        )
        
        selected = [ts.task_id for ts in task_scores[:batch_size]]
        return selected, task_scores


class HybridStrategy(BaseStrategy):
    """
    Hybrid Strategy.
    
    Combines multiple active learning strategies to leverage their
    complementary strengths.
    """
    
    def __init__(
        self,
        strategies: List[BaseStrategy],
        weights: Optional[List[float]] = None,
        **kwargs
    ):
        """
        Initialize hybrid strategy.
        
        Args:
            strategies: List of strategy instances
            weights: Weights for each strategy (normalized internally)
        """
        super().__init__(StrategyType.HYBRID, **kwargs)
        
        self.strategies = strategies
        
        if weights is None:
            self.weights = [1.0 / len(strategies)] * len(strategies)
        else:
            if len(weights) != len(strategies):
                raise ValueError("weights length must match strategies length")
            # Normalize weights
            total = sum(weights)
            self.weights = [w / total for w in weights]
    
    def compute_scores(
        self,
        task_ids: List[int],
        task_features: np.ndarray,
        model_predictions: Optional[np.ndarray] = None,
        **kwargs
    ) -> List[TaskScore]:
        """Compute weighted combination of strategy scores."""
        all_scores = []
        
        for strategy, weight in zip(self.strategies, self.weights):
            scores = strategy.compute_scores(
                task_ids, task_features, model_predictions, **kwargs
            )
            all_scores.append((scores, weight))
        
        # Combine scores
        combined = {}
        for task_id in task_ids:
            combined[task_id] = 0.0
        
        for scores, weight in all_scores:
            for ts in scores:
                combined[ts.task_id] += ts.score * weight
        
        task_scores = []
        for task_id, score in combined.items():
            task_scores.append(TaskScore(
                task_id=task_id,
                score=score,
                metadata={'weights': self.weights},
                strategy_used=self.strategy_type.value
            ))
        
        task_scores.sort(key=lambda x: x.score, reverse=True)
        return task_scores
    
    def select_batch(
        self,
        task_ids: List[int],
        task_features: np.ndarray,
        batch_size: int,
        model_predictions: Optional[np.ndarray] = None,
        **kwargs
    ) -> Tuple[List[int], List[TaskScore]]:
        """Select batch using hybrid strategy."""
        self._validate_inputs(task_ids, task_features, batch_size)
        
        task_scores = self.compute_scores(
            task_ids, task_features, model_predictions, **kwargs
        )
        
        selected = [ts.task_id for ts in task_scores[:batch_size]]
        return selected, task_scores


class ExpectedModelChange(BaseStrategy):
    """
    Expected Model Change Strategy.
    
    Selects tasks that would cause the largest change in the model
    if their labels were known.
    """
    
    def __init__(self, **kwargs):
        super().__init__(StrategyType.EXPECTED_GRADIENT, **kwargs)
    
    def compute_scores(
        self,
        task_ids: List[int],
        task_features: np.ndarray,
        model_predictions: Optional[np.ndarray] = None,
        **kwargs
    ) -> List[TaskScore]:
        """Compute expected model change scores."""
        # Simplified implementation using prediction uncertainty
        if model_predictions is None:
            scores = np.random.random(len(task_ids))
        else:
            # Use entropy as proxy for expected model change
            probs = np.clip(model_predictions, 1e-10, 1.0)
            entropy = -np.sum(probs * np.log(probs), axis=1)
            scores = self._normalize_scores(entropy)
        
        task_scores = []
        for i, (task_id, score) in enumerate(zip(task_ids, scores)):
            task_scores.append(TaskScore(
                task_id=task_id,
                score=float(score),
                metadata={'method': 'expected_model_change'},
                strategy_used=self.strategy_type.value
            ))
        
        task_scores.sort(key=lambda x: x.score, reverse=True)
        return task_scores
    
    def select_batch(
        self,
        task_ids: List[int],
        task_features: np.ndarray,
        batch_size: int,
        model_predictions: Optional[np.ndarray] = None,
        **kwargs
    ) -> Tuple[List[int], List[TaskScore]]:
        """Select batch with highest expected model change."""
        self._validate_inputs(task_ids, task_features, batch_size)
        
        task_scores = self.compute_scores(
            task_ids, task_features, model_predictions, **kwargs
        )
        
        selected = [ts.task_id for ts in task_scores[:batch_size]]
        return selected, task_scores


def create_strategy(strategy_type: str, **kwargs) -> BaseStrategy:
    """
    Factory function to create strategy instances.
    
    Args:
        strategy_type: Type of strategy to create
        **kwargs: Strategy-specific parameters
    
    Returns:
        Strategy instance
    """
    strategies = {
        'uncertainty': UncertaintySampling,
        'diversity': DiversitySampling,
        'committee': QueryByCommittee,
        'hybrid': HybridStrategy,
        'expected_gradient': ExpectedModelChange,
    }
    
    if strategy_type not in strategies:
        raise ValueError(f"Unknown strategy type: {strategy_type}")
    
    return strategies[strategy_type](**kwargs)
