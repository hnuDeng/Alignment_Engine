/**
 * Data-Centric AI - API Service
 */

import type {
  ActiveLearningConfig,
  ActiveLearningRound,
  SelectionResult,
  QualityReport,
  QualityIssue,
  QualityDashboardData,
  AnnotatorProfile,
  LabelStats,
  DriftBaseline,
  DriftReport,
  DriftAlert,
  PaginatedResponse,
} from '../types';

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

// ==================== Active Learning API ====================

export const activeLearningApi = {
  getConfigs: (projectId: number) =>
    apiCall<PaginatedResponse<ActiveLearningConfig>>(
      `/active-learning/configs/?project=${projectId}`
    ),

  getConfig: (id: number) =>
    apiCall<ActiveLearningConfig>(`/active-learning/configs/${id}/`),

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
    apiCall<{ id: number; is_enabled: boolean; message: string }>(
      `/active-learning/configs/${id}/toggle/`,
      { method: 'POST' }
    ),

  selectTasks: (configId: number, batchSize?: number) =>
    apiCall<SelectionResult>(
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

// ==================== Data Quality API ====================

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
    apiCall<PaginatedResponse<AnnotatorProfile>>(
      `/data-quality/projects/${projectId}/annotators/`
    ),

  getLabelStats: (projectId: number) =>
    apiCall<PaginatedResponse<LabelStats>>(
      `/data-quality/projects/${projectId}/labels/`
    ),
};

// ==================== Drift Detection API ====================

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
