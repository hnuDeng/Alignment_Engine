/**
 * Data-Centric AI Main Page
 */

import React, { useState } from 'react';
import { ActiveLearningPage } from './ActiveLearning';
import { DataQualityPage } from './DataQuality';
import { DriftDetectionPage } from './DriftDetection';
import type { TabType } from '../types';

interface DataCentricAIProps {
  projectId: number;
}

export const DataCentricAI: React.FC<DataCentricAIProps> = ({ projectId }) => {
  const [activeTab, setActiveTab] = useState<TabType>('data-quality');

  const tabs = [
    { id: 'data-quality' as TabType, label: 'Data Quality', icon: '🛡️' },
    { id: 'active-learning' as TabType, label: 'Active Learning', icon: '🧠' },
    { id: 'drift-detection' as TabType, label: 'Drift Detection', icon: '📈' },
  ];

  const renderContent = () => {
    switch (activeTab) {
      case 'active-learning':
        return <ActiveLearningPage projectId={projectId} />;
      case 'data-quality':
        return <DataQualityPage projectId={projectId} />;
      case 'drift-detection':
        return <DriftDetectionPage projectId={projectId} />;
      default:
        return null;
    }
  };

  return (
    <div className="data-centric-ai">
      {/* Header */}
      <div className="navigation-header">
        <h1>Data-Centric AI</h1>
        <p>Intelligent data management workflow</p>
      </div>

      {/* Navigation */}
      <div className="navigation">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={`navigation__tab ${
              activeTab === tab.id ? 'navigation__tab--active' : ''
            }`}
            onClick={() => setActiveTab(tab.id)}
          >
            <span>{tab.icon}</span>
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Content */}
      {renderContent()}
    </div>
  );
};

export default DataCentricAI;
