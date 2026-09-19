/**
 * Status Badge Component
 */

import React from 'react';

interface StatusBadgeProps {
  status: string;
  variant?: 'default' | 'success' | 'warning' | 'error';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  variant = 'default',
}) => {
  return (
    <span className={`badge badge--${variant}`}>
      {status}
    </span>
  );
};
