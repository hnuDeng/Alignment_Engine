/**
 * @file store/types.ts
 * @brief Store layer type definitions -- extends types/index.ts with
 *        pipeline-specific state machines, normalized entities, and
 *        middleware protocol types.
 */

import type { DriftReport, DriftSeverity, WsConnectionStatus } from "../types";

// ══════════════════════════════════════════════════════════════
// Pipeline stage enums
// ══════════════════════════════════════════════════════════════

export enum PipelineStage {
  IDLE       = "idle",
  EXTRACTING = "extracting",
  ANALYZING  = "analyzing",
  REVIEWING  = "reviewing",
  EXECUTING  = "executing",
  COMPLETED  = "completed",
  FAILED     = "failed",
  CANCELLED  = "cancelled",
}

export enum ExtractorStatus {
  IDLE        = "idle",
  CONNECTING  = "connecting",
  FETCHING    = "fetching",
  SLICING     = "slicing",
  COMPLETED   = "completed",
  FAILED      = "failed",
}

export enum AnalyzerStatus {
  IDLE           = "idle",
  LOADING_MODEL  = "loading_model",
  WARMING_UP     = "warming_up",
  INFERRING      = "inferring",
  POST_PROCESSING = "post_processing",
  COMPLETED      = "completed",
  FAILED         = "failed",
  OUT_OF_MEMORY  = "out_of_memory",
}

export enum ReviewerStatus {
  IDLE            = "idle",
  GENERATING      = "generating_script",
  AST_CHECKING    = "ast_checking",
  SANDBOX_RUNNING = "sandbox_running",
  AWAITING_USER   = "awaiting_user_decision",
  EXECUTING       = "executing_update",
  COMPLETED       = "completed",
  FAILED          = "failed",
  REJECTED        = "rejected",
}

export enum ExecutionMode {
  CUDA     = "cuda",
  NUMPY    = "numpy",
  CPP_BFS  = "cpp_bfs",
  MOCK     = "mock",
}

export enum SeverityLevel {
  INFO     = "info",
  WARNING  = "warning",
  ERROR    = "error",
  CRITICAL = "critical",
}

// ══════════════════════════════════════════════════════════════
// Normalized entity interfaces (for DataNormalizer)
// ══════════════════════════════════════════════════════════════

export interface NormalizedSample {
  sampleId: string;
  label: string;
  labelId: number;
  embedding: number[] | null;
  isDrift: boolean;
  isolationScore: number;
  centroidDistance: number;
  reason: string;
  severity: DriftSeverity;
  /** ID of the parent report */
  reportId: string;
  /** Index in the original points array */
  pointIndex: number;
}

export interface NormalizedReport {
  reportId: string;
  timestamp: string;
  analysisMode: ExecutionMode;
  stats: DriftReport["stats"];
  /** Ordered list of sample IDs in this report */
  sampleIds: string[];
}

export interface NormalizedReviewLog {
  logId: string;
  reportId: string;
  timestamp: string;
  generatedScript: string;
  astCheckPassed: boolean;
  astIssues: string[];
  sandboxSuccess: boolean;
  sandboxLog: string;
  sandboxTimeMs: number;
  userDecision: "pending" | "accepted" | "rejected";
  rejectionReason?: string;
}

/** The normalized entity store shape. */
export interface NormalizedEntities {
  samples: Record<string, NormalizedSample>;
  reports: Record<string, NormalizedReport>;
  reviewLogs: Record<string, NormalizedReviewLog>;
}

// ══════════════════════════════════════════════════════════════
// Agent pipeline state
// ══════════════════════════════════════════════════════════════

export interface ExtractorState {
  status: ExtractorStatus;
  lastSliceId: string | null;
  sliceCount: number;
  totalSamplesExtracted: number;
  errorMessage: string | null;
  lastFetchTimestamp: number | null;
}

export interface AnalyzerState {
  status: AnalyzerStatus;
  executionMode: ExecutionMode;
  modelLoaded: boolean;
  modelName: string | null;
  vramUsedMb: number;
  vramTotalMb: number;
  batchSize: number;
  inferenceCount: number;
  errorMessage: string | null;
  lastInferenceTimestamp: number | null;
}

export interface ReviewerState {
  status: ReviewerStatus;
  currentLogId: string | null;
  pendingDecisionCount: number;
  acceptedCount: number;
  rejectedCount: number;
  errorMessage: string | null;
  lastReviewTimestamp: number | null;
}

export interface AgentState {
  pipeline: PipelineStage;
  extractor: ExtractorState;
  analyzer: AnalyzerState;
  reviewer: ReviewerState;
  connectionStatus: WsConnectionStatus;
  lastHeartbeat: number | null;
  isStreaming: boolean;
}

// ══════════════════════════════════════════════════════════════
// Dataset state
// ══════════════════════════════════════════════════════════════

export interface DatasetFilter {
  labelIds: number[];
  severityLevels: DriftSeverity[];
  driftOnly: boolean;
  searchQuery: string;
}

export interface DatasetStats {
  totalSamples: number;
  driftCount: number;
  labelDistribution: Record<number, number>;
  meanIsolationScore: number;
  maxIsolationScore: number;
}

export interface DatasetState {
  datasetName: string | null;
  /** Normalized entity store */
  entities: NormalizedEntities;
  /** Current UMAP snapshot ID */
  currentSnapshotId: string | null;
  /** Highlighted sample IDs */
  highlightedSampleIds: string[];
  /** Current filter */
  filter: DatasetFilter;
  /** Cached stats */
  stats: DatasetStats;
  /** Ordered report IDs (newest first) */
  reportOrder: string[];
  /** Ordered review log IDs (newest first) */
  reviewLogOrder: string[];
  /** Selected sample IDs from box-select */
  boxSelectedSampleIds: string[];
  /** Error log */
  errors: Array<{ timestamp: number; message: string; severity: SeverityLevel }>;
}

// ══════════════════════════════════════════════════════════════
// Combined root state
// ══════════════════════════════════════════════════════════════

export interface RootState {
  agent: AgentState;
  dataset: DatasetState;
}

// ══════════════════════════════════════════════════════════════
// WebSocket middleware types
// ══════════════════════════════════════════════════════════════

export interface WsMiddlewareConfig {
  url: string;
  reconnectBaseMs: number;
  reconnectMaxMs: number;
  heartbeatIntervalMs: number;
  heartbeatTimeoutMs: number;
  maxQueueSize: number;
  serializationFormat: "json" | "msgpack";
}

export interface WsOutboundMessage {
  type: string;
  payload: unknown;
  seq: number;
  timestamp: number;
}

export interface WsInboundMessage {
  type: string;
  payload: unknown;
  seq: number;
  timestamp: number;
}

export type WsMiddlewareEvent =
  | { event: "connected" }
  | { event: "disconnected"; code: number; reason: string }
  | { event: "reconnecting"; attempt: number; delayMs: number }
  | { event: "message"; message: WsInboundMessage }
  | { event: "error"; error: string }
  | { event: "heartbeat_sent" }
  | { event: "heartbeat_timeout" };
