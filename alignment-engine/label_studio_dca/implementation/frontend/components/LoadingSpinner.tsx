/**
 * Loading Spinner Component
 */

import React from 'react';

interface LoadingSpinnerProps {
  size?: 'small' | 'medium' | 'large';
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  size = 'medium',
}) => {
  return (
    <div className={`spinner spinner--${size}`}>
      <div className="spinner__circle" />
    </div>
  );
};
