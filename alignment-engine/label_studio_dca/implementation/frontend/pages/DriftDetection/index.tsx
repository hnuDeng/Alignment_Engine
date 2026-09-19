/**
 * Drift Detection Page
 */

import React, { useState } from 'react';
import { useDriftReports, useDriftAlerts } from '../../hooks';
import { ScoreCard, LoadingSpinner, EmptyState, StatusBadge } from '../../components';

interface DriftDetectionPageProps {
  projectId: number;
}

type SubTab = 'dashboard' | 'alerts' | 'baselines';

export const DriftDetectionPage: React.FC<DriftDetectionPageProps> = ({
  projectId,
}) => {
  const [activeSubTab, setActiveSubTab] = useState<SubTab>('dashboard');
  const { reports, loading, refresh } = useDriftReports(projectId);
  const { alerts, acknowledgeAlert, resolveAlert } = useDriftAlerts(projectId);

  if (loading) {
    return <LoadingSpinner size="large" />;
  }

  const latestReport = reports[0];
  const activeAlerts = alerts.filter((a) => a.status === 'active');

  return (
    <div className="drift-detection">
      {/* Header */}
      <div className="page-header">
        <h2>Drift Detection</h2>
        <div className="page-header__actions">
          <select className="select">
            <option value="">Select Baseline</option>
          </select>
          <button className="button button--primary" onClick={refresh}>
            Run Detection
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      {latestReport && (
        <div className="score-cards">
          <ScoreCard
            title="Overall Drift"
            value={latestReport.overall_drift_score * 100}
            color={
              latestReport.drift_level === 'critical' || latestReport.drift_level === 'high'
                ? 'red'
                : latestReport.drift_level === 'medium'
                ? 'yellow'
                : 'green'
            }
          />
          <ScoreCard
            title="Feature Drift"
            value={(latestReport.feature_drift_score || 0) * 100}
          />
          <ScoreCard
            title="Label Drift"
            value={(latestReport.label_drift_score || 0) * 100}
          />
          <ScoreCard
            title="Active Alerts"
            value={activeAlerts.length}
            suffix=""
            color={activeAlerts.length > 0 ? 'red' : 'green'}
          />
        </div>
      )}

      {/* Sub Navigation */}
      <div className="sub-nav">
        {(['dashboard', 'alerts', 'baselines'] as SubTab[]).map((tab) => (
          <button
            key={tab}
            className={`sub-nav__item ${
              activeSubTab === tab ? 'sub-nav__item--active' : ''
            }`}
            onClick={() => setActiveSubTab(tab)}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
            {tab === 'alerts' && activeAlerts.length > 0 && (
              <span className="badge badge--error">
                {activeAlerts.length}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="content">
        {activeSubTab === 'dashboard' && (
          <div>
            <h3>Drift Dashboard</h3>
            {reports.length === 0 ? (
              <p>No drift reports available. Run a detection to see results.</p>
            ) : (
              <div>
                <p>Reports: {reports.length}</p>
                <p>Latest drift level: {latestReport?.drift_level}</p>
                <p>Tasks analyzed: {latestReport?.task_count}</p>
              </div>
            )}
          </div>
        )}

        {activeSubTab === 'alerts' && (
          <AlertsList
            alerts={alerts}
            onAcknowledge={acknowledgeAlert}
            onResolve={resolveAlert}
          />
        )}

        {activeSubTab === 'baselines' && (
          <div>
            <h3>Baseline Manager</h3>
            <p>Manage drift detection baselines here.</p>
          </div>
        )}
      </div>
    </div>
  );
};

// Alerts List Component
const AlertsList: React.FC<{
  alerts: any[];
  onAcknowledge: (id: number) => void;
  onResolve: (id: number) => void;
}> = ({ alerts, onAcknowledge, onResolve }) => {
  if (alerts.length === 0) {
    return <p>No alerts.</p>;
  }

  return (
    <div className="alerts-list">
      <table className="table">
        <thead>
          <tr>
            <th>Status</th>
            <th>Type</th>
            <th>Message</th>
            <th>Created</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {alerts.map((alert) => (
            <tr key={alert.id}>
              <td>
                <StatusBadge
                  status={alert.status}
                  variant={
                    alert.status === 'active' ? 'error' :
                    alert.status === 'acknowledged' ? 'warning' :
                    'success'
                  }
                />
              </td>
              <td>{alert.alert_type}</td>
              <td>{alert.message}</td>
              <td>{new Date(alert.created_at).toLocaleDateString()}</td>
              <td>
                {alert.status === 'active' && (
                  <>
                    <button
                      className="button button--warning"
                      onClick={() => onAcknowledge(alert.id)}
                    >
                      Acknowledge
                    </button>
                    <button
                      className="button button--success"
                      onClick={() => onResolve(alert.id)}
                    >
                      Resolve
                    </button>
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
