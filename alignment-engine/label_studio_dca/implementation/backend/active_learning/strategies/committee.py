"""
Query by Committee (QBC) strategy for active learning.
"""

import logging
from typing import Any, Dict, List, Tuple

import numpy as np

from backend.active_learning.strategies.base import BaseStrategy

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
        else:
            # Default to vote entropy
            return self.compute_vote_entropy(predictions)
    
    def compute_scores(
        self,
        tasks: List[Dict[str, Any]],
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
        tasks: List[Dict[str, Any]],
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
