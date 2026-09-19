/**
 * Active Learning Page
 */

import React, { useState, useCallback } from 'react';
import { useActiveLearning } from '../../hooks';
import { ScoreCard, LoadingSpinner, EmptyState } from '../../components';
import type { SelectionResult } from '../../types';

interface ActiveLearningPageProps {
  projectId: number;
}

export const ActiveLearningPage: React.FC<ActiveLearningPageProps> = ({
  projectId,
}) => {
  const {
    config,
    loading,
    error,
    toggleEnabled,
    selectTasks,
    refresh,
  } = useActiveLearning(projectId);

  const [selectionResult, setSelectionResult] = useState<SelectionResult | null>(null);
  const [selecting, setSelecting] = useState(false);

  const handleSelectTasks = useCallback(
    async (batchSize?: number) => {
      try {
        setSelecting(true);
        const result = await selectTasks(batchSize);
        if (result) {
          setSelectionResult(result);
        }
      } catch (err) {
        console.error('Selection failed:', err);
      } finally {
        setSelecting(false);
      }
    },
    [selectTasks]
  );

  if (loading) {
    return <LoadingSpinner size="large" />;
  }

  if (error) {
    return (
      <EmptyState
        title="Error Loading Configuration"
        description={error}
        action={{ label: 'Retry', onClick: refresh }}
      />
    );
  }

  return (
    <div className="active-learning">
      {/* Header */}
      <div className="page-header">
        <h2>Active Learning</h2>
        <div className="page-header__actions">
          {config && (
            <button
              className={`button ${
                config.is_enabled ? 'button--danger' : 'button--success'
              }`}
              onClick={toggleEnabled}
            >
              {config.is_enabled ? 'Disable' : 'Enable'}
            </button>
          )}
        </div>
      </div>

      {/* Status */}
      {config && (
        <div className="score-cards">
          <ScoreCard
            title="Status"
            value={config.is_enabled ? 100 : 0}
            suffix="%"
            color={config.is_enabled ? 'green' : 'red'}
          />
          <ScoreCard
            title="Strategy"
            value={0}
            suffix={config.strategy}
            color="blue"
          />
          <ScoreCard
            title="Batch Size"
            value={config.batch_size}
            suffix=""
            color="blue"
          />
        </div>
      )}

      {/* Task Selection */}
      {config?.is_enabled && (
        <div className="card">
          <div className="card__header">
            <h3 className="card__title">Select Tasks</h3>
            <button
              className="button button--primary"
              onClick={() => handleSelectTasks()}
              disabled={selecting}
            >
              {selecting ? 'Selecting...' : 'Select Next Batch'}
            </button>
          </div>

          {selectionResult && (
            <div className="selection-result">
              <h4>Selection Result</h4>
              <div className="score-cards">
                <ScoreCard
                  title="Selected Tasks"
                  value={selectionResult.selected_task_ids.length}
                  suffix=""
                  color="green"
                />
                <ScoreCard
                  title="Avg Uncertainty"
                  value={selectionResult.avg_uncertainty * 100}
                  color="blue"
                />
                <ScoreCard
                  title="Strategy Used"
                  value={0}
                  suffix={selectionResult.strategy_used}
                  color="blue"
                />
              </div>
              
              <div className="task-list">
                <h5>Selected Task IDs:</h5>
                <div className="task-ids">
                  {selectionResult.selected_task_ids.map((taskId) => (
                    <span key={taskId} className="task-id">
                      #{taskId}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Not configured message */}
      {!config && (
        <EmptyState
          title="Active Learning Not Configured"
          description="Configure active learning to start intelligent task selection."
          action={{
            label: 'Configure',
            onClick: () => {
              // Navigate to configuration
            },
          }}
        />
      )}
    </div>
  );
};
