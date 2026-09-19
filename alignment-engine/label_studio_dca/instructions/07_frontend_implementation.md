# 指令 07：前端基础架构与页面实现

## 目标

创建数据为中心AI工作流的前端界面，包括主动学习、数据质量和漂移检测的可视化面板。

## 需要创建的文件

```
web/apps/labelstudio/src/pages/DataCentricAI/
├── index.tsx                          # 主页面
├── types.ts                           # TypeScript类型定义
├── api.ts                             # API服务
├── hooks.ts                           # 自定义Hooks
├── components/
│   ├── Layout.tsx                     # 布局组件
│   ├── Navigation.tsx                 # 导航组件
│   ├── ScoreCard.tsx                  # 分数卡片
│   ├── ChartComponents.tsx           # 图表组件
│   └── CommonUI.tsx                   # 通用UI组件
├── ActiveLearning/
│   ├── index.tsx                      # 主动学习主页
│   ├── StrategyConfig.tsx            # 策略配置
│   ├── TaskSelector.tsx              # 任务选择
│   ├── RoundHistory.tsx              # 轮次历史
│   └── FeedbackPanel.tsx             # 反馈面板
├── DataQuality/
│   ├── index.tsx                      # 数据质量主页
│   ├── QualityDashboard.tsx          # 质量仪表盘
│   ├── IssueList.tsx                 # 问题列表
│   ├── AnnotatorProfile.tsx          # 标注者档案
│   └── LabelStats.tsx                # 标签统计
└── DriftDetection/
    ├── index.tsx                      # 漂移检测主页
    ├── DriftDashboard.tsx            # 漂移仪表盘
    ├── AlertCenter.tsx               # 告警中心
    └── BaselineManager.tsx           # 基线管理
```

## 详细实现

### 7.1 类型定义 (`types.ts`)

```typescript
// web/apps/labelstudio/src/pages/DataCentricAI/types.ts

// Active Learning Types
export interface ActiveLearningConfig {
  id: number;
  project: number;
  project_title: string;
  ml_backend: number | null;
  ml_backend_title: string | null;
  strategy: StrategyType;
  uncertainty_method: UncertaintyMethod;
  batch_size: number;
  is_enabled: boolean;
  auto_select: boolean;
  auto_train: boolean;
  round_count: number;
  created_at: string;
  updated_at: string;
}

export type StrategyType = 
  | 'uncertainty' 
  | 'diversity' 
  | 'committee' 
  | 'expected_gradient' 
  | 'hybrid' 
  | 'random';

export type UncertaintyMethod = 
  | 'least_confidence' 
  | 'margin_sampling' 
  | 'entropy';

export interface ActiveLearningRound {
  id: number;
  config: number;
  round_number: number;
  task_count: number;
  strategy_used: string;
  selection_scores: Record<number, number>;
  avg_uncertainty: number;
  diversity_score: number;
  is_completed: boolean;
  completed_at: string | null;
  created_at: string;
}

export interface TaskSelectionResult {
  round_id: number;
  round_number: number;
  task_ids: number[];
  task_scores: Record<number, number>;
  strategy_used: string;
  avg_uncertainty: number;
  diversity_score: number;
  selection_summary: {
    total_candidates: number;
    selected: number;
    avg_score: number;
  };
}

// Data Quality Types
export interface QualityReport {
  id: number;
  project: number;
  project_title: string;
  report_type: ReportType;
  overall_score: number;
  consistency_score: number | null;
  agreement_score: number | null;
  completeness_score: number | null;
  statistics: Record<string, any>;
  issue_count: number;
  critical_issue_count: number;
  tasks_analyzed: number;
  annotations_analyzed: number;
  annotators_analyzed: number;
  created_at: string;
  created_by: number | null;
}

export type ReportType = 'project' | 'annotator' | 'task' | 'label';

export interface QualityIssue {
  id: number;
  report: number;
  issue_type: IssueType;
  severity: SeverityLevel;
  task: number | null;
  task_id: number | null;
  annotation: number | null;
  annotator: number | null;
  annotator_username: string | null;
  title: string;
  description: string;
  details: Record<string, any>;
  is_resolved: boolean;
  resolved_at: string | null;
  resolved_by: number | null;
  resolution_notes: string;
  created_at: string;
}

export type IssueType = 
  | 'inconsistency' 
  | 'outlier' 
  | 'bias' 
  | 'missing' 
  | 'conflict' 
  | 'low_agreement' 
  | 'speed_anomaly';

export type SeverityLevel = 'low' | 'medium' | 'high' | 'critical';

export interface AnnotatorQualityProfile {
  id: number;
  user: number;
  username: string;
  project: number;
  project_title: string;
  total_annotations: number;
  agreement_rate: number;
  avg_annotation_time: number;
  quality_score: number;
  consistency_score: number;
  issue_count: number;
  critical_issue_count: number;
  statistics: Record<string, any>;
  first_annotation_at: string | null;
  last_annotation_at: string | null;
}

export interface LabelQualityStats {
  id: number;
  project: number;
  label_name: string;
  label_type: string;
  usage_count: number;
  unique_annotators: number;
  agreement_rate: number;
  consistency_score: number;
  usage_percentage: number;
}

export interface QualityDashboardData {
  project_id: number;
  project_title: string;
  overall_score: number;
  total_issues: number;
  critical_issues: number;
  resolved_issues: number;
  consistency_score: number;
  agreement_score: number;
  completeness_score: number;
  score_trend: number[];
  top_issues: QualityIssue[];
  annotator_stats: AnnotatorQualityProfile[];
  label_stats: LabelQualityStats[];
}

// Drift Detection Types
export interface DriftBaseline {
  id: number;
  project: number;
  name: string;
  description: string;
  feature_statistics: Record<string, any>;
  label_distribution: Record<string, any>;
  sample_count: number;
  sample_start_date: string | null;
  sample_end_date: string | null;
  is_active: boolean;
  created_at: string;
  created_by: number | null;
}

export interface DriftReport {
  id: number;
  project: number;
  baseline: number;
  drift_level: DriftLevel;
  feature_drift_score: number | null;
  label_drift_score: number | null;
  overall_drift_score: number;
  details: Record<string, any>;
  window_start: string;
  window_end: string;
  task_count: number;
  created_at: string;
}

export type DriftLevel = 'none' | 'low' | 'medium' | 'high' | 'critical';

export interface DriftAlert {
  id: number;
  project: number;
  report: number | null;
  alert_type: string;
  status: AlertStatus;
  message: string;
  details: Record<string, any>;
  notified_users: number[];
  created_at: string;
  acknowledged_at: string | null;
  acknowledged_by: number | null;
  resolved_at: string | null;
}

export type AlertStatus = 'active' | 'acknowledged' | 'resolved';

// Common Types
export interface ApiResponse<T> {
  data: T;
  message?: string;
  error?: string;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
```

