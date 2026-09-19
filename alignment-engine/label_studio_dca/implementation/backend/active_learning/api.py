"""
Active Learning API interfaces.

This module provides API-like interfaces for the active learning module.
In a Django project, these would be Django REST Framework views.
Here we provide standalone implementations.
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from backend.active_learning.models import (
    ActiveLearningConfig,
    ActiveLearningRound,
    SelectionResult,
    TaskData,
    ActiveLearningFeedback,
)
from backend.active_learning.selectors import TaskSelector

logger = logging.getLogger(__name__)


class ActiveLearningAPI:
    """
    API interface for Active Learning module.
    
    Provides methods that would typically be exposed as REST endpoints.
    """
    
    def __init__(self):
        """Initialize API."""
        self.configs: Dict[int, ActiveLearningConfig] = {}
        self.rounds: Dict[int, List[ActiveLearningRound]] = {}
        self.selectors: Dict[int, TaskSelector] = {}
        self._next_config_id = 1
        self._next_round_id = 1
    
    def create_config(
        self,
        project_id: int,
        strategy: str = 'uncertainty',
        batch_size: int = 10,
        **kwargs
    ) -> ActiveLearningConfig:
        """
        Create active learning configuration.
        
        Args:
            project_id: Project ID
            strategy: Strategy name
            batch_size: Batch size for selection
            **kwargs: Additional configuration
        
        Returns:
            Created ActiveLearningConfig
        """
        from backend.active_learning.models import StrategyType, UncertaintyMethod
        
        config = ActiveLearningConfig(
            id=self._next_config_id,
            project_id=project_id,
            strategy=StrategyType(strategy),
            batch_size=batch_size,
            **kwargs
        )
        
        self.configs[config.id] = config
        self.selectors[config.id] = TaskSelector(config)
        self.rounds[config.id] = []
        self._next_config_id += 1
        
        logger.info(f'Created active learning config {config.id} for project {project_id}')
        
        return config
    
    def get_config(self, config_id: int) -> Optional[ActiveLearningConfig]:
        """
        Get active learning configuration.
        
        Args:
            config_id: Configuration ID
        
        Returns:
            ActiveLearningConfig or None
        """
        return self.configs.get(config_id)
    
    def list_configs(self, project_id: Optional[int] = None) -> List[ActiveLearningConfig]:
        """
        List active learning configurations.
        
        Args:
            project_id: Filter by project ID
        
        Returns:
            List of ActiveLearningConfig
        """
        configs = list(self.configs.values())
        
        if project_id is not None:
            configs = [c for c in configs if c.project_id == project_id]
        
        return configs
    
    def update_config(
        self,
        config_id: int,
        **kwargs
    ) -> Optional[ActiveLearningConfig]:
        """
        Update active learning configuration.
        
        Args:
            config_id: Configuration ID
            **kwargs: Fields to update
        
        Returns:
            Updated ActiveLearningConfig or None
        """
        config = self.configs.get(config_id)
        if not config:
            return None
        
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        config.updated_at = datetime.now()
        
        # Update selector
        self.selectors[config_id] = TaskSelector(config)
        
        logger.info(f'Updated active learning config {config_id}')
        
        return config
    
    def toggle_config(self, config_id: int) -> Optional[Dict[str, Any]]:
        """
        Toggle active learning configuration enabled state.
        
        Args:
            config_id: Configuration ID
        
        Returns:
            Dictionary with updated state
        """
        config = self.configs.get(config_id)
        if not config:
            return None
        
        config.is_enabled = not config.is_enabled
        config.updated_at = datetime.now()
        
        return {
            'id': config.id,
            'is_enabled': config.is_enabled,
            'message': f'Active learning {"enabled" if config.is_enabled else "disabled"}',
        }
    
    def select_tasks(
        self,
        config_id: int,
        tasks: List[TaskData],
        predictions: Optional[Dict[int, List[Dict]]] = None,
        batch_size: Optional[int] = None
    ) -> Optional[SelectionResult]:
        """
        Select tasks for annotation.
        
        Args:
            config_id: Configuration ID
            tasks: List of tasks
            predictions: Predictions for tasks
            batch_size: Batch size override
        
        Returns:
            SelectionResult or None
        """
        config = self.configs.get(config_id)
        if not config:
            return None
        
        if not config.is_enabled:
            logger.warning(f'Active learning is disabled for config {config_id}')
            return None
        
        selector = self.selectors.get(config_id)
        if not selector:
            selector = TaskSelector(config)
            self.selectors[config_id] = selector
        
        # Get previously selected tasks
        previous_rounds = self.rounds.get(config_id, [])
        exclude_selected = []
        for round_obj in previous_rounds:
            if not round_obj.is_completed:
                exclude_selected.extend(round_obj.selected_tasks)
        
        # Select tasks
        result = selector.select_tasks(
            tasks=tasks,
            predictions=predictions,
            batch_size=batch_size,
            exclude_annotated=True,
            exclude_selected=exclude_selected,
        )
        
        # Create round
        round_number = len(self.rounds.get(config_id, [])) + 1
        round_obj = ActiveLearningRound(
            id=self._next_round_id,
            config_id=config_id,
            round_number=round_number,
            selected_tasks=result.selected_task_ids,
            task_count=len(result.selected_task_ids),
            strategy_used=result.strategy_used,
            selection_scores=result.task_scores,
            avg_uncertainty=result.avg_uncertainty,
            diversity_score=result.diversity_score,
        )
        
        if config_id not in self.rounds:
            self.rounds[config_id] = []
        self.rounds[config_id].append(round_obj)
        self._next_round_id += 1
        
        # Update result with round info
        result.round_id = round_obj.id
        result.round_number = round_number
        
        logger.info(
            f'Selected {len(result.selected_task_ids)} tasks '
            f'(config: {config_id}, round: {round_number})'
        )
        
        return result
    
    def get_rounds(self, config_id: int) -> List[ActiveLearningRound]:
        """
        Get rounds for a configuration.
        
        Args:
            config_id: Configuration ID
        
        Returns:
            List of ActiveLearningRound
        """
        return self.rounds.get(config_id, [])
    
    def get_status(self, project_id: int) -> Dict[str, Any]:
        """
        Get active learning status for a project.
        
        Args:
            project_id: Project ID
        
        Returns:
            Status dictionary
        """
        configs = self.list_configs(project_id)
        
        if not configs:
            return {
                'configured': False,
                'is_enabled': False,
            }
        
        config = configs[0]
        rounds = self.rounds.get(config.id, [])
        
        return {
            'configured': True,
            'is_enabled': config.is_enabled,
            'strategy': config.strategy.value,
            'total_rounds': len(rounds),
            'latest_round': rounds[-1].to_dict() if rounds else None,
            'pending_tasks': sum(
                len(r.selected_tasks) for r in rounds if not r.is_completed
            ),
        }
    
    def add_feedback(
        self,
        config_id: int,
        task_id: int,
        feedback_type: str,
        comment: Optional[str] = None,
        created_by: Optional[int] = None
    ) -> Optional[ActiveLearningFeedback]:
        """
        Add feedback for active learning.
        
        Args:
            config_id: Configuration ID
            task_id: Task ID
            feedback_type: Type of feedback
            comment: Optional comment
            created_by: User ID
        
        Returns:
            ActiveLearningFeedback or None
        """
        config = self.configs.get(config_id)
        if not config:
            return None
        
        feedback = ActiveLearningFeedback(
            id=0,  # Would be assigned by database
            config_id=config_id,
            task_id=task_id,
            feedback_type=feedback_type,
            comment=comment,
            created_by=created_by,
        )
        
        logger.info(
            f'Added feedback for task {task_id}: {feedback_type}'
        )
        
        return feedback


# Global API instance
active_learning_api = ActiveLearningAPI()
