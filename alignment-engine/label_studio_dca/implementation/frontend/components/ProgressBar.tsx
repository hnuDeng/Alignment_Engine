/**
 * Progress Bar Component
 */

import React from 'react';

interface ProgressBarProps {
  value: number;
  max?: number;
  label?: string;
  showPercentage?: boolean;
  color?: 'green' | 'blue' | 'yellow' | 'red';
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  value,
  max = 100,
  label,
  showPercentage = true,
  color = 'blue',
}) => {
  const percentage = Math.min((value / max) * 100, 100);

  return (
    <div className="progress">
      {label && <div className="progress__label">{label}</div>}
      <div className="progress__bar">
        <div
          className={`progress__fill progress__fill--${color}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      {showPercentage && (
        <div className="progress__percentage">{percentage.toFixed(1)}%</div>
      )}
    </div>
  );
};
