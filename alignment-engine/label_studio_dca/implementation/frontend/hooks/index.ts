/**
 * Data-Centric AI - Custom React Hooks
 */

import { useState, useEffect, useCallback } from 'react';
import { activeLearningApi, dataQualityApi, driftDetectionApi } from '../api';
import type {
  ActiveLearningConfig,
  QualityDashboardData,
  DriftReport,
  DriftAlert,
} from '../types';

// ==================== Active Learning Hooks ====================

export function useActiveLearning(projectId: number) {
  const [config, setConfig] = useState<ActiveLearningConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchConfig = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
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
    try {
      const result = await activeLearningApi.toggleConfig(config.id);
      setConfig({ ...config, is_enabled: result.is_enabled });
    } catch (err: any) {
      setError(err.message);
    }
  }, [config]);

  const selectTasks = useCallback(
    async (batchSize?: number) => {
      if (!config) return null;
      try {
        return await activeLearningApi.selectTasks(config.id, batchSize);
      } catch (err: any) {
        setError(err.message);
        return null;
      }
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

// ==================== Data Quality Hooks ====================

export function useQualityDashboard(projectId: number) {
  const [data, setData] = useState<QualityDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
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

export function useQualityIssues(projectId: number, filters?: Record<string, any>) {
  const [issues, setIssues] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchIssues = useCallback(async () => {
    try {
      setLoading(true);
      const response = await dataQualityApi.getIssues(projectId, filters);
      setIssues(response.results);
    } catch (err) {
      console.error('Failed to fetch issues:', err);
    } finally {
      setLoading(false);
    }
  }, [projectId, filters]);

  useEffect(() => {
    fetchIssues();
  }, [fetchIssues]);

  const resolveIssue = useCallback(async (issueId: number, notes?: string) => {
    try {
      await dataQualityApi.resolveIssue(issueId, notes);
      setIssues((prev) =>
        prev.map((issue) =>
          issue.id === issueId ? { ...issue, is_resolved: true } : issue
        )
      );
    } catch (err) {
      console.error('Failed to resolve issue:', err);
    }
  }, []);

  return {
    issues,
    loading,
    resolveIssue,
    refresh: fetchIssues,
  };
}

// ==================== Drift Detection Hooks ====================

export function useDriftReports(projectId: number) {
  const [reports, setReports] = useState<DriftReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchReports = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
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
    try {
      await driftDetectionApi.acknowledgeAlert(alertId);
      setAlerts((prev) =>
        prev.map((a) =>
          a.id === alertId ? { ...a, status: 'acknowledged' as const } : a
        )
      );
    } catch (err) {
      console.error('Failed to acknowledge alert:', err);
    }
  }, []);

  const resolveAlert = useCallback(async (alertId: number) => {
    try {
      await driftDetectionApi.resolveAlert(alertId);
      setAlerts((prev) =>
        prev.map((a) =>
          a.id === alertId ? { ...a, status: 'resolved' as const } : a
        )
      );
    } catch (err) {
      console.error('Failed to resolve alert:', err);
    }
  }, []);

  return {
    alerts,
    loading,
    acknowledgeAlert,
    resolveAlert,
    refresh: fetchAlerts,
  };
}

// ==================== Common Hooks ====================

export function useAsync<T>(
  asyncFunction: () => Promise<T>,
  dependencies: any[] = []
) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let isMounted = true;

    const execute = async () => {
      try {
        setLoading(true);
        setError(null);
        const result = await asyncFunction();
        if (isMounted) {
          setData(result);
        }
      } catch (err) {
        if (isMounted) {
          setError(err as Error);
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    execute();

    return () => {
      isMounted = false;
    };
  }, dependencies);

  return { data, loading, error };
}

export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}
