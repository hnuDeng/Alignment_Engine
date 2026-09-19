/**
 * Data-Centric AI Workflow - TypeScript Type Definitions
 */

// ==================== Active Learning Types ====================

export type StrategyType = 
  | 'uncertainty' 
  | 'diversity' 
  | 'committee' 
  | 'hybrid' 
  | 'random';

export type UncertaintyMethod = 
  | 'least_confidence' 
  | 'margin_sampling' 
  | 'entropy';

export interface ActiveLearningConfig {
  id: number;
  project_id: number;
  strategy: StrategyType;
  uncertainty_method: UncertaintyMethod;
  batch_size: number;
  is_enabled: boolean;
  auto_select: boolean;
  auto_train: boolean;
  min_annotations_for_training: number;
  diversity_metric: string;
  committee_size: number;
  strategy_params: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface ActiveLearningRound {
  id: number;
  config_id: number;
  round_number: number;
  selected_tasks: number[];
  task_count: number;
  strategy_used: string;
  selection_scores: Record<number, number>;
  avg_uncertainty: number | null;
  diversity_score: number | null;
  is_completed: boolean;
  completed_at: string | null;
  created_at: string;
}

export interface SelectionResult {
  round_id: number;
  round_number: number;
  selected_task_ids: number[];
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

export interface TaskScore {
  task_id: number;
  uncertainty_score: number | null;
  diversity_score: number | null;
  committee_disagreement: number | null;
  final_score: number;
  rank: number;
  is_selected: boolean;
}

// ==================== Data Quality Types ====================

export type ReportType = 'project' | 'annotator' | 'task' | 'label';

export type IssueType = 
  | 'inconsistency' 
  | 'outlier' 
  | 'bias' 
  | 'missing' 
  | 'conflict' 
  | 'low_agreement' 
  | 'speed_anomaly';

export type SeverityLevel = 'low' | 'medium' | 'high' | 'critical';

export interface QualityReport {
  id: number;
  project_id: number;
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
  issues: QualityIssue[];
  created_at: string;
  created_by: number | null;
}

export interface QualityIssue {
  id: number;
  report_id: number;
  issue_type: IssueType;
  severity: SeverityLevel;
  title: string;
  description: string;
  task_id: number | null;
  annotation_id: number | null;
  annotator_id: number | null;
  details: Record<string, any>;
  is_resolved: boolean;
  resolved_at: string | null;
  resolved_by: number | null;
  resolution_notes: string;
  created_at: string;
}

export interface AnnotatorProfile {
  id: number;
  user_id: number;
  project_id: number;
  username: string;
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

export interface LabelStats {
  id: number;
  project_id: number;
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
  has_data: boolean;
  overall_score?: number;
  consistency_score?: number;
  agreement_score?: number;
  completeness_score?: number;
  total_issues?: number;
  critical_issues?: number;
  issue_counts?: Record<string, number>;
  tasks_analyzed?: number;
  annotations_analyzed?: number;
  annotators_analyzed?: number;
  last_updated?: string;
}

// ==================== Drift Detection Types ====================

export type DriftLevel = 'none' | 'low' | 'medium' | 'high' | 'critical';

export type AlertStatus = 'active' | 'acknowledged' | 'resolved';

export type AlertType = 'feature' | 'label' | 'concept' | 'quality';

export interface DriftBaseline {
  id: number;
  project_id: number;
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
  project_id: number;
  baseline_id: number;
  drift_level: DriftLevel;
  feature_drift_score: number | null;
  label_drift_score: number | null;
  overall_drift_score: number;
  details: Record<string, any>;
  window_start: string | null;
  window_end: string | null;
  task_count: number;
  created_at: string;
}

export interface DriftAlert {
  id: number;
  project_id: number;
  report_id: number | null;
  alert_type: AlertType;
  status: AlertStatus;
  message: string;
  details: Record<string, any>;
  notified_users: number[];
  created_at: string;
  acknowledged_at: string | null;
  acknowledged_by: number | null;
  resolved_at: string | null;
}

export interface DriftMonitorConfig {
  id: number;
  project_id: number;
  is_enabled: boolean;
  check_interval_hours: number;
  feature_drift_threshold: number;
  label_drift_threshold: number;
  alert_on_drift: boolean;
  notify_users: number[];
  created_at: string;
  updated_at: string;
}

// ==================== Common Types ====================

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

export interface ApiError {
  detail: string;
  code?: string;
}

// ==================== UI Types ====================

export type TabType = 'active-learning' | 'data-quality' | 'drift-detection';

export interface ScoreCardData {
  title: string;
  value: number;
  suffix?: string;
  trend?: 'up' | 'down' | 'stable';
  trendValue?: number;
  color?: 'green' | 'red' | 'yellow' | 'blue';
}

export interface ChartDataPoint {
  name: string;
  value: number;
  label?: string;
}

export interface TrendDataPoint {
  date: string;
  value: number;
}
