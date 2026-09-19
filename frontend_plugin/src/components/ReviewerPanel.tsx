/**
 * @file components/ReviewerPanel.tsx
 * @brief 交互式决策面板 —— 展示 Reviewer 沙盒日志，支持接受/拒绝操作
 *
 * 布局：
 *  ┌─────────────────────────────────────────────┐
 *  │  Reviewer 决策面板                            │
 *  │  ───────────────────────────────────────────│
 *  │  日志卡片 #1 (pending)                       │
 *  │    ├ AST 审计状态徽章                         │
 *  │    ├ 沙盒执行结果 + 耗时                      │
 *  │    ├ [查看脚本] 展开代码                       │
 *  │    ├ [接受修改]  [拒绝并重新分析]               │
 *  │    └ 拒绝原因输入框（拒绝后展开）              │
 *  │  ───────────────────────────────────────────│
 *  │  日志卡片 #2 (accepted)                      │
 *  │    └ ✓ 已接受                                │
 *  └─────────────────────────────────────────────┘
 */

import React, { useCallback, useMemo, useState } from "react";

import type { ReviewerPanelProps, ReviewLogEntry } from "../types";

// ── 样式 ─────────────────────────────────────────────────────

const PANEL_STYLE: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 10,
  fontFamily: "system-ui, -apple-system, sans-serif",
  fontSize: 13,
  color: "#e2e8f0",
};

const CARD_STYLE: React.CSSProperties = {
  border: "1px solid #1e293b",
  borderRadius: 8,
  padding: 14,
  backgroundColor: "#0f172a",
};

const SCRIPT_BOX_STYLE: React.CSSProperties = {
  backgroundColor: "#020617",
  border: "1px solid #1e293b",
  borderRadius: 6,
  padding: 10,
  fontSize: 11,
  fontFamily: "Consolas, 'Fira Code', monospace",
  color: "#a5f3fc",
  maxHeight: 200,
  overflowY: "auto",
  whiteSpace: "pre-wrap",
  wordBreak: "break-all",
  marginTop: 8,
  marginBottom: 8,
};

const LOG_BOX_STYLE: React.CSSProperties = {
  backgroundColor: "#020617",
  border: "1px solid #1e293b",
  borderRadius: 6,
  padding: 10,
  fontSize: 11,
  fontFamily: "Consolas, 'Fira Code', monospace",
  color: "#94a3b8",
  maxHeight: 120,
  overflowY: "auto",
  whiteSpace: "pre-wrap",
  marginTop: 8,
};

const BTN_BASE: React.CSSProperties = {
  padding: "6px 16px",
  borderRadius: 6,
  border: "none",
  cursor: "pointer",
  fontSize: 12,
  fontWeight: 600,
  fontFamily: "inherit",
  transition: "all 0.15s ease",
};

const BTN_ACCEPT: React.CSSProperties = {
  ...BTN_BASE,
  backgroundColor: "#16a34a",
  color: "#fff",
};

const BTN_REJECT: React.CSSProperties = {
  ...BTN_BASE,
  backgroundColor: "#dc2626",
  color: "#fff",
};

const BTN_GHOST: React.CSSProperties = {
  ...BTN_BASE,
  backgroundColor: "transparent",
  color: "#64748b",
  border: "1px solid #334155",
};

// ── 状态徽章 ─────────────────────────────────────────────────

const StatusBadge: React.FC<{ passed: boolean; label: string }> = ({
  passed,
  label,
}) => (
  <span
    style={{
      display: "inline-flex",
      alignItems: "center",
      gap: 4,
      padding: "2px 8px",
      borderRadius: 4,
      fontSize: 11,
      fontWeight: 600,
      backgroundColor: passed ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)",
      color: passed ? "#22c55e" : "#ef4444",
    }}
  >
    {passed ? "PASS" : "FAIL"} {label}
  </span>
);

const DecisionBadge: React.FC<{
  decision: "pending" | "accepted" | "rejected";
}> = ({ decision }) => {
  const colors = {
    pending:  { bg: "rgba(234,179,8,0.15)", text: "#eab308", label: "待决策" },
    accepted: { bg: "rgba(34,197,94,0.15)", text: "#22c55e", label: "已接受" },
    rejected: { bg: "rgba(239,68,68,0.15)", text: "#ef4444", label: "已拒绝" },
  };
  const c = colors[decision];
  return (
    <span
      style={{
        padding: "2px 10px",
        borderRadius: 4,
        fontSize: 11,
        fontWeight: 700,
        backgroundColor: c.bg,
        color: c.text,
      }}
    >
      {c.label}
    </span>
  );
};

// ── 单条日志卡片 ─────────────────────────────────────────────

interface LogCardProps {
  log: ReviewLogEntry;
  onAccept: (logId: string) => void;
  onReject: (logId: string, reason: string) => void;
}

