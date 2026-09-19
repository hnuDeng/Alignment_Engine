/**
 * Empty State Component
 */

import React from 'react';

interface EmptyStateProps {
  title: string;
  description: string;
  action?: {
    label: string;
    onClick: () => void;
  };
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  action,
}) => {
  return (
    <div className="empty-state">
      <div className="empty-state__icon">📊</div>
      <h3 className="empty-state__title">{title}</h3>
      <p className="empty-state__description">{description}</p>
      {action && (
        <button
          className="button button--primary"
          onClick={action.onClick}
        >
          {action.label}
        </button>
      )}
    </div>
  );
};
