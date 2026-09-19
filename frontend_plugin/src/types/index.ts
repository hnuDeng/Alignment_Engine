/**
 * @file types/index.ts
 * @brief Agent_Copilot 插件的完整类型系统
 *
 * 覆盖 WebSocket 消息协议、漂移诊断数据、UMAP 散点数据、
 * Reviewer 决策、FiftyOne 状态桥接等全部类型定义。
 */

// ══════════════════════════════════════════════════════════════
// WebSocket 消息协议
// ══════════════════════════════════════════════════════════════

export type WsConnectionStatus =
  | "connecting"
  | "connected"
  | "disconnected"
  | "error";

export enum DriftMessageType {
  STREAM_START  = "stream_start",
  DRIFT_EVENT   = "drift_event",
  DRIFT_REPORT  = "drift_report",
  STREAM_END    = "stream_end",
  HEARTBEAT     = "heartbeat",
  UMAP_UPDATE   = "umap_update",
  REVIEW_LOG    = "review_log",
}

export enum DriftSeverity {
  LOW      = "low",
  MEDIUM   = "medium",
  HIGH     = "high",
  CRITICAL = "critical",
}

// ══════════════════════════════════════════════════════════════
// 漂移诊断数据
// ══════════════════════════════════════════════════════════════

export interface DriftSample {
  sampleId: string;
  isolationScore: number;
  centroidDistance: number;
  reason: string;
  severity: DriftSeverity;
}

export interface DriftReport {
  reportId: string;
  timestamp: string;
  analysisMode: "cuda" | "numpy" | "cpp_bfs";
  samples: DriftSample[];
  stats: {
    totalSamples: number;
    meanDistance: number;
    threshold: number;
    driftCount: number;
  };
}

export interface DriftWsMessage {
  type: DriftMessageType;
  payload: DriftReport | DriftSample[] | UmapSnapshot | ReviewLogEntry | null;
  seq: number;
}

// ══════════════════════════════════════════════════════════════
// UMAP 散点数据
// ══════════════════════════════════════════════════════════════

/** 单个 UMAP 投影点 */
export interface UmapPoint {
  sampleId: string;
  /** UMAP 降维后的 2D 坐标 */
  x: number;
  y: number;
  /** 原始标签 ID（用于着色） */
  labelId: number;
  /** 原始标签名 */
  label: string;
  /** 是否为漂移异常样本 */
  isDrift: boolean;
  /** 孤立度分数（仅异常样本有值） */
  isolationScore?: number;
}

/** UMAP 快照（后端一次性推送所有点） */
export interface UmapSnapshot {
  snapshotId: string;
  timestamp: string;
  points: UmapPoint[];
  /** 各标签 ID → 颜色映射 */
  labelColorMap: Record<number, string>;
}

// ══════════════════════════════════════════════════════════════
// Reviewer 决策日志
// ══════════════════════════════════════════════════════════════

export interface ReviewLogEntry {
  /** 日志 ID */
  logId: string;
  /** 关联的漂移报告 ID */
  reportId: string;
  timestamp: string;
  /** Reviewer 生成的脚本内容 */
  generatedScript: string;
  /** AST 审计是否通过 */
  astCheckPassed: boolean;
  /** AST 审计发现的问题 */
  astIssues: string[];
  /** 沙盒执行是否成功 */
  sandboxSuccess: boolean;
  /** 沙盒执行日志 */
  sandboxLog: string;
  /** 沙盒执行耗时（毫秒） */
  sandboxTimeMs: number;
  /** 用户决策状态 */
  userDecision: "pending" | "accepted" | "rejected";
  /** 用户拒绝时的自然语言反馈 */
  rejectionReason?: string;
}

// ══════════════════════════════════════════════════════════════
// 插件状态
// ══════════════════════════════════════════════════════════════

export interface AgentCopilotState {
  connectionStatus: WsConnectionStatus;
  reports: DriftReport[];
  highlightedSampleIds: Set<string>;
  isStreaming: boolean;
  lastHeartbeat: number | null;
  /** UMAP 散点快照 */
  umapSnapshot: UmapSnapshot | null;
  /** Reviewer 日志列表 */
  reviewLogs: ReviewLogEntry[];
}

export type AgentCopilotAction =
  | { type: "WS_STATUS_CHANGED"; status: WsConnectionStatus }
  | { type: "REPORT_RECEIVED"; report: DriftReport }
  | { type: "HIGHLIGHT_SAMPLES"; sampleIds: string[] }
  | { type: "CLEAR_HIGHLIGHTS" }
  | { type: "SET_STREAMING"; active: boolean }
  | { type: "HEARTBEAT_RECEIVED" }
  | { type: "UMAP_RECEIVED"; snapshot: UmapSnapshot }
  | { type: "REVIEW_LOG_RECEIVED"; log: ReviewLogEntry }
  | { type: "USER_DECISION"; logId: string; decision: "accepted" | "rejected"; reason?: string }
  | { type: "RESET" };

// ══════════════════════════════════════════════════════════════
// FiftyOne 状态桥接
// ══════════════════════════════════════════════════════════════

export interface FiftyOneDatasetBridge {
  setSelectedSamples(sampleIds: string[]): void;
  getDatasetName(): string;
  flashSamples(sampleIds: string[], duration?: number): void;
}

// ══════════════════════════════════════════════════════════════
// 组件 Props
// ══════════════════════════════════════════════════════════════

export interface AgentCopilotPanelProps {
  wsEndpoint: string;
  datasetBridge: FiftyOneDatasetBridge;
  maxReports?: number;
}

export interface DriftAlertProps {
  report: DriftReport;
  onHighlight: (sampleIds: string[]) => void;
  expanded: boolean;
  onToggleExpand: () => void;
}

export interface HighlightButtonProps {
  sampleIds: string[];
  highlightedIds: Set<string>;
  onClick: () => void;
  variant?: "primary" | "danger" | "ghost";
}

export interface DriftScatterPlotProps {
  /** UMAP 快照数据 */
  snapshot: UmapSnapshot | null;
  /** 当前高亮的样本 ID 集合 */
  highlightedIds: Set<string>;
  /** 点击散点时的回调 */
  onPointClick?: (sampleId: string) => void;
  /** 框选完成时的回调 */
  onSelectionComplete?: (sampleIds: string[]) => void;
  /** 画布宽度（默认撑满容器） */
  width?: number;
  /** 画布高度（默认 480） */
  height?: number;
}

export interface ReviewerPanelProps {
  /** Reviewer 日志列表 */
  reviewLogs: ReviewLogEntry[];
  /** 用户点击"接受修改" */
  onAccept: (logId: string) => void;
  /** 用户点击"拒绝并重新分析" */
  onReject: (logId: string, reason: string) => void;
}
