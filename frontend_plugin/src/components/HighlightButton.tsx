/**
 * @file components/HighlightButton.tsx
 * @brief 高亮按钮组件 —— 支持 toggle 高亮状态 + FiftyOne 视图联动
 *
 * 状态映射：
 *  - 未高亮 → 显示"高亮异常样本"（primary/danger 变体）
 *  - 已高亮 → 显示"取消高亮"（ghost 变体 + 取消图标）
 */

import React, { useCallback, useMemo } from "react";
import type { HighlightButtonProps } from "../types";

// ── 样式常量 ─────────────────────────────────────────────────
const STYLES = {
  base: {
    display: "inline-flex",
    alignItems: "center",
    gap: "6px",
    padding: "6px 14px",
    borderRadius: "6px",
    border: "none",
    cursor: "pointer",
    fontSize: "13px",
    fontWeight: 600,
    fontFamily: "inherit",
    transition: "all 0.15s ease",
    userSelect: "none" as const,
  },
  primary: {
    backgroundColor: "#3b82f6",
    color: "#fff",
  },
  danger: {
    backgroundColor: "#ef4444",
    color: "#fff",
  },
  ghost: {
    backgroundColor: "transparent",
    color: "#94a3b8",
    border: "1px solid #334155",
  },
  disabled: {
    opacity: 0.5,
    cursor: "not-allowed",
  },
} as const;

// ── 图标 ─────────────────────────────────────────────────────
const EyeIcon: React.FC = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
       stroke="currentColor" strokeWidth="2" strokeLinecap="round"
       strokeLinejoin="round">
    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
    <circle cx="12" cy="12" r="3" />
  </svg>
);

const EyeOffIcon: React.FC = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
       stroke="currentColor" strokeWidth="2" strokeLinecap="round"
       strokeLinejoin="round">
    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
    <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
    <line x1="1" y1="1" x2="23" y2="23" />
  </svg>
);

// ── 组件 ─────────────────────────────────────────────────────

export const HighlightButton: React.FC<HighlightButtonProps> = ({
  sampleIds,
  highlightedIds,
  onClick,
  variant = "primary",
}) => {
  // 判断此组样本是否全部已高亮
  const isHighlighted = useMemo(
    () => sampleIds.length > 0 && sampleIds.every((id) => highlightedIds.has(id)),
    [sampleIds, highlightedIds]
  );

  const handleClick = useCallback(() => {
    if (sampleIds.length === 0) return;
    onClick();
  }, [onClick, sampleIds.length]);

  const style = useMemo(
    () => ({
      ...STYLES.base,
      ...(isHighlighted ? STYLES.ghost : STYLES[variant]),
      ...(sampleIds.length === 0 ? STYLES.disabled : {}),
    }),
    [isHighlighted, variant, sampleIds.length]
  );

  return (
    <button
      type="button"
      style={style}
      onClick={handleClick}
      disabled={sampleIds.length === 0}
      title={isHighlighted ? "取消高亮" : `高亮 ${sampleIds.length} 个异常样本`}
    >
      {isHighlighted ? <EyeOffIcon /> : <EyeIcon />}
      <span>
        {isHighlighted
          ? "取消高亮"
          : `高亮 (${sampleIds.length})`}
      </span>
    </button>
  );
};
