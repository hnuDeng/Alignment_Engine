"""
Diversity sampling strategies for active learning.
"""

import logging
from typing import Any, Dict, List, Tuple

import numpy as np

from backend.active_learning.strategies.base import BaseStrategy

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
    
    def extract_features(self, tasks: List[Dict[str, Any]]) -> np.ndarray:
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
            # Cosine distance
            norms = np.linalg.norm(features, axis=1, keepdims=True)
            norms = np.where(norms == 0, 1, norms)
            normalized = features / norms
            return 1 - normalized @ normalized.T
        
        elif self.metric == 'euclidean':
            # Euclidean distance
            diff = features[:, np.newaxis, :] - features[np.newaxis, :, :]
            return np.sqrt(np.sum(diff ** 2, axis=2))
        
        elif self.metric == 'manhattan':
            # Manhattan distance
            diff = features[:, np.newaxis, :] - features[np.newaxis, :, :]
            return np.sum(np.abs(diff), axis=2)
        
        else:
            raise ValueError(f"Unknown metric: {self.metric}")
    
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
    
    def compute_scores(
        self,
        tasks: List[Dict[str, Any]],
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
        
        # Compute distance matrix
        distances = self.compute_distance(features)
        
        # Compute diversity score as average distance to other tasks
        scores = {}
        for i, task_id in enumerate(task_ids):
            avg_distance = float(np.mean(distances[i]))
            scores[task_id] = avg_distance
        
        # Normalize scores
        scores = self._normalize_scores(scores)
        
        logger.debug(
            f'Computed diversity scores for {len(tasks)} tasks '
            f'(metric: {self.metric}, avg: {np.mean(list(scores.values())):.3f})'
        )
        
        return scores
    
    def select(
        self,
        tasks: List[Dict[str, Any]],
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
        selected_ids = self.select_diverse_subset(features, task_ids, batch_size)
        
        # Compute scores for all tasks
        scores = self.compute_scores(tasks, predictions)
        
        logger.info(
            f'Selected {len(selected_ids)} tasks using diversity sampling '
            f'(metric: {self.metric})'
        )
        
        return selected_ids, scores
