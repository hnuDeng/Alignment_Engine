"""
Task selector for active learning.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from backend.active_learning.models import (
    ActiveLearningConfig,
    ActiveLearningRound,
    SelectionResult,
    TaskData,
    TaskScore,
)

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
        self.strategy = config.get_strategy_instance()
    
    def get_candidate_tasks(
        self,
        tasks: List[TaskData],
        exclude_annotated: bool = True,
        exclude_selected: Optional[List[int]] = None
    ) -> List[TaskData]:
        """
        Get candidate tasks for selection.
        
        Args:
            tasks: List of all tasks
            exclude_annotated: Whether to exclude annotated tasks
            exclude_selected: List of task IDs to exclude
        
        Returns:
            List of candidate tasks
        """
        candidates = tasks
        
        if exclude_annotated:
            candidates = [t for t in candidates if not t.is_labeled]
        
        if exclude_selected:
            candidates = [t for t in candidates if t.id not in exclude_selected]
        
        return candidates
    
    def prepare_task_data(self, tasks: List[TaskData]) -> List[Dict[str, Any]]:
        """
        Prepare task data for strategy.
        
        Args:
            tasks: List of tasks
        
        Returns:
            List of task data dictionaries
        """
        return [task.to_dict() for task in tasks]
    
    def prepare_predictions(
        self,
        tasks: List[TaskData],
        predictions: Optional[Dict[int, List[Dict]]] = None
    ) -> Dict[int, List[Dict]]:
        """
        Prepare predictions for strategy.
        
        Args:
            tasks: List of tasks
            predictions: Raw predictions
        
        Returns:
            Formatted predictions dictionary
        """
        if predictions is None:
            return {}
        
        return predictions
    
    def select_tasks(
        self,
        tasks: List[TaskData],
        predictions: Optional[Dict[int, List[Dict]]] = None,
        batch_size: Optional[int] = None,
        strategy_name: Optional[str] = None,
        exclude_annotated: bool = True,
        exclude_selected: Optional[List[int]] = None
    ) -> SelectionResult:
        """
        Select tasks for annotation.
        
        Args:
            tasks: List of all tasks
            predictions: Predictions for tasks
            batch_size: Number of tasks to select
            strategy_name: Strategy to use
            exclude_annotated: Whether to exclude annotated tasks
            exclude_selected: List of task IDs to exclude
        
        Returns:
            SelectionResult with selected tasks
        """
        from backend.active_learning.strategies import get_strategy
        
        # Use config values if not specified
        batch_size = batch_size or self.config.batch_size
        
        # Get strategy
        if strategy_name:
            strategy = get_strategy(strategy_name)
        else:
            strategy = self.strategy
        
        # Get candidate tasks
        candidates = self.get_candidate_tasks(
            tasks,
            exclude_annotated=exclude_annotated,
            exclude_selected=exclude_selected
        )
        
        if not candidates:
            logger.warning('No candidate tasks available for selection')
            return SelectionResult(
                round_id=0,
                round_number=0,
                selected_task_ids=[],
                task_scores={},
                strategy_used=strategy_name or self.config.strategy.value,
                avg_uncertainty=0.0,
                diversity_score=0.0,
                selection_summary={'message': 'No tasks available'},
            )
        
        # Prepare data
        task_data = self.prepare_task_data(candidates)
        prepared_predictions = self.prepare_predictions(candidates, predictions)
        
        # Select tasks
        selected_ids, scores = strategy.select(
            tasks=task_data,
            predictions=prepared_predictions,
            batch_size=batch_size,
        )
        
        # Compute metrics
        avg_uncertainty = float(np.mean([scores.get(tid, 0) for tid in selected_ids])) if selected_ids else 0
        
        # Create task scores
        task_scores = {
            tid: TaskScore(
                task_id=tid,
                final_score=scores.get(tid, 0.0),
                rank=rank,
                is_selected=True,
            )
            for rank, tid in enumerate(selected_ids, 1)
        }
        
        # Create result
        result = SelectionResult(
            round_id=0,  # Would be assigned by database
            round_number=0,  # Would be assigned by database
            selected_task_ids=selected_ids,
            task_scores={tid: scores.get(tid, 0) for tid in selected_ids},
            strategy_used=strategy_name or self.config.strategy.value,
            avg_uncertainty=avg_uncertainty,
            diversity_score=self._compute_diversity_score(selected_ids, task_data) if selected_ids else 0.0,
            selection_summary={
                'total_candidates': len(candidates),
                'selected': len(selected_ids),
                'avg_score': float(np.mean(list(scores.values()))) if scores else 0,
            },
        )
        
        logger.info(
            f'Selected {len(selected_ids)} tasks '
            f'(strategy: {result.strategy_used}, avg_uncertainty: {avg_uncertainty:.3f})'
        )
        
        return result