const LogCard: React.FC<LogCardProps> = ({ log, onAccept, onReject }) => {
  const [showScript, setShowScript] = useState(false);
  const [showRejectInput, setShowRejectInput] = useState(false);
  const [rejectReason, setRejectReason] = useState("");

  const handleAccept = useCallback(() => {
    onAccept(log.logId);
  }, [onAccept, log.logId]);

  const handleReject = useCallback(() => {
    if (!rejectReason.trim()) return;
    onReject(log.logId, rejectReason.trim());
    setShowRejectInput(false);
    setRejectReason("");
  }, [onReject, log.logId, rejectReason]);

  const timeStr = useMemo(() => {
    try {
      return new Date(log.timestamp).toLocaleTimeString();
    } catch {
      return log.timestamp;
    }
  }, [log.timestamp]);

  const isPending = log.userDecision === "pending";

  return (
    <div
      style={{
        ...CARD_STYLE,
        opacity: isPending ? 1 : 0.7,
        borderColor: isPending ? "#334155" : "#1e293b",
      }}
    >
      {/* ── 标题行 ── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 8,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 11, color: "#64748b" }}>{timeStr}</span>
          <StatusBadge passed={log.astCheckPassed} label="AST" />
          <StatusBadge passed={log.sandboxSuccess} label="Sandbox" />
          {log.sandboxTimeMs > 0 && (
            <span style={{ fontSize: 11, color: "#475569" }}>
              {log.sandboxTimeMs.toFixed(0)}ms
            </span>
          )}
        </div>
        <DecisionBadge decision={log.userDecision} />
      </div>

      {/* ── AST 问题列表 ── */}
      {log.astIssues.length > 0 && (
        <div style={{ marginBottom: 8 }}>
          {log.astIssues.map((issue, i) => (
            <div
              key={i}
              style={{
                fontSize: 11,
                color: "#fca5a5",
                padding: "2px 0",
              }}
            >
              {issue}
            </div>
          ))}
        </div>
      )}

      {/* ── 沙盒日志 ── */}
      {log.sandboxLog && (
        <div style={LOG_BOX_STYLE}>{log.sandboxLog}</div>
      )}

      {/* ── 查看脚本按钮 ── */}
      <button
        type="button"
        onClick={() => setShowScript(!showScript)}
        style={{
          ...BTN_GHOST,
          marginBottom: 8,
          fontSize: 11,
          padding: "3px 10px",
        }}
      >
        {showScript ? "收起脚本" : "查看生成脚本"}
      </button>

      {showScript && (
        <div style={SCRIPT_BOX_STYLE}>{log.generatedScript}</div>
      )}

      {/* ── 操作栏 ── */}
      {isPending && (
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <button type="button" style={BTN_ACCEPT} onClick={handleAccept}>
            接受修改
          </button>
          <button
            type="button"
            style={BTN_REJECT}
            onClick={() => setShowRejectInput(!showRejectInput)}
          >
            拒绝并重新分析
          </button>
        </div>
      )}

      {/* ── 拒绝原因输入 ── */}
      {showRejectInput && isPending && (
        <div style={{ marginTop: 10 }}>
          <textarea
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            placeholder="请输入拒绝原因（自然语言），将反馈给 Reviewer 重新分析…"
            style={{
              width: "100%",
              minHeight: 64,
              padding: 8,
              backgroundColor: "#020617",
              border: "1px solid #334155",
              borderRadius: 6,
              color: "#e2e8f0",
              fontSize: 12,
              fontFamily: "inherit",
              resize: "vertical",
              outline: "none",
            }}
          />
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <button
              type="button"
              style={{
                ...BTN_REJECT,
                opacity: rejectReason.trim() ? 1 : 0.5,
              }}
              onClick={handleReject}
              disabled={!rejectReason.trim()}
            >
              确认拒绝
            </button>
            <button
              type="button"
              style={BTN_GHOST}
              onClick={() => {
                setShowRejectInput(false);
                setRejectReason("");
              }}
            >
              取消
            </button>
          </div>
        </div>
      )}

      {/* ── 已拒绝原因展示 ── */}
      {log.userDecision === "rejected" && log.rejectionReason && (
        <div
          style={{
            marginTop: 8,
            padding: 8,
            backgroundColor: "rgba(239,68,68,0.08)",
            borderRadius: 6,
            borderLeft: "3px solid #ef4444",
            fontSize: 12,
            color: "#fca5a5",
          }}
        >
          拒绝原因: {log.rejectionReason}
        </div>
      )}
    </div>
  );
};

// ══════════════════════════════════════════════════════════════
// 主面板
// ══════════════════════════════════════════════════════════════

export const ReviewerPanel: React.FC<ReviewerPanelProps> = ({
  reviewLogs,
  onAccept,
  onReject,
}) => {
  // 统计
  const stats = useMemo(() => {
    const pending  = reviewLogs.filter((l) => l.userDecision === "pending").length;
    const accepted = reviewLogs.filter((l) => l.userDecision === "accepted").length;
    const rejected = reviewLogs.filter((l) => l.userDecision === "rejected").length;
    return { pending, accepted, rejected, total: reviewLogs.length };
  }, [reviewLogs]);

  return (
    <div style={PANEL_STYLE}>
      {/* ── 标题栏 ── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 4,
        }}
      >
        <span style={{ fontWeight: 700, fontSize: 14 }}>
          Reviewer 决策面板
        </span>
        <div style={{ display: "flex", gap: 10, fontSize: 11, color: "#64748b" }}>
          <span>{stats.pending} 待决策</span>
          <span style={{ color: "#22c55e" }}>{stats.accepted} 已接受</span>
          <span style={{ color: "#ef4444" }}>{stats.rejected} 已拒绝</span>
        </div>
      </div>

      {/* ── 日志列表 ── */}
      {reviewLogs.length === 0 ? (
        <div
          style={{
            textAlign: "center",
            color: "#475569",
            padding: 32,
            fontSize: 13,
          }}
        >
          等待 Reviewer 生成审计日志…
        </div>
      ) : (
        reviewLogs.map((log) => (
          <LogCard
            key={log.logId}
            log={log}
            onAccept={onAccept}
            onReject={onReject}
          />
        ))
      )}
    </div>
  );
};
