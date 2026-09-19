"""
Data-Centric AI Workflow - Unified Entry Point

This module provides a unified interface for all DCA functionality.
"""

import logging
from typing import Any, Dict, List, Optional

from backend.active_learning.api import ActiveLearningAPI
from backend.data_quality.api import DataQualityAPI
from backend.drift_detection.api import DriftDetectionAPI

logger = logging.getLogger(__name__)


class DataCentricAI:
    """
    Unified interface for Data-Centric AI Workflow.
    
    Provides access to all DCA modules through a single entry point.
    """
    
    def __init__(self, project_id: int):
        """
        Initialize DCA workflow.
        
        Args:
            project_id: Project ID
        """
        self.project_id = project_id
        self.active_learning = ActiveLearningAPI()
        self.data_quality = DataQualityAPI()
        self.drift_detection = DriftDetectionAPI()
        
        logger.info(f'Initialized DCA workflow for project {project_id}')
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get overall DCA status.
        
        Returns:
            Status dictionary
        """
        return {
            'project_id': self.project_id,
            'active_learning': self.active_learning.get_status(self.project_id),
            'data_quality': self.data_quality.get_dashboard(self.project_id),
            'drift_detection': {
                'baselines': len(self.drift_detection.list_baselines(self.project_id)),
                'reports': len(self.drift_detection.get_reports(self.project_id)),
                'alerts': len(self.drift_detection.get_alerts(self.project_id)),
            },
        }
    
    def run_full_assessment(
        self,
        tasks: List[Dict[str, Any]],
        annotations: List[Dict[str, Any]],
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Run full DCA assessment.
        
        Args:
            tasks: List of task data
            annotations: List of annotation data
            user_id: User running the assessment
        
        Returns:
            Assessment results
        """
        results = {}
        
        # Run data quality assessment
        try:
            quality_report = self.data_quality.run_assessment(
                project_id=self.project_id,
                tasks=tasks,
                annotations=annotations,
                user_id=user_id,
            )
            results['quality'] = quality_report.to_dict()
        except Exception as e:
            logger.error(f'Quality assessment failed: {str(e)}')
            results['quality'] = {'error': str(e)}
        
        return results


# Convenience function
def create_dca_workflow(project_id: int) -> DataCentricAI:
    """
    Create a DCA workflow instance.
    
    Args:
        project_id: Project ID
    
    Returns:
        DataCentricAI instance
    """
    return DataCentricAI(project_id)