### 7.2 API服务 (`api.ts`)

```typescript
// web/apps/labelstudio/src/pages/DataCentricAI/api.ts

import type {
  ActiveLearningConfig,
  ActiveLearningRound,
  TaskSelectionResult,
  QualityReport,
  QualityIssue,
  QualityDashboardData,
  AnnotatorQualityProfile,
  LabelQualityStats,
  DriftBaseline,
  DriftReport,
  DriftAlert,
  PaginatedResponse,
} from './types';

const API_BASE = '/api';

// Helper function for API calls
async function apiCall<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || error.message || 'API request failed');
  }

  return response.json();
}

// Active Learning API
export const activeLearningApi = {
  getConfigs: (projectId: number) =>
    apiCall<PaginatedResponse<ActiveLearningConfig>>(
      `/active-learning/configs/?project=${projectId}`
    ),

  getConfig: (id: number) =>
    apiCall<ActiveLearningConfig>(`/active-learning/configs/${id}/``),

  createConfig: (data: Partial<ActiveLearningConfig>) =>
    apiCall<ActiveLearningConfig>('/active-learning/configs/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateConfig: (id: number, data: Partial<ActiveLearningConfig>) =>
    apiCall<ActiveLearningConfig>(`/active-learning/configs/${id}/`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  toggleConfig: (id: number) =>
    apiCall<{ is_enabled: boolean }>(
      `/active-learning/configs/${id}/toggle/`,
      { method: 'POST' }
    ),

  selectTasks: (configId: number, batchSize?: number) =>
    apiCall<TaskSelectionResult>(
      `/active-learning/configs/${configId}/select/`,
      {
        method: 'POST',
        body: JSON.stringify({ batch_size: batchSize }),
      }
    ),

  getRounds: (configId: number) =>
    apiCall<PaginatedResponse<ActiveLearningRound>>(
      `/active-learning/configs/${configId}/rounds/`
    ),

  getStatus: (projectId: number) =>
    apiCall<any>(`/active-learning/projects/${projectId}/status/`),
};

// Data Quality API
export const dataQualityApi = {
  getReports: (projectId: number, reportType?: string) => {
    const params = new URLSearchParams({ project: String(projectId) });
    if (reportType) params.append('report_type', reportType);
    return apiCall<PaginatedResponse<QualityReport>>(
      `/data-quality/reports/?${params}`
    );
  },

  getReport: (id: number) =>
    apiCall<QualityReport>(`/data-quality/reports/${id}/`),

  runAssessment: (projectId: number, assessors?: string[]) =>
    apiCall<QualityReport>(
      `/data-quality/projects/${projectId}/assess/`,
      {
        method: 'POST',
        body: JSON.stringify({ assessors }),
      }
    ),

  getIssues: (projectId: number, filters?: Record<string, any>) => {
    const params = new URLSearchParams({ project: String(projectId) });
    if (filters) {
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          params.append(key, String(value));
        }
      });
    }
    return apiCall<PaginatedResponse<QualityIssue>>(
      `/data-quality/issues/?${params}`
    );
  },

  resolveIssue: (issueId: number, notes?: string) =>
    apiCall<QualityIssue>(`/data-quality/issues/${issueId}/resolve/`, {
      method: 'POST',
      body: JSON.stringify({ notes }),
    }),

  getDashboard: (projectId: number) =>
    apiCall<QualityDashboardData>(
      `/data-quality/projects/${projectId}/dashboard/`
    ),

  getAnnotatorProfiles: (projectId: number) =>
    apiCall<PaginatedResponse<AnnotatorQualityProfile>>(
      `/data-quality/projects/${projectId}/annotators/`
    ),

  getLabelStats: (projectId: number) =>
    apiCall<PaginatedResponse<LabelQualityStats>>(
      `/data-quality/projects/${projectId}/labels/`
    ),

  getSummary: (projectId: number) =>
    apiCall<any>(`/data-quality/projects/${projectId}/summary/`),
};

