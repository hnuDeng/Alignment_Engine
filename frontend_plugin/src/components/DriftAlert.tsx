/**
 * @file components/DriftAlert.tsx
 * @brief 单条漂移警报卡片组件
 *
 * 布局：
 *  - 标题行：时间戳 + 严重等级徽章 + 样本数
 *  - 折叠区：每个异常样本的详细信息（ID、分数、原因）
 *  - 操作栏：高亮按钮 + 展开/折叠切换
 *
 * 严重等级颜色映射：
 *  CRITICAL → red-500, HIGH → orange-500, MEDIUM → yellow-500, LOW → blue-400
 */

import React, { useCallback, useMemo } from "react";
import type { DriftAlertProps } from "../types"
import { DriftSeverity } from "../types";
import { HighlightButton } from "./HighlightButton";

// ── 严重等级颜色映射 ─────────────────────────────────────────
const SEVERITY_COLORS: Record<DriftSeverity, { bg: string; text: string; label: string }> = {
  critical: { bg: "#fee2e2", text: "#dc2626", label: "CRITICAL" },
  high:     { bg: "#ffedd5", text: "#ea580c", label: "HIGH" },
  medium:   { bg: "#fef9c3", text: "#ca8a04", label: "MEDIUM" },
  low:      { bg: "#dbeafe", text: "#2563eb", label: "LOW" },
};

// ── 样式 ─────────────────────────────────────────────────────
const CARD_STYLE: React.CSSProperties = {
  border: "1px solid #1e293b",
  borderRadius: "8px",
  padding: "12px",
  marginBottom: "8px",
  backgroundColor: "#0f172a",
  fontFamily: "system-ui, -apple-system, sans-serif",
  fontSize: "13px",
  color: "#e2e8f0",
};

const HEADER_STYLE: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  marginBottom: "8px",
};

const STAT_STYLE: React.CSSProperties = {
  display: "flex",
  gap: "12px",
  fontSize: "12px",
  color: "#94a3b8",
  marginBottom: "8px",
};

const SAMPLE_ROW_STYLE: React.CSSProperties = {
  display: "flex",
  alignItems: "flex-start",
  gap: "8px",
  padding: "6px 0",
  borderTop: "1px solid #1e293b",
  fontSize: "12px",
};

// ── 组件 ─────────────────────────────────────────────────────

export const DriftAlert: React.FC<DriftAlertProps> = ({
  report,
  onHighlight,
  expanded,
  onToggleExpand,
}) => {
  const sampleIds = useMemo(
    () => report.samples.map((s) => s.sampleId),
    [report.samples]
  );

  // 推断整体严重等级：取最高
  const overallSeverity = useMemo(() => {
    const order: Record<string, number> = {
      critical: 4, high: 3, medium: 2, low: 1,
    };
    let maxSev: DriftSeverity = DriftSeverity.LOW;
    for (const s of report.samples) {
      if ((order[s.severity] ?? 0) > (order[maxSev] ?? 0)) {
        maxSev = s.severity;
      }
    }
    return maxSev;
  }, [report.samples]);

  const sevColor = SEVERITY_COLORS[overallSeverity];

  const handleHighlight = useCallback(() => {
    onHighlight(sampleIds);
  }, [onHighlight, sampleIds]);

  // 时间格式化
  const timeStr = useMemo(() => {
    try {
      return new Date(report.timestamp).toLocaleTimeString();
    } catch {
      return report.timestamp;
    }
  }, [report.timestamp]);

  return (
    <div style={CARD_STYLE}>
      {/* ── 标题行 ── */}
      <div style={HEADER_STYLE}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ fontSize: "11px", color: "#64748b" }}>{timeStr}</span>
          <span
            style={{
              padding: "2px 8px",
              borderRadius: "4px",
              backgroundColor: sevColor.bg,
              color: sevColor.text,
              fontSize: "11px",
              fontWeight: 700,
            }}
          >
            {sevColor.label}
          </span>
          <span style={{ fontSize: "12px", color: "#cbd5e1" }}>
            {report.samples.length} 个异常样本
          </span>
        </div>
        <span style={{ fontSize: "11px", color: "#475569" }}>
          {report.analysisMode}
        </span>
      </div>

      {/* ── 统计行 ── */}
      <div style={STAT_STYLE}>
        <span>均值距离: {report.stats.meanDistance.toFixed(4)}</span>
        <span>阈值: {report.stats.threshold.toFixed(4)}</span>
        <span>总量: {report.stats.totalSamples}</span>
      </div>

      {/* ── 操作栏 ── */}
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        <HighlightButton
          sampleIds={sampleIds}
          highlightedIds={new Set()}
          onClick={handleHighlight}
          variant={overallSeverity === "critical" ? "danger" : "primary"}
        />
        <button
          type="button"
          onClick={onToggleExpand}
          style={{
            background: "none",
            border: "none",
            color: "#64748b",
            cursor: "pointer",
            fontSize: "12px",
            padding: "4px 8px",
          }}
        >
          {expanded ? "收起详情 ▲" : "展开详情 ▼"}
        </button>
      </div>

      {/* ── 折叠区：样本详情 ── */}
      {expanded && (
        <div style={{ marginTop: "8px" }}>
          {report.samples.map((sample) => {
            const sColor = SEVERITY_COLORS[sample.severity];
            return (
              <div key={sample.sampleId} style={SAMPLE_ROW_STYLE}>
                <code
                  style={{
                    color: "#38bdf8",
                    fontSize: "11px",
                    minWidth: "80px",
                  }}
                >
                  {sample.sampleId.slice(0, 8)}
                </code>
                <span
                  style={{
                    padding: "1px 6px",
                    borderRadius: "3px",
                    backgroundColor: sColor.bg,
                    color: sColor.text,
                    fontSize: "10px",
                    fontWeight: 600,
                  }}
                >
                  {sample.severity.toUpperCase()}
                </span>
                <span style={{ flex: 1, color: "#94a3b8" }}>
                  {sample.reason}
                </span>
                <span style={{ color: "#64748b", whiteSpace: "nowrap" }}>
                  score={sample.isolationScore.toFixed(2)}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
