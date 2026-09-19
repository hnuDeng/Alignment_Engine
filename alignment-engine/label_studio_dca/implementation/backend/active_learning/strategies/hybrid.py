"""
Hybrid strategy combining multiple active learning strategies.
"""

import logging
from typing import Any, Dict, List, Tuple

import numpy as np

from backend.active_learning.strategies.base import BaseStrategy
from backend.active_learning.strategies.uncertainty import UncertaintySampling
from backend.active_learning.strategies.diversity import DiversitySampling
from backend.active_learning.strategies.committee import QueryByCommittee

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
        tasks: List[Dict[str, Any]],
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
        tasks: List[Dict[str, Any]],
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
