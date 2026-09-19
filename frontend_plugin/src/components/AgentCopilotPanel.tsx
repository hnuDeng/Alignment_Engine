/**
 * @file components/AgentCopilotPanel.tsx
 * @brief Agent_Copilot 主面板组件
 *
 * 布局：
 *  ┌─────────────────────────────────────┐
 *  │  状态栏：连接状态 + 流控制按钮        │
 *  │  ───────────────────────────────────│
 *  │  漂移报告列表（最新的在前）           │
 *  │    ├ DriftAlert #1                   │
 *  │    ├ DriftAlert #2                   │
 *  │    └ ...                             │
 *  │  ───────────────────────────────────│
 *  │  底部工具栏：清除 + 统计              │
 *  └─────────────────────────────────────┘
 *
 * 与 FiftyOne 的交互：
 *  - 点击"高亮"按钮 → 通过 datasetBridge.setSelectedSamples 更新主视图
 *  - 漂移报告中的 sampleId 直接对应 FiftyOne dataset 的 sample.id
 */

import React, { useCallback, useMemo, useState } from "react";

import { useDriftStream } from "../hooks/useDriftStream";
import type { AgentCopilotPanelProps, WsConnectionStatus } from "../types";
import { DriftAlert } from "./DriftAlert";

// ══════════════════════════════════════════════════════════════
// 样式常量
// ══════════════════════════════════════════════════════════════

const PANEL_STYLE: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  height: "100%",
  backgroundColor: "#020617",
  color: "#e2e8f0",
  fontFamily: "system-ui, -apple-system, sans-serif",
  fontSize: "13px",
  overflow: "hidden",
};

const STATUS_BAR_STYLE: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "10px 12px",
  borderBottom: "1px solid #1e293b",
  backgroundColor: "#0f172a",
  flexShrink: 0,
};

const REPORTS_AREA_STYLE: React.CSSProperties = {
  flex: 1,
  overflowY: "auto",
  padding: "12px",
};

const FOOTER_STYLE: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "8px 12px",
  borderTop: "1px solid #1e293b",
  backgroundColor: "#0f172a",
  fontSize: "11px",
  color: "#64748b",
  flexShrink: 0,
};

// ══════════════════════════════════════════════════════════════
// 连接状态指示器
// ══════════════════════════════════════════════════════════════

const STATUS_COLORS: Record<WsConnectionStatus, string> = {
  connected: "#22c55e",
  connecting: "#eab308",
  disconnected: "#64748b",
  error: "#ef4444",
};

const STATUS_LABELS: Record<WsConnectionStatus, string> = {
  connected: "已连接",
  connecting: "连接中…",
  disconnected: "未连接",
  error: "连接错误",
};

const StatusIndicator: React.FC<{ status: WsConnectionStatus }> = ({
  status,
}) => (
  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
    <div
      style={{
        width: "8px",
        height: "8px",
        borderRadius: "50%",
        backgroundColor: STATUS_COLORS[status],
        boxShadow: status === "connected" ? `0 0 6px ${STATUS_COLORS[status]}` : "none",
      }}
    />
    <span style={{ fontSize: "12px", color: "#94a3b8" }}>
      {STATUS_LABELS[status]}
    </span>
  </div>
);

// ══════════════════════════════════════════════════════════════
// 主面板组件
// ══════════════════════════════════════════════════════════════