// Drift Detection API
export const driftDetectionApi = {
  getBaselines: (projectId: number) =>
    apiCall<PaginatedResponse<DriftBaseline>>(
      `/drift/baselines/?project=${projectId}`
    ),

  createBaseline: (data: Partial<DriftBaseline>) =>
    apiCall<DriftBaseline>('/drift/baselines/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  runDetection: (projectId: number, baselineId: number, windowHours?: number) =>
    apiCall<DriftReport>(`/drift/projects/${projectId}/detect/`, {
      method: 'POST',
      body: JSON.stringify({
        baseline_id: baselineId,
        window_hours: windowHours,
      }),
    }),

  getReports: (projectId: number) =>
    apiCall<PaginatedResponse<DriftReport>>(
      `/drift/projects/${projectId}/reports/`
    ),

  getAlerts: (projectId: number) =>
    apiCall<PaginatedResponse<DriftAlert>>(
      `/drift/projects/${projectId}/alerts/`
    ),

  acknowledgeAlert: (alertId: number) =>
    apiCall<DriftAlert>(`/drift/alerts/${alertId}/acknowledge/`, {
      method: 'POST',
    }),

  resolveAlert: (alertId: number) =>
    apiCall<DriftAlert>(`/drift/alerts/${alertId}/resolve/`, {
      method: 'POST',
    }),
};
```

### 7.3 自定义Hooks (`hooks.ts`)

```typescript
// web/apps/labelstudio/src/pages/DataCentricAI/hooks.ts

import { useState, useEffect, useCallback } from 'react';
import { activeLearningApi, dataQualityApi, driftDetectionApi } from './api';
import type {
  ActiveLearningConfig,
  QualityDashboardData,
  DriftReport,
  DriftAlert,
} from './types';

// Hook for Active Learning
export function useActiveLearning(projectId: number) {
  const [config, setConfig] = useState<ActiveLearningConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchConfig = useCallback(async () => {
    try {
      setLoading(true);
      const response = await activeLearningApi.getConfigs(projectId);
      if (response.results.length > 0) {
        setConfig(response.results[0]);
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  const toggleEnabled = useCallback(async () => {
    if (!config) return;
    const result = await activeLearningApi.toggleConfig(config.id);
    setConfig({ ...config, is_enabled: result.is_enabled });
  }, [config]);

  const selectTasks = useCallback(
    async (batchSize?: number) => {
      if (!config) return null;
      return activeLearningApi.selectTasks(config.id, batchSize);
    },
    [config]
  );

  return {
    config,
    loading,
    error,
    toggleEnabled,
    selectTasks,
    refresh: fetchConfig,
  };
}

// Hook for Quality Dashboard
export function useQualityDashboard(projectId: number) {
  const [data, setData] = useState<QualityDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const result = await dataQualityApi.getDashboard(projectId);
      setData(result);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return {
    data,
    loading,
    error,
    refresh: fetchData,
  };
}

// Hook for Drift Reports
export function useDriftReports(projectId: number) {
  const [reports, setReports] = useState<DriftReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchReports = useCallback(async () => {
    try {
      setLoading(true);
      const response = await driftDetectionApi.getReports(projectId);
      setReports(response.results);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchReports();
  }, [fetchReports]);

  return {
    reports,
    loading,
    error,
    refresh: fetchReports,
  };
}

// Hook for Drift Alerts
export function useDriftAlerts(projectId: number) {
  const [alerts, setAlerts] = useState<DriftAlert[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchAlerts = useCallback(async () => {
    try {
      setLoading(true);
      const response = await driftDetectionApi.getAlerts(projectId);
      setAlerts(response.results);
    } catch (err) {
      console.error('Failed to fetch alerts:', err);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts]);

  const acknowledgeAlert = useCallback(async (alertId: number) => {
    await driftDetectionApi.acknowledgeAlert(alertId);
    setAlerts((prev) =>
      prev.map((a) =>
        a.id === alertId ? { ...a, status: 'acknowledged' as const } : a
      )
    );
  }, []);

  const resolveAlert = useCallback(async (alertId: number) => {
    await driftDetectionApi.resolveAlert(alertId);
    setAlerts((prev) =>
      prev.map((a) =>
        a.id === alertId ? { ...a, status: 'resolved' as const } : a
      )
    );
  }, []);

  return {
    alerts,
    loading,
    acknowledgeAlert,
    resolveAlert,
    refresh: fetchAlerts,
  };
}
```

### 7.4 主页面 (`index.tsx`)

```tsx
// web/apps/labelstudio/src/pages/DataCentricAI/index.tsx

import React, { useState } from 'react';
import { Navigation } from './components/Navigation';
import { ActiveLearningPage } from './ActiveLearning';
import { DataQualityPage } from './DataQuality';
import { DriftDetectionPage } from './DriftDetection';
import './styles.css';

type TabType = 'active-learning' | 'data-quality' | 'drift-detection';

interface DataCentricAIProps {
  projectId: number;
}

export const DataCentricAI: React.FC<DataCentricAIProps> = ({ projectId }) => {
  const [activeTab, setActiveTab] = useState<TabType>('data-quality');

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
      <Navigation activeTab={activeTab} onTabChange={setActiveTab} />
      <main className="data-centric-ai__content">
        {renderContent()}
      </main>
    </div>
  );
};

export default DataCentricAI;
```

### 7.5 导航组件 (`components/Navigation.tsx`)

```tsx
// web/apps/labelstudio/src/pages/DataCentricAI/components/Navigation.tsx

import React from 'react';
import { 
  Brain, 
  Shield, 
  TrendingUp 
} from 'lucide-react';

type TabType = 'active-learning' | 'data-quality' | 'drift-detection';

interface NavigationProps {
  activeTab: TabType;
  onTabChange: (tab: TabType) => void;
}

const tabs = [
  {
    id: 'data-quality' as TabType,
    label: 'Data Quality',
    icon: Shield,
    description: 'Assess annotation quality',
  },
  {
    id: 'active-learning' as TabType,
    label: 'Active Learning',
    icon: Brain,
    description: 'Smart task selection',
  },
  {
    id: 'drift-detection' as TabType,
    label: 'Drift Detection',
    icon: TrendingUp,
    description: 'Monitor data changes',
  },
];

export const Navigation: React.FC<NavigationProps> = ({
  activeTab,
  onTabChange,
}) => {
  return (
    <nav className="dca-navigation">
      <div className="dca-navigation__header">
        <h1 className="dca-navigation__title">Data-Centric AI</h1>
        <p className="dca-navigation__subtitle">
          Intelligent data management workflow
        </p>
      </div>
      
      <div className="dca-navigation__tabs">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          
          return (
            <button
              key={tab.id}
              className={`dca-tab ${isActive ? 'dca-tab--active' : ''}`}
              onClick={() => onTabChange(tab.id)}
            >
              <Icon className="dca-tab__icon" size={20} />
              <div className="dca-tab__content">
                <span className="dca-tab__label">{tab.label}</span>
                <span className="dca-tab__description">{tab.description}</span>
              </div>
            </button>
          );
        })}
      </div>
    </nav>
  );
};
```

### 7.6 通用组件 (`components/CommonUI.tsx`)

```tsx
// web/apps/labelstudio/src/pages/DataCentricAI/components/CommonUI.tsx

import React from 'react';

// Score Card Component
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
    <div className={`dca-score-card dca-score-card--${colorClass}`}>
      <div className="dca-score-card__header">
        <span className="dca-score-card__title">{title}</span>
        {trend && (
          <span className={`dca-score-card__trend dca-score-card__trend--${trend}`}>
            {trend === 'up' ? '↑' : trend === 'down' ? '↓' : '→'}
            {trendValue && ` ${trendValue}%`}
          </span>
        )}
      </div>
      <div className="dca-score-card__value">
        {typeof value === 'number' ? value.toFixed(1) : value}
        <span className="dca-score-card__suffix">{suffix}</span>
      </div>
    </div>
  );
};

// Status Badge Component
interface StatusBadgeProps {
  status: string;
  variant?: 'default' | 'success' | 'warning' | 'error';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  variant = 'default',
}) => {
  return (
    <span className={`dca-badge dca-badge--${variant}`}>
      {status}
    </span>
  );
};

// Loading Spinner
export const LoadingSpinner: React.FC<{ size?: 'small' | 'medium' | 'large' }> = ({
  size = 'medium',
}) => {
  return (
    <div className={`dca-spinner dca-spinner--${size}`}>
      <div className="dca-spinner__circle" />
    </div>
  );
};

// Empty State
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
    <div className="dca-empty-state">
      <div className="dca-empty-state__icon">📊</div>
      <h3 className="dca-empty-state__title">{title}</h3>
      <p className="dca-empty-state__description">{description}</p>
      {action && (
        <button
          className="dca-button dca-button--primary"
          onClick={action.onClick}
        >
          {action.label}
        </button>
      )}
    </div>
  );
};

