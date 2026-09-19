/**
 * Score Card Component
 */

import React from 'react';

interface ScoreCardProps {
  title: string;
  value: number;
  suffix?: string;
  trend?: 'up' | 'down' | 'stable';
  trendValue?: number;
  color?: 'green' | 'red' | 'yellow' | 'blue';
}

export const ScoreCard: React.FC<ScoreCardProps> = ({
  title,
  value,
  suffix = '%',
  trend,
  trendValue,
  color = 'blue',
}) => {
  const getColorClass = () => {
    if (value >= 80) return 'green';
    if (value >= 60) return 'yellow';
    return 'red';
  };

  const colorClass = color === 'blue' ? getColorClass() : color;

  return (
    <div className={`score-card score-card--${colorClass}`}>
      <div className="score-card__header">
        <span className="score-card__title">{title}</span>
        {trend && (
          <span className={`score-card__trend score-card__trend--${trend}`}>
            {trend === 'up' ? '↑' : trend === 'down' ? '↓' : '→'}
            {trendValue && ` ${trendValue}%`}
          </span>
        )}
      </div>
      <div className="score-card__value">
        {typeof value === 'number' ? value.toFixed(1) : value}
        <span className="score-card__suffix">{suffix}</span>
      </div>
    </div>
  );
};