export const AgentCopilotPanel: React.FC<AgentCopilotPanelProps> = ({
  wsEndpoint,
  datasetBridge,
}) => {
  const {
    state,
    connect,
    disconnect,
    toggleHighlight,
    clearHighlights,
  } = useDriftStream({
    wsEndpoint,
    autoConnect: true,
  });

  // 展开/折叠状态管理（reportId → boolean）
  const [expandedReports, setExpandedReports] = useState<Set<string>>(
    new Set()
  );

  const toggleExpand = useCallback((reportId: string) => {
    setExpandedReports((prev) => {
      const next = new Set(prev);
      if (next.has(reportId)) {
        next.delete(reportId);
      } else {
        next.add(reportId);
      }
      return next;
    });
  }, []);

  // 高亮处理：同步到 FiftyOne 主视图
  const handleHighlight = useCallback(
    (sampleIds: string[]) => {
      toggleHighlight(sampleIds);

      // 通过 FiftyOne 状态桥接更新主视图
      const newHighlighted = new Set(state.highlightedSampleIds);
      for (const id of sampleIds) {
        if (newHighlighted.has(id)) {
          newHighlighted.delete(id);
        } else {
          newHighlighted.add(id);
        }
      }

      if (newHighlighted.size > 0) {
        datasetBridge.setSelectedSamples(Array.from(newHighlighted));
        datasetBridge.flashSamples(Array.from(newHighlighted), 2000);
      } else {
        datasetBridge.setSelectedSamples([]);
      }
    },
    [toggleHighlight, state.highlightedSampleIds, datasetBridge]
  );

  // 清除所有高亮并同步 FiftyOne
  const handleClearAll = useCallback(() => {
    clearHighlights();
    datasetBridge.setSelectedSamples([]);
  }, [clearHighlights, datasetBridge]);

  // 当高亮集合变化时自动滚动到最新报告
  const reportCount = state.reports.length;
  const driftSampleCount = useMemo(
    () => state.reports.reduce((sum, r) => sum + r.samples.length, 0),
    [state.reports]
  );

  // 连接/断开切换按钮
  const isConnected = state.connectionStatus === "connected";
  const toggleConnection = useCallback(() => {
    if (isConnected) {
      disconnect();
    } else {
      connect();
    }
  }, [isConnected, connect, disconnect]);

  return (
    <div style={PANEL_STYLE}>
      {/* ── 状态栏 ── */}
      <div style={STATUS_BAR_STYLE}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <span style={{ fontWeight: 700, fontSize: "14px" }}>
            Agent Copilot
          </span>
          <StatusIndicator status={state.connectionStatus} />
        </div>
        <button
          type="button"
          onClick={toggleConnection}
          style={{
            padding: "4px 12px",
            borderRadius: "4px",
            border: "1px solid #334155",
            backgroundColor: isConnected ? "transparent" : "#1e40af",
            color: isConnected ? "#94a3b8" : "#fff",
            cursor: "pointer",
            fontSize: "12px",
            fontWeight: 600,
          }}
        >
          {isConnected ? "断开" : "连接"}
        </button>
      </div>

      {/* ── 报告列表 ── */}
      <div style={REPORTS_AREA_STYLE}>
        {state.reports.length === 0 ? (
          <div
            style={{
              textAlign: "center",
              color: "#475569",
              padding: "40px 0",
            }}
          >
            {state.connectionStatus === "connected"
              ? "等待漂移诊断事件…"
              : "未连接到后端 Analyzer"}
          </div>
        ) : (
          state.reports.map((report) => (
            <DriftAlert
              key={report.reportId}
              report={report}
              onHighlight={handleHighlight}
              expanded={expandedReports.has(report.reportId)}
              onToggleExpand={() => toggleExpand(report.reportId)}
            />
          ))
        )}
      </div>

      {/* ── 底部工具栏 ── */}
      <div style={FOOTER_STYLE}>
        <span>
          {reportCount} 份报告 · {driftSampleCount} 个异常样本 ·{" "}
          {state.highlightedSampleIds.size} 个已高亮
        </span>
        <button
          type="button"
          onClick={handleClearAll}
          style={{
            background: "none",
            border: "1px solid #334155",
            borderRadius: "4px",
            color: "#64748b",
            cursor: "pointer",
            padding: "2px 10px",
            fontSize: "11px",
          }}
        >
          清除高亮
        </button>
      </div>
    </div>
  );
};
