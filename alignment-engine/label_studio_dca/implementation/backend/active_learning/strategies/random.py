"""
Random sampling strategy for active learning (baseline).
"""

import logging
import random
from typing import Any, Dict, List, Tuple

from backend.active_learning.strategies.base import BaseStrategy

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
        tasks: List[Dict[str, Any]],
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
        tasks: List[Dict[str, Any]],
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
