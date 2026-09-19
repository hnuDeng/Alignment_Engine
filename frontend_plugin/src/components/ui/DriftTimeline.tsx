/**
 * @file components/ui/DriftTimeline.tsx
 * @brief Drift dynamic timeline -- visualizes drift events over time.
 *
 * Features:
 *  - Horizontal timeline with severity-coded event markers
 *  - Zoom/pan via mouse wheel and drag
 *  - Click-to-select event detail popover
 *  - Animated entry with CSS transitions
 *  - ARIA timeline roles
 *
 * No external dependencies.
 */

import React, {
  useCallback,
  useMemo,
  useRef,
  useState,
} from "react";
import type { DriftReport, DriftSeverity } from "../../types";

// ══════════════════════════════════════════════════════════════
// Types
// ══════════════════════════════════════════════════════════════

export interface TimelineEvent {
  id: string;
  timestamp: number;
  report: DriftReport;
  severity: DriftSeverity;
  sampleCount: number;
}

export interface DriftTimelineProps {
  /** Drift reports to display */
  reports: DriftReport[];
  /** Currently selected event ID */
  selectedEventId?: string | null;
  /** Event click handler */
  onEventClick?: (reportId: string) => void;
  /** Container height (default 200) */
  height?: number;
  /** ARIA label */
  ariaLabel?: string;
}

// ══════════════════════════════════════════════════════════════
// Constants
// ══════════════════════════════════════════════════════════════

const SEVERITY_COLORS: Record<DriftSeverity, string> = {
  critical: "var(--ac-danger)",
  high:     "#ea580c",
  medium:   "var(--ac-warning)",
  low:      "var(--ac-info)",
};

const SEVERITY_SIZES: Record<DriftSeverity, number> = {
  critical: 14,
  high:     12,
  medium:   10,
  low:      8,
};

const MIN_ZOOM = 0.5;
const MAX_ZOOM = 10;

// ══════════════════════════════════════════════════════════════
// Helpers
// ══════════════════════════════════════════════════════════════

function inferSeverity(report: DriftReport): DriftSeverity {
  let max = "low" as DriftSeverity;
  const order: Record<string, number> = { low: 1, medium: 2, high: 3, critical: 4 };
  for (const s of report.samples) {
    if ((order[s.severity] ?? 0) > (order[max] ?? 0)) max = s.severity;
  }
  return max;
}

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString();
}

function formatDate(ts: number): string {
  return new Date(ts).toLocaleDateString();
}

// ══════════════════════════════════════════════════════════════
// DriftTimeline component
// ══════════════════════════════════════════════════════════════

