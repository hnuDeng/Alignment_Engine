/**
 * @file components/ui/SandboxLogViewer.tsx
 * @brief Sandbox log viewer with syntax highlighting and collapsible sections.
 *
 * Features:
 *  - Syntax highlighting for Python/shell code blocks
 *  - Collapsible sections (click line number gutter)
 *  - Auto-scroll to bottom on new content
 *  - Search/filter with match highlighting
 *  - ARIA log roles and keyboard navigation
 *
 * No external dependencies.
 */

import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

// ══════════════════════════════════════════════════════════════
// Types
// ══════════════════════════════════════════════════════════════

export type LogLineType = "stdout" | "stderr" | "system" | "error" | "info" | "code" | "separator";

export interface LogLine {
  /** Unique line ID */
  id: string;
  /** Line number (1-based) */
  lineNo: number;
  /** Raw text content */
  text: string;
  /** Line type for coloring */
  type: LogLineType;
  /** If true, this line starts a collapsible section */
  sectionStart?: boolean;
  /** Section title (for collapsible headers) */
  sectionTitle?: string;
}

export interface SandboxLogViewerProps {
  /** Raw log text */
  content: string;
  /** Height (default 400) */
  height?: number;
  /** Whether to auto-scroll to bottom */
  autoScroll?: boolean;
  /** Search filter */
  searchQuery?: string;
  /** ARIA label */
  ariaLabel?: string;
  /** Called when user copies a line */
  onLineCopy?: (line: LogLine) => void;
}

// ══════════════════════════════════════════════════════════════
// Syntax highlighting patterns
// ══════════════════════════════════════════════════════════════