// Progress Bar
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
    <div className="dca-progress">
      {label && <div className="dca-progress__label">{label}</div>}
      <div className="dca-progress__bar">
        <div
          className={`dca-progress__fill dca-progress__fill--${color}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      {showPercentage && (
        <div className="dca-progress__percentage">{percentage.toFixed(1)}%</div>
      )}
    </div>
  );
};
```

### 7.7 图表组件 (`components/ChartComponents.tsx`)

```tsx
// web/apps/labelstudio/src/pages/DataCentricAI/components/ChartComponents.tsx

import React from 'react';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

// Trend Chart
interface TrendChartProps {
  data: number[];
  labels?: string[];
  title?: string;
  height?: number;
}

export const TrendChart: React.FC<TrendChartProps> = ({
  data,
  labels,
  title,
  height = 300,
}) => {
  const chartData = data.map((value, index) => ({
    name: labels?.[index] || `#${index + 1}`,
    value,
  }));

  return (
    <div className="dca-chart">
      {title && <h3 className="dca-chart__title">{title}</h3>}
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis domain={[0, 100]} />
          <Tooltip />
          <Line
            type="monotone"
            dataKey="value"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={{ fill: '#3b82f6' }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

// Distribution Chart
interface DistributionChartProps {
  data: Record<string, number>;
  title?: string;
  height?: number;
}

const COLORS = [
  '#3b82f6',
  '#10b981',
  '#f59e0b',
  '#ef4444',
  '#8b5cf6',
  '#ec4899',
  '#06b6d4',
  '#84cc16',
];

export const DistributionChart: React.FC<DistributionChartProps> = ({
  data,
  title,
  height = 300,
}) => {
  const chartData = Object.entries(data).map(([name, value]) => ({
    name,
    value,
  }));

  return (
    <div className="dca-chart">
      {title && <h3 className="dca-chart__title">{title}</h3>}
      <ResponsiveContainer width="100%" height={height}>
        <PieChart>
          <Pie
            data={chartData}
            cx="50%"
            cy="50%"
            labelLine={false}
            label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
            outerRadius={80}
            fill="#8884d8"
            dataKey="value"
          >
            {chartData.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={COLORS[index % COLORS.length]}
              />
            ))}
          </Pie>
          <Tooltip />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
};

// Comparison Bar Chart
interface ComparisonChartProps {
  data: Array<{
    name: string;
    baseline: number;
    current: number;
  }>;
  title?: string;
  height?: number;
}

export const ComparisonChart: React.FC<ComparisonChartProps> = ({
  data,
  title,
  height = 300,
}) => {
  return (
    <div className="dca-chart">
      {title && <h3 className="dca-chart__title">{title}</h3>}
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Bar dataKey="baseline" fill="#94a3b8" name="Baseline" />
          <Bar dataKey="current" fill="#3b82f6" name="Current" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};
```

### 7.8 数据质量页面 (`DataQuality/index.tsx`)

```tsx
// web/apps/labelstudio/src/pages/DataCentricAI/DataQuality/index.tsx

import React, { useState } from 'react';
import { useQualityDashboard } from '../hooks';
import { dataQualityApi } from '../api';
import { ScoreCard, LoadingSpinner, EmptyState } from '../components/CommonUI';
import { TrendChart, DistributionChart } from '../components/ChartComponents';
import { QualityDashboard } from './QualityDashboard';
import { IssueList } from './IssueList';
import { AnnotatorProfile } from './AnnotatorProfile';
import { LabelStats } from './LabelStats';

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

  if (!data || !data.overall_score) {
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
    <div className="dca-data-quality">
      {/* Header with action buttons */}
      <div className="dca-page-header">
        <h2>Data Quality Assessment</h2>
        <button
          className="dca-button dca-button--primary"
          onClick={handleRunAssessment}
          disabled={assessing}
        >
          {assessing ? 'Running Assessment...' : 'Run Assessment'}
        </button>
      </div>

      {/* Score cards */}
      <div className="dca-score-cards">
        <ScoreCard
          title="Overall Quality"
          value={data.overall_score * 100}
          color="blue"
        />
        <ScoreCard
          title="Consistency"
          value={data.consistency_score * 100}
          color="green"
        />
        <ScoreCard
          title="Agreement"
          value={data.agreement_score * 100}
          color="yellow"
        />
        <ScoreCard
          title="Completeness"
          value={data.completeness_score * 100}
          color="blue"
        />
      </div>

      {/* Sub-navigation */}
      <div className="dca-sub-nav">
        {(['dashboard', 'issues', 'annotators', 'labels'] as SubTab[]).map(
          (tab) => (
            <button
              key={tab}
              className={`dca-sub-nav__item ${
                activeSubTab === tab ? 'dca-sub-nav__item--active' : ''
              }`}
              onClick={() => setActiveSubTab(tab)}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          )
        )}
      </div>

      {/* Content */}
      <div className="dca-content">
        {activeSubTab === 'dashboard' && (
          <QualityDashboard data={data} />
        )}
        {activeSubTab === 'issues' && (
          <IssueList projectId={projectId} />
        )}
        {activeSubTab === 'annotators' && (
          <AnnotatorProfile projectId={projectId} />
        )}
        {activeSubTab === 'labels' && (
          <LabelStats projectId={projectId} />
        )}
      </div>
    </div>
  );
};
```

### 7.9 主动学习页面 (`ActiveLearning/index.tsx`)

```tsx
// web/apps/labelstudio/src/pages/DataCentricAI/ActiveLearning/index.tsx

import React, { useState, useCallback } from 'react';
import { useActiveLearning } from '../hooks';
import { activeLearningApi } from '../api';
import { LoadingSpinner, EmptyState, ScoreCard } from '../components/CommonUI';
import { StrategyConfig } from './StrategyConfig';
import { TaskSelector } from './TaskSelector';
import { RoundHistory } from './RoundHistory';

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

  const [selectionResult, setSelectionResult] = useState<any>(null);
  const [selecting, setSelecting] = useState(false);

  const handleSelectTasks = useCallback(
    async (batchSize?: number) => {
      try {
        setSelecting(true);
        const result = await selectTasks(batchSize);
        setSelectionResult(result);
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
    <div className="dca-active-learning">
      <div className="dca-page-header">
        <h2>Active Learning</h2>
        <div className="dca-page-header__actions">
          {config && (
            <button
              className={`dca-button ${
                config.is_enabled
                  ? 'dca-button--danger'
                  : 'dca-button--success'
              }`}
              onClick={toggleEnabled}
            >
              {config.is_enabled ? 'Disable' : 'Enable'}
            </button>
          )}
        </div>
      </div>

      {/* Configuration */}
      <StrategyConfig
        config={config}
        projectId={projectId}
        onUpdate={refresh}
      />

      {/* Task Selection */}
      {config?.is_enabled && (
        <TaskSelector
          config={config}
          onSelect={handleSelectTasks}
          selecting={selecting}
          result={selectionResult}
        />
      )}

      {/* Round History */}
      {config && (
        <RoundHistory configId={config.id} />
      )}
    </div>
  );
};
```

### 7.10 漂移检测页面 (`DriftDetection/index.tsx`)

```tsx
// web/apps/labelstudio/src/pages/DataCentricAI/DriftDetection/index.tsx

import React, { useState } from 'react';
import { useDriftReports, useDriftAlerts } from '../hooks';
import { driftDetectionApi } from '../api';
import { LoadingSpinner, EmptyState, ScoreCard } from '../components/CommonUI';
import { TrendChart } from '../components/ChartComponents';
import { DriftDashboard } from './DriftDashboard';
import { AlertCenter } from './AlertCenter';
import { BaselineManager } from './BaselineManager';

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

  const [detecting, setDetecting] = useState(false);
  const [selectedBaseline, setSelectedBaseline] = useState<number | null>(null);

  const handleRunDetection = async () => {
    if (!selectedBaseline) return;

    try {
      setDetecting(true);
      await driftDetectionApi.runDetection(projectId, selectedBaseline);
      refresh();
    } catch (err) {
      console.error('Detection failed:', err);
    } finally {
      setDetecting(false);
    }
  };

  if (loading) {
    return <LoadingSpinner size="large" />;
  }

  const latestReport = reports[0];
  const activeAlerts = alerts.filter((a) => a.status === 'active');

  return (
    <div className="dca-drift-detection">
      <div className="dca-page-header">
        <h2>Drift Detection</h2>
        <div className="dca-page-header__actions">
          <select
            className="dca-select"
            value={selectedBaseline || ''}
            onChange={(e) => setSelectedBaseline(Number(e.target.value))}
          >
            <option value="">Select Baseline</option>
            {/* Baselines would be loaded here */}
          </select>
          <button
            className="dca-button dca-button--primary"
            onClick={handleRunDetection}
            disabled={detecting || !selectedBaseline}
          >
            {detecting ? 'Detecting...' : 'Run Detection'}
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      {latestReport && (
        <div className="dca-score-cards">
          <ScoreCard
            title="Overall Drift"
            value={latestReport.overall_drift_score * 100}
            color={
              latestReport.drift_level === 'critical'
                ? 'red'
                : latestReport.drift_level === 'high'
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

      {/* Sub-navigation */}
      <div className="dca-sub-nav">
        {(['dashboard', 'alerts', 'baselines'] as SubTab[]).map((tab) => (
          <button
            key={tab}
            className={`dca-sub-nav__item ${
              activeSubTab === tab ? 'dca-sub-nav__item--active' : ''
            }`}
            onClick={() => setActiveSubTab(tab)}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
            {tab === 'alerts' && activeAlerts.length > 0 && (
              <span className="dca-badge dca-badge--error">
                {activeAlerts.length}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="dca-content">
        {activeSubTab === 'dashboard' && (
          <DriftDashboard reports={reports} />
        )}
        {activeSubTab === 'alerts' && (
          <AlertCenter
            alerts={alerts}
            onAcknowledge={acknowledgeAlert}
            onResolve={resolveAlert}
          />
        )}
        {activeSubTab === 'baselines' && (
          <BaselineManager projectId={projectId} />
        )}
      </div>
    </div>
  );
};
```

### 7.11 样式文件 (`styles.css`)

```css
/* web/apps/labelstudio/src/pages/DataCentricAI/styles.css */

/* Base Styles */
.data-centric-ai {
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
}

.dca-navigation {
  margin-bottom: 32px;
}

.dca-navigation__header {
  margin-bottom: 24px;
}

.dca-navigation__title {
  font-size: 28px;
  font-weight: 700;
  color: #1e293b;
  margin: 0 0 4px 0;
}

.dca-navigation__subtitle {
  font-size: 14px;
  color: #64748b;
  margin: 0;
}

/* Navigation Tabs */
.dca-navigation__tabs {
  display: flex;
  gap: 12px;
  border-bottom: 2px solid #e2e8f0;
  padding-bottom: 12px;
}

.dca-tab {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 20px;
  border: none;
  background: transparent;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.dca-tab:hover {
  background: #f1f5f9;
}

.dca-tab--active {
  background: #3b82f6;
  color: white;
}

.dca-tab--active:hover {
  background: #2563eb;
}

.dca-tab__icon {
  flex-shrink: 0;
}

.dca-tab__content {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}

.dca-tab__label {
  font-size: 14px;
  font-weight: 600;
}

.dca-tab__description {
  font-size: 12px;
  opacity: 0.8;
}

/* Score Cards */
.dca-score-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.dca-score-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  border-left: 4px solid #3b82f6;
}

.dca-score-card--green {
  border-left-color: #10b981;
}

.dca-score-card--red {
  border-left-color: #ef4444;
}

.dca-score-card--yellow {
  border-left-color: #f59e0b;
}

.dca-score-card__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.dca-score-card__title {
  font-size: 13px;
  color: #64748b;
  font-weight: 500;
}

.dca-score-card__value {
  font-size: 32px;
  font-weight: 700;
  color: #1e293b;
}

.dca-score-card__suffix {
  font-size: 16px;
  color: #94a3b8;
  margin-left: 4px;
}

/* Buttons */
.dca-button {
  padding: 10px 20px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.dca-button--primary {
  background: #3b82f6;
  color: white;
}

.dca-button--primary:hover {
  background: #2563eb;
}

.dca-button--success {
  background: #10b981;
  color: white;
}

.dca-button--danger {
  background: #ef4444;
  color: white;
}

.dca-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Sub Navigation */
.dca-sub-nav {
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
  border-bottom: 1px solid #e2e8f0;
  padding-bottom: 12px;
}

.dca-sub-nav__item {
  padding: 8px 16px;
  border: none;
  background: transparent;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  color: #64748b;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  gap: 8px;
}

.dca-sub-nav__item:hover {
  background: #f1f5f9;
  color: #1e293b;
}

.dca-sub-nav__item--active {
  background: #3b82f6;
  color: white;
}

/* Loading Spinner */
.dca-spinner {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 48px;
}

.dca-spinner__circle {
  width: 40px;
  height: 40px;
  border: 3px solid #e2e8f0;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* Empty State */
.dca-empty-state {
  text-align: center;
  padding: 48px;
}

.dca-empty-state__icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.dca-empty-state__title {
  font-size: 18px;
  font-weight: 600;
  color: #1e293b;
  margin: 0 0 8px 0;
}

.dca-empty-state__description {
  font-size: 14px;
  color: #64748b;
  margin: 0 0 24px 0;
}

/* Badge */
.dca-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.dca-badge--default {
  background: #e2e8f0;
  color: #475569;
}

.dca-badge--success {
  background: #d1fae5;
  color: #065f46;
}

.dca-badge--warning {
  background: #fef3c7;
  color: #92400e;
}

.dca-badge--error {
  background: #fee2e2;
  color: #991b1b;
}

/* Progress Bar */
.dca-progress {
  display: flex;
  align-items: center;
  gap: 12px;
}

.dca-progress__bar {
  flex: 1;
  height: 8px;
  background: #e2e8f0;
  border-radius: 4px;
  overflow: hidden;
}

.dca-progress__fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
}

.dca-progress__fill--blue {
  background: #3b82f6;
}

.dca-progress__fill--green {
  background: #10b981;
}

.dca-progress__fill--yellow {
  background: #f59e0b;
}

.dca-progress__fill--red {
  background: #ef4444;
}

/* Chart */
.dca-chart {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.dca-chart__title {
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
  margin: 0 0 16px 0;
}

/* Select */
.dca-select {
  padding: 10px 16px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 14px;
  background: white;
  cursor: pointer;
}

.dca-select:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

/* Page Header */
.dca-page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.dca-page-header h2 {
  font-size: 24px;
  font-weight: 700;
  color: #1e293b;
  margin: 0;
}

.dca-page-header__actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

/* Content Area */
.dca-content {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}
```

## 验证检查点

- [ ] TypeScript类型定义完整
- [ ] API服务正常工作
- [ ] 自定义Hooks功能正常
- [ ] 主页面导航正常
- [ ] 数据质量页面显示正常
- [ ] 主动学习页面显示正常
- [ ] 漂移检测页面显示正常
- [ ] 图表组件渲染正常
- [ ] 样式应用正确

## 下一步

执行 `08_api_integration.md` 进行API集成和路由配置。