export const DriftTimeline: React.FC<DriftTimelineProps> = ({
  reports,
  selectedEventId,
  onEventClick,
  height = 200,
  ariaLabel = "Drift event timeline",
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState(1);
  const [panX, setPanX] = useState(0);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const dragRef = useRef<{ startX: number; startPan: number } | null>(null);

  // ── Build timeline events ──────────────────────────────────
  const events: TimelineEvent[] = useMemo(
    () =>
      reports
        .map((r) => ({
          id: r.reportId,
          timestamp: new Date(r.timestamp).getTime(),
          report: r,
          severity: inferSeverity(r),
          sampleCount: r.samples.length,
        }))
        .sort((a, b) => a.timestamp - b.timestamp),
    [reports],
  );

  const timeRange = useMemo(() => {
    if (events.length === 0) return { min: 0, max: 1 };
    return {
      min: events[0].timestamp,
      max: events[events.length - 1].timestamp,
    };
  }, [events]);

  const timeSpan = timeRange.max - timeRange.min || 1;

  // ── Event position calculation ─────────────────────────────
  const getEventX = useCallback(
    (ts: number): number => {
      const ratio = (ts - timeRange.min) / timeSpan;
      return ratio * (containerRef.current?.clientWidth ?? 800) * zoom + panX;
    },
    [timeRange, timeSpan, zoom, panX],
  );

  // ── Wheel zoom ─────────────────────────────────────────────
  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
      e.preventDefault();
      const delta = e.deltaY > 0 ? 0.9 : 1.1;
      setZoom((prev) => Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, prev * delta)));
    },
    [],
  );

  // ── Drag pan ───────────────────────────────────────────────
  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (e.button !== 0) return;
      dragRef.current = { startX: e.clientX, startPan: panX };
    },
    [panX],
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!dragRef.current) return;
      const diff = e.clientX - dragRef.current.startX;
      setPanX(dragRef.current.startPan + diff);
    },
    [],
  );

  const handleMouseUp = useCallback(() => {
    dragRef.current = null;
  }, []);

  // ── Keyboard navigation ────────────────────────────────────
  const [focusIndex, setFocusIndex] = useState(-1);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "ArrowRight") {
        e.preventDefault();
        setFocusIndex((prev) => Math.min(prev + 1, events.length - 1));
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        setFocusIndex((prev) => Math.max(prev - 1, 0));
      } else if (e.key === "Enter" && focusIndex >= 0) {
        onEventClick?.(events[focusIndex].id);
      }
    },
    [events, focusIndex, onEventClick],
  );

  // ── Render ─────────────────────────────────────────────────

  return (
    <div
      ref={containerRef}
      role="list"
      aria-label={ariaLabel}
      aria-roledescription="timeline"
      tabIndex={0}
      onKeyDown={handleKeyDown}
      onWheel={handleWheel}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      style={{
        position: "relative",
        height,
        overflow: "hidden",
        backgroundColor: "var(--ac-bg0)",
        border: "1px solid var(--ac-border0)",
        borderRadius: "var(--ac-radius-md)",
        fontFamily: "var(--ac-font)",
        cursor: dragRef.current ? "grabbing" : "grab",
        userSelect: "none",
      }}
    >
      {/* ── Axis line ── */}
      <div
        style={{
          position: "absolute",
          top: height / 2,
          left: 0,
          right: 0,
          height: 1,
          backgroundColor: "var(--ac-border1)",
        }}
      />

      {/* ── Tick marks ── */}
      {events.map((ev) => {
        const x = getEventX(ev.timestamp);
        if (x < -20 || x > (containerRef.current?.clientWidth ?? 800) + 20) return null;
        return (
          <div key={ev.id} style={{ position: "absolute", left: x, top: 0, bottom: 0 }}>
            {/* Tick line */}
            <div
              style={{
                position: "absolute",
                top: height / 2 - 20,
                width: 1,
                height: 40,
                backgroundColor: "var(--ac-border1)",
              }}
            />
          </div>
        );
      })}

      {/* ── Event markers ── */}
      {events.map((ev, i) => {
        const x = getEventX(ev.timestamp);
        if (x < -20 || x > (containerRef.current?.clientWidth ?? 800) + 20) return null;

        const isAbove = i % 2 === 0;
        const size = SEVERITY_SIZES[ev.severity];
        const color = SEVERITY_COLORS[ev.severity];
        const isSelected = ev.id === selectedEventId;
        const isHovered = ev.id === hoveredId;
        const isFocused = i === focusIndex;

        return (
          <div
            key={ev.id}
            role="listitem"
            aria-label={`${ev.severity} drift event at ${formatTime(ev.timestamp)} with ${ev.sampleCount} samples`}
            aria-selected={isSelected}
            tabIndex={isFocused ? 0 : -1}
            style={{
              position: "absolute",
              left: x - size / 2,
              top: isAbove ? height / 2 - 30 - size : height / 2 + 30,
              width: size,
              height: size,
              borderRadius: "var(--ac-radius-full)",
              backgroundColor: color,
              border: isSelected ? "2px solid var(--ac-fg0)" : "none",
              transform: isHovered ? "scale(1.4)" : "scale(1)",
              transition: "transform var(--ac-transition-fast)",
              cursor: "pointer",
              boxShadow: isHovered ? `0 0 8px ${color}` : "none",
            }}
            onClick={(e) => {
              e.stopPropagation();
              onEventClick?.(ev.id);
            }}
            onMouseEnter={() => setHoveredId(ev.id)}
            onMouseLeave={() => setHoveredId(null)}
          />
        );
      })}

      {/* ── Hover tooltip ── */}
      {hoveredId && (() => {
        const ev = events.find((e) => e.id === hoveredId);
        if (!ev) return null;
        const x = getEventX(ev.timestamp);
        return (
          <div
            role="tooltip"
            style={{
              position: "absolute",
              left: Math.min(x, (containerRef.current?.clientWidth ?? 800) - 180),
              top: 8,
              padding: "var(--ac-space-xs) var(--ac-space-sm)",
              backgroundColor: "var(--ac-bg2)",
              border: "1px solid var(--ac-border1)",
              borderRadius: "var(--ac-radius-sm)",
              color: "var(--ac-fg0)",
              fontSize: "var(--ac-text-xs)",
              pointerEvents: "none",
              zIndex: 10,
              whiteSpace: "nowrap",
            }}
          >
            <div style={{ color: SEVERITY_COLORS[ev.severity], fontWeight: 600 }}>
              {ev.severity.toUpperCase()}
            </div>
            <div>{formatTime(ev.timestamp)}</div>
            <div>{ev.sampleCount} samples</div>
          </div>
        );
      })()}

      {/* ── Time axis labels ── */}
      <div
        style={{
          position: "absolute",
          bottom: 4,
          left: 8,
          right: 8,
          display: "flex",
          justifyContent: "space-between",
          color: "var(--ac-fg3)",
          fontSize: "var(--ac-text-xs)",
        }}
      >
        <span>{formatDate(timeRange.min)}</span>
        <span>{formatDate(timeRange.max)}</span>
      </div>
    </div>
  );
};
