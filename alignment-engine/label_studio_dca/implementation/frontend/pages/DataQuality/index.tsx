/**
 * Data Quality Page
 */

import React, { useState } from 'react';
import { useQualityDashboard, useQualityIssues } from '../../hooks';
import { dataQualityApi } from '../../api';
import { ScoreCard, LoadingSpinner, EmptyState, StatusBadge } from '../../components';

interface DataQualityPageProps {
  projectId: number;
}

type SubTab = 'dashboard' | 'issues' | 'annotators' | 'labels';

export const DataQualityPage: React.FC<DataQualityPageProps> = ({
  projectId,
}) => {
  const [activeSubTab, setActiveSubTab] = useState<SubTab>('dashboard');
  const [assessing, setAssessing] = useState(false);
  const { data, loading, error, refresh } = useQualityDashboard(projectId);

  const handleRunAssessment = async () => {
    try {
      setAssessing(true);
      await dataQualityApi.runAssessment(projectId);
      refresh();
    } catch (err) {
      console.error('Assessment failed:', err);
    } finally {
      setAssessing(false);
    }
  };

  if (loading) {
    return <LoadingSpinner size="large" />;
  }

  if (error) {
    return (
      <EmptyState
        title="Error Loading Data"
        description={error}
        action={{ label: 'Retry', onClick: refresh }}
      />
    );
  }

  if (!data || !data.has_data) {
    return (
      <EmptyState
        title="No Quality Data"
        description="Run a quality assessment to see data quality metrics."
        action={{
          label: assessing ? 'Running...' : 'Run Assessment',
          onClick: handleRunAssessment,
        }}
      />
    );
  }

  return (
    <div className="data-quality">
      {/* Header */}
      <div className="page-header">
        <h2>Data Quality Assessment</h2>
        <button
          className="button button--primary"
          onClick={handleRunAssessment}
          disabled={assessing}
        >
          {assessing ? 'Running Assessment...' : 'Run Assessment'}
        </button>
      </div>

      {/* Score Cards */}
      <div className="score-cards">
        <ScoreCard
          title="Overall Quality"
          value={(data.overall_score || 0) * 100}
          color="blue"
        />
        <ScoreCard
          title="Consistency"
          value={(data.consistency_score || 0) * 100}
          color="green"
        />
        <ScoreCard
          title="Agreement"
          value={(data.agreement_score || 0) * 100}
          color="yellow"
        />
        <ScoreCard
          title="Completeness"
          value={(data.completeness_score || 0) * 100}
          color="blue"
        />
      </div>

      {/* Issue Summary */}
      {data.issue_counts && (
        <div className="card">
          <div className="card__header">
            <h3 className="card__title">Issues Summary</h3>
          </div>
          <div className="issue-counts">
            {Object.entries(data.issue_counts).map(([severity, count]) => (
              <StatusBadge
                key={severity}
                status={`${severity}: ${count}`}
                variant={
                  severity === 'critical' ? 'error' :
                  severity === 'high' ? 'warning' :
                  'default'
                }
              />
            ))}
          </div>
        </div>
      )}

      {/* Sub Navigation */}
      <div className="sub-nav">
        {(['dashboard', 'issues', 'annotators', 'labels'] as SubTab[]).map(
          (tab) => (
            <button
              key={tab}
              className={`sub-nav__item ${
                activeSubTab === tab ? 'sub-nav__item--active' : ''
              }`}
              onClick={() => setActiveSubTab(tab)}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          )
        )}
      </div>

      {/* Content */}
      <div className="content">
        {activeSubTab === 'dashboard' && (
          <div>
            <h3>Quality Dashboard</h3>
            <p>Tasks analyzed: {data.tasks_analyzed}</p>
            <p>Annotations analyzed: {data.annotations_analyzed}</p>
            <p>Annotators analyzed: {data.annotators_analyzed}</p>
            <p>Last updated: {data.last_updated}</p>
          </div>
        )}
        
        {activeSubTab === 'issues' && (
          <IssuesList projectId={projectId} />
        )}
        
        {activeSubTab === 'annotators' && (
          <div>
            <h3>Annotator Profiles</h3>
            <p>Annotator quality profiles will be displayed here.</p>
          </div>
        )}
        
        {activeSubTab === 'labels' && (
          <div>
            <h3>Label Statistics</h3>
            <p>Label quality statistics will be displayed here.</p>
          </div>
        )}
      </div>
    </div>
  );
};

// Issues List Component
const IssuesList: React.FC<{ projectId: number }> = ({ projectId }) => {
  const { issues, loading, resolveIssue } = useQualityIssues(projectId);

  if (loading) {
    return <LoadingSpinner />;
  }

  if (issues.length === 0) {
    return <p>No issues found.</p>;
  }

  return (
    <div className="issues-list">
      <table className="table">
        <thead>
          <tr>
            <th>Severity</th>
            <th>Type</th>
            <th>Title</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {issues.map((issue) => (
            <tr key={issue.id}>
              <td>
                <StatusBadge
                  status={issue.severity}
                  variant={
                    issue.severity === 'critical' ? 'error' :
                    issue.severity === 'high' ? 'warning' :
                    'default'
                  }
                />
              </td>
              <td>{issue.issue_type}</td>
              <td>{issue.title}</td>
              <td>
                <StatusBadge
                  status={issue.is_resolved ? 'Resolved' : 'Open'}
                  variant={issue.is_resolved ? 'success' : 'warning'}
                />
              </td>
              <td>
                {!issue.is_resolved && (
                  <button
                    className="button button--success"
                    onClick={() => resolveIssue(issue.id)}
                  >
                    Resolve
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