const KEYWORDS = /\b(import|from|def|class|if|elif|else|for|while|return|try|except|finally|with|as|yield|raise|pass|break|continue|and|or|not|in|is|lambda|async|await|True|False|None)\b/g;
const STRINGS = /(["'])(?:(?=(\\?))\2.)*?\1/g;
const COMMENTS = /(#.*$)/gm;

function highlightSyntax(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];

  let key = 0;

  // Simple token-based highlighting
  const tokens: Array<{ start: number; end: number; type: string }> = [];

  // Find comments
  let m: RegExpExecArray | null;
  COMMENTS.lastIndex = 0;
  while ((m = COMMENTS.exec(text)) !== null) {
    tokens.push({ start: m.index, end: m.index + m[0].length, type: "comment" });
  }

  // Find strings
  STRINGS.lastIndex = 0;
  while ((m = STRINGS.exec(text)) !== null) {
    tokens.push({ start: m.index, end: m.index + m[0].length, type: "string" });
  }

  // Sort by start position, non-overlapping
  tokens.sort((a, b) => a.start - b.start);
  const merged: typeof tokens = [];
  for (const t of tokens) {
    if (merged.length > 0 && t.start < merged[merged.length - 1].end) continue;
    merged.push(t);
  }

  // Build parts
  let pos = 0;
  for (const t of merged) {
    if (t.start > pos) {
      parts.push(highlightKeywords(text.slice(pos, t.start), key++));
    }
    const style: React.CSSProperties = {
      color: t.type === "comment" ? "var(--ac-fg3)" : "#a5f3fc",
    };
    parts.push(<span key={key++} style={style}>{text.slice(t.start, t.end)}</span>);
    pos = t.end;
  }
  if (pos < text.length) {
    parts.push(highlightKeywords(text.slice(pos), key++));
  }

  return parts;
}

function highlightKeywords(text: string, keyBase: number): React.ReactNode {
  const parts: React.ReactNode[] = [];
  let last = 0;
  KEYWORDS.lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = KEYWORDS.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    parts.push(
      <span key={keyBase + "-" + m.index} style={{ color: "var(--ac-accent)" }}>
        {m[0]}
      </span>,
    );
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts.length === 1 ? parts[0] : <>{parts}</>;
}

// ══════════════════════════════════════════════════════════════
// Line type color map
// ══════════════════════════════════════════════════════════════

const LINE_COLORS: Record<LogLineType, string> = {
  stdout:    "var(--ac-fg0)",
  stderr:    "var(--ac-warning)",
  system:    "var(--ac-fg2)",
  error:     "var(--ac-danger)",
  info:      "var(--ac-info)",
  code:      "#a5f3fc",
  separator: "var(--ac-fg3)",
};

// ══════════════════════════════════════════════════════════════
// Parse raw log text into LogLine[]
// ══════════════════════════════════════════════════════════════

function parseLogLines(content: string): LogLine[] {
  const raw = content.split("\n");
  const lines: LogLine[] = [];
  let lineNo = 0;

  for (const text of raw) {
    lineNo++;
    let type: LogLineType = "stdout";
    let sectionStart = false;
    let sectionTitle: string | undefined;

    if (text.startsWith(">>> ") || text.startsWith("$ ")) {
      type = "code";
      sectionStart = true;
      sectionTitle = text.slice(0, 60);
    } else if (text.startsWith("[ERROR]") || text.startsWith("Error:") || text.includes("Traceback")) {
      type = "error";
    } else if (text.startsWith("[WARN]")) {
      type = "stderr";
    } else if (text.startsWith("[INFO]") || text.startsWith("[OK]")) {
      type = "info";
    } else if (text.startsWith("---") || text.startsWith("===")) {
      type = "separator";
    } else if (text.startsWith("#") && text.length > 1 && text[1] !== " ") {
      type = "system";
    }

    lines.push({
      id: `line-${lineNo}`,
      lineNo,
      text,
      type,
      sectionStart,
      sectionTitle,
    });
  }

  return lines;
}

// ══════════════════════════════════════════════════════════════
// SandboxLogViewer component
// ══════════════════════════════════════════════════════════════

export const SandboxLogViewer: React.FC<SandboxLogViewerProps> = ({
  content,
  height = 400,
  autoScroll = true,
  searchQuery = "",
  ariaLabel = "Sandbox execution log",
  onLineCopy,
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [collapsedSections, setCollapsedSections] = useState<Set<number>>(new Set());
  const [copiedLineId, setCopiedLineId] = useState<string | null>(null);

  const allLines = useMemo(() => parseLogLines(content), [content]);

  // ── Collapse logic ─────────────────────────────────────────
  const toggleSection = useCallback(
    (lineIndex: number) => {
      setCollapsedSections((prev) => {
        const next = new Set(prev);
        if (next.has(lineIndex)) next.delete(lineIndex);
        else next.add(lineIndex);
        return next;
      });
    },
    [],
  );

  // ── Filter and collapse ────────────────────────────────────
  const visibleLines = useMemo(() => {
    const result: LogLine[] = [];
    let skipUntilSectionEnd = false;


    for (let i = 0; i < allLines.length; i++) {
      const line = allLines[i];

      // If in a collapsed section, skip until next section of same or higher level
      if (skipUntilSectionEnd) {
        if (line.sectionStart) {
          skipUntilSectionEnd = false;
        } else {
          continue;
        }
      }

      // Check if this section is collapsed
      if (collapsedSections.has(i)) {
        skipUntilSectionEnd = true;
        // Still show the section header
        result.push(line);
        continue;
      }

      // Apply search filter
      if (searchQuery && !line.text.toLowerCase().includes(searchQuery.toLowerCase())) {
        continue;
      }

      result.push(line);
    }

    return result;
  }, [allLines, collapsedSections, searchQuery]);

  // ── Auto-scroll ────────────────────────────────────────────
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [content, autoScroll]);

  // ── Copy handler ───────────────────────────────────────────
  const handleCopyLine = useCallback(
    (line: LogLine) => {
      navigator.clipboard?.writeText(line.text).catch(() => {});
      setCopiedLineId(line.id);
      setTimeout(() => setCopiedLineId(null), 1500);
      onLineCopy?.(line);
    },
    [onLineCopy],
  );

  // ── Search match highlighting ──────────────────────────────
  const highlightSearch = useCallback(
    (text: string): React.ReactNode => {
      if (!searchQuery) return text;
      const idx = text.toLowerCase().indexOf(searchQuery.toLowerCase());
      if (idx === -1) return text;
      return (
        <>
          {text.slice(0, idx)}
          <mark style={{ backgroundColor: "var(--ac-highlight)", color: "var(--ac-fg0)" }}>
            {text.slice(idx, idx + searchQuery.length)}
          </mark>
          {text.slice(idx + searchQuery.length)}
        </>
      );
    },
    [searchQuery],
  );

  // ── Render ─────────────────────────────────────────────────

  return (
    <div
      ref={scrollRef}
      role="log"
      aria-label={ariaLabel}
      aria-live="polite"
      aria-relevant="additions"
      style={{
        height,
        overflowY: "auto",
        backgroundColor: "var(--ac-bg0)",
        border: "1px solid var(--ac-border0)",
        borderRadius: "var(--ac-radius-md)",
        fontFamily: "var(--ac-font-mono)",
        fontSize: "var(--ac-text-sm)",
        lineHeight: 1.6,
        color: "var(--ac-fg0)",
      }}
    >
      {visibleLines.map((line, vi) => {
        const isSection = line.sectionStart;
        const isCollapsed = collapsedSections.has(vi);

        return (
          <div
            key={line.id}
            role="row"
            aria-expanded={isSection ? !isCollapsed : undefined}
            style={{
              display: "flex",
              minHeight: 20,
              backgroundColor: line.type === "error"
                ? "rgba(239,68,68,0.08)"
                : line.type === "code"
                  ? "var(--ac-bg1)"
                  : "transparent",
              borderBottom: line.type === "separator" ? "1px solid var(--ac-border0)" : "none",
            }}
          >
            {/* Line number gutter */}
            <div
              role="cell"
              style={{
                width: 48,
                minWidth: 48,
                textAlign: "right",
                paddingRight: "var(--ac-space-xs)",
                color: "var(--ac-fg3)",
                userSelect: "none",
                cursor: isSection ? "pointer" : "default",
                backgroundColor: isSection ? "var(--ac-bg2)" : "transparent",
                fontWeight: isSection ? 600 : 400,
              }}
              onClick={() => isSection && toggleSection(vi)}
              title={isSection ? (isCollapsed ? "Expand section" : "Collapse section") : undefined}
            >
              {isSection ? (isCollapsed ? "\u25B6" : "\u25BC") : line.lineNo}
            </div>

            {/* Content */}
            <div
              role="cell"
              style={{
                flex: 1,
                padding: "0 var(--ac-space-xs)",
                color: LINE_COLORS[line.type],
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "pre-wrap",
                wordBreak: "break-all",
              }}
            >
              {line.type === "code" ? highlightSyntax(line.text) : highlightSearch(line.text)}
            </div>

            {/* Copy button (on hover, shown via CSS) */}
            <div
              role="button"
              aria-label={`Copy line ${line.lineNo}`}
              tabIndex={0}
              onClick={() => handleCopyLine(line)}
              onKeyDown={(e) => e.key === "Enter" && handleCopyLine(line)}
              style={{
                width: 24,
                minWidth: 24,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: copiedLineId === line.id ? "var(--ac-success)" : "var(--ac-fg3)",
                cursor: "pointer",
                fontSize: "var(--ac-text-xs)",
                opacity: 0.6,
              }}
            >
              {copiedId(line.id, copiedLineId)}
            </div>
          </div>
        );
      })}

      {visibleLines.length === 0 && (
        <div style={{ padding: "var(--ac-space-lg)", color: "var(--ac-fg3)", textAlign: "center" }}>
          {searchQuery ? "No matching log lines" : "No log output"}
        </div>
      )}
    </div>
  );
};

function copiedId(lineId: string, copiedLineId: string | null): string {
  return copiedLineId === lineId ? "\u2713" : "\u2398";
}
