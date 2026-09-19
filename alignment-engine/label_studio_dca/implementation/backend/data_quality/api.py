"""
Data Quality API interfaces.
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from backend.data_quality.models import (
    QualityReport,
    QualityIssue,
    AnnotatorProfile,
    LabelStats,
    QualityConfig,
    ReportType,
    IssueType,
    SeverityLevel,
)
from backend.data_quality.assessors import QualityAssessmentEngine

logger = logging.getLogger(__name__)


class DataQualityAPI:
    """
    API interface for Data Quality module.
    """
    
    def __init__(self):
        """Initialize API."""
        self.reports: Dict[int, QualityReport] = {}
        self.configs: Dict[int, QualityConfig] = {}
        self._next_report_id = 1
        self._next_issue_id = 1
    
    def run_assessment(
        self,
        project_id: int,
        tasks: List[Dict[str, Any]],
        annotations: List[Dict[str, Any]],
        assessors: Optional[List[str]] = None,
        user_id: Optional[int] = None
    ) -> QualityReport:
        """
        Run quality assessment for a project.
        
        Args:
            project_id: Project ID
            tasks: List of task data
            annotations: List of annotation data
            assessors: Specific assessors to run
            user_id: User running the assessment
        
        Returns:
            QualityReport
        """
        engine = QualityAssessmentEngine(project_id)
        report = engine.run_assessment(
            tasks=tasks,
            annotations=annotations,
            assessors=assessors,
            user_id=user_id,
        )
        
        # Assign IDs
        report.id = self._next_report_id
        self._next_report_id += 1
        
        for i, issue in enumerate(report.issues):
            issue.id = self._next_issue_id
            issue.report_id = report.id
            self._next_issue_id += 1
        
        # Store report
        self.reports[report.id] = report
        
        logger.info(
            f'Quality assessment completed for project {project_id}: '
            f'score={report.overall_score:.3f}'
        )
        
        return report
    
    def get_report(self, report_id: int) -> Optional[QualityReport]:
        """
        Get quality report by ID.
        
        Args:
            report_id: Report ID
        
        Returns:
            QualityReport or None
        """
        return self.reports.get(report_id)
    
    def list_reports(
        self,
        project_id: Optional[int] = None,
        report_type: Optional[str] = None
    ) -> List[QualityReport]:
        """
        List quality reports.
        
        Args:
            project_id: Filter by project ID
            report_type: Filter by report type
        
        Returns:
            List of QualityReport
        """
        reports = list(self.reports.values())
        
        if project_id is not None:
            reports = [r for r in reports if r.project_id == project_id]
        
        if report_type is not None:
            reports = [r for r in reports if r.report_type.value == report_type]
        
        return sorted(reports, key=lambda r: r.created_at, reverse=True)
    
    def get_latest_report(self, project_id: int) -> Optional[QualityReport]:
        """
        Get latest quality report for a project.
        
        Args:
            project_id: Project ID
        
        Returns:
            Latest QualityReport or None
        """
        reports = self.list_reports(project_id=project_id)
        return reports[0] if reports else None
    
    def resolve_issue(
        self,
        issue_id: int,
        user_id: int,
        notes: str = ''
    ) -> Optional[QualityIssue]:
        """
        Resolve a quality issue.
        
        Args:
            issue_id: Issue ID
            user_id: User resolving the issue
            notes: Resolution notes
        
        Returns:
            Updated QualityIssue or None
        """
        for report in self.reports.values():
            for issue in report.issues:
                if issue.id == issue_id:
                    issue.resolve(user_id, notes)
                    return issue
        
        return None
    
    def get_dashboard_data(self, project_id: int) -> Dict[str, Any]:
        """
        Get quality dashboard data.
        
        Args:
            project_id: Project ID
        
        Returns:
            Dashboard data dictionary
        """
        latest_report = self.get_latest_report(project_id)
        
        if not latest_report:
            return {
                'project_id': project_id,
                'has_data': False,
                'message': 'No quality reports available',
            }
        
        # Count issues by severity
        issue_counts = {}
        for issue in latest_report.issues:
            severity = issue.severity.value
            issue_counts[severity] = issue_counts.get(severity, 0) + 1
        
        return {
            'project_id': project_id,
            'has_data': True,
            'overall_score': latest_report.overall_score,
            'consistency_score': latest_report.consistency_score,
            'agreement_score': latest_report.agreement_score,
            'completeness_score': latest_report.completeness_score,
            'total_issues': latest_report.issue_count,
            'critical_issues': latest_report.critical_issue_count,
            'issue_counts': issue_counts,
            'tasks_analyzed': latest_report.tasks_analyzed,
            'annotations_analyzed': latest_report.annotations_analyzed,
            'annotators_analyzed': latest_report.annotators_analyzed,
            'last_updated': latest_report.created_at.isoformat(),
        }


# Global API instance
data_quality_api = DataQualityAPI()
