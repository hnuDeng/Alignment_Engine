/**
 * @file components/ui/VirtualTable.tsx
 * @brief Virtualized table for 100k+ row drift diagnostic reports.
 *
 * Features:
 *  - Only renders visible rows (virtual DOM window)
 *  - Column sorting (click header)
 *  - Drag-to-resize column widths
 *  - Smooth scroll with overscan buffer
 *  - ARIA table roles and keyboard navigation
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

export interface TableColumn<T = Record<string, unknown>> {
  /** Unique column key */
  key: string;
  /** Display header label */
  label: string;
  /** Fixed pixel width (default 150) */
  width?: number;
  /** Minimum pixel width (default 60) */
  minWidth?: number;
  /** Whether this column is sortable (default true) */
  sortable?: boolean;
  /** Whether this column is resizable (default true) */
  resizable?: boolean;
  /** Custom cell renderer */
  render?: (value: unknown, row: T, rowIndex: number) => React.ReactNode;
  /** Value extractor for sorting */
  accessor?: (row: T) => string | number;
  /** Text alignment */
  align?: "left" | "center" | "right";
}

export type SortDirection = "asc" | "desc" | null;

export interface SortState {
  columnKey: string;
  direction: SortDirection;
}

export interface VirtualTableProps<T = Record<string, unknown>> {
  /** Column definitions */
  columns: TableColumn<T>[];
  /** Full dataset (can be 100k+ rows) */
  data: T[];
  /** Row height in pixels (default 36) */
  rowHeight?: number;
  /** Header height in pixels (default 40) */
  headerHeight?: number;
  /** Number of extra rows to render above/below viewport (default 5) */
  overscan?: number;
  /** Table height (default 600) */
  height?: number;
  /** Unique key extractor for rows */
  rowKey: (row: T, index: number) => string;
  /** Row click handler */
  onRowClick?: (row: T, index: number) => void;
  /** Row double-click handler */
  onRowDoubleClick?: (row: T, index: number) => void;
  /** Currently selected row keys */
  selectedKeys?: Set<string>;
  /** ARIA label */
  ariaLabel?: string;
  /** Custom row className */
  rowClassName?: (row: T, index: number) => string;
  /** Enable IntersectionObserver-based row recycling for off-screen DOM nodes. */
  enableRowRecycling?: boolean;
  /** Called when row visibility changes; receives visible and recycled row key sets. */
  onRowVisibilityChange?: (visibleKeys: Set<string>, recycledKeys: Set<string>) => void;
  /** Threshold for IntersectionObserver (0-1). Default 0. */
  intersectionThreshold?: number;
}

// ══════════════════════════════════════════════════════════════
// useIntersectionRowRecycling -- IntersectionObserver-based row recycling hook
//
// Tracks which row DOM elements are visible in the viewport. Rows that scroll
// completely out of view are marked as 'recycled' so the parent can skip
// rendering expensive cell content for them.
//
// Time:  O(V) observer setup per render batch, O(1) per intersection callback
// Space: O(V) for the Set<string> of visible/recycled keys
// ══════════════════════════════════════════════════════════════

function useIntersectionRowRecycling(
  containerRef: React.RefObject<HTMLDivElement | null>,
  enabled: boolean,
  threshold: number,
): {
  visibleKeys: Set<string>;
  recycledKeys: Set<string>;
  observeRow: (element: HTMLElement | null, key: string) => void;
} {
  const visibleRef = useRef<Set<string>>(new Set());
  const recycledRef = useRef<Set<string>>(new Set());
  const [, forceUpdate] = useState(0);
  const observerRef = useRef<IntersectionObserver | null>(null);
  const elementMapRef = useRef<Map<string, HTMLElement>>(new Map());

  // Create / destroy the observer
  useEffect(() => {
    if (!enabled) return;

    const observer = new IntersectionObserver(
      (entries: IntersectionObserverEntry[]) => {
        let changed = false;
        for (const entry of entries) {
          const key = (entry.target as HTMLElement).dataset.rowKey;
          if (!key) continue;

          if (entry.isIntersecting) {
            // Row entered viewport: mark visible, unmark recycled
            if (!visibleRef.current.has(key)) {
              visibleRef.current.add(key);
              recycledRef.current.delete(key);
              changed = true;
            }
          } else {
            // Row left viewport: mark recycled, unmark visible
            if (visibleRef.current.has(key)) {
              visibleRef.current.delete(key);
              recycledRef.current.add(key);
              changed = true;
            }
          }
        }
        if (changed) forceUpdate((c) => c + 1);
      },
      {
        root: containerRef.current,
        threshold,
        rootMargin: "0px"},
    );
    observerRef.current = observer;

    // Re-observe all previously tracked elements
    for (const el of elementMapRef.current.values()) {
      observer.observe(el);
    }

    return () => {
      observer.disconnect();
      observerRef.current = null;
    };
  }, [enabled, threshold, containerRef]);

  // Cleanup stale elements on each render
  useEffect(() => {
    if (!enabled) return;
    // Remove elements that are no longer in the DOM
    const observer = observerRef.current;
    if (!observer) return;
    for (const [key, el] of elementMapRef.current.entries()) {
      if (!el.isConnected) {
        observer.unobserve(el);
        elementMapRef.current.delete(key);
        visibleRef.current.delete(key);
        recycledRef.current.delete(key);
      }
    }
  });

  // Observe a row element (called from the row render)
  const observeRow = useCallback((element: HTMLElement | null, key: string) => {
    if (!enabled || !element) return;
    const observer = observerRef.current;
    if (!observer) return;

    // Set data attribute for the observer callback
    element.dataset.rowKey = key;

    // Only observe new elements
    if (!elementMapRef.current.has(key)) {
      elementMapRef.current.set(key, element);
      observer.observe(element);
      // New rows start as visible until proven otherwise
      visibleRef.current.add(key);
    }
  }, [enabled]);

  return {
    visibleKeys: visibleRef.current,
    recycledKeys: recycledRef.current,
    observeRow,
  };
}

// ══════════════════════════════════════════════════════════════
// Style constants
// ══════════════════════════════════════════════════════════════

const CONTAINER_STYLE: React.CSSProperties = {
  position: "relative",
  overflow: "auto",
  backgroundColor: "var(--ac-bg0)",
  border: "1px solid var(--ac-border0)",
  borderRadius: "var(--ac-radius-md)",
  fontFamily: "var(--ac-font)",
  fontSize: "var(--ac-text-md)",
  color: "var(--ac-fg0)",
};

const HEADER_STYLE: React.CSSProperties = {
  display: "flex",
  position: "sticky",
  top: 0,
  zIndex: 2,
  backgroundColor: "var(--ac-bg1)",
  borderBottom: "1px solid var(--ac-border1)",
  userSelect: "none",
};

const ROW_STYLE: React.CSSProperties = {
  display: "flex",
  borderBottom: "1px solid var(--ac-border0)",
  cursor: "pointer",
  transition: "background-color var(--ac-transition-fast)",
};

const CELL_STYLE: React.CSSProperties = {
  padding: "0 var(--ac-space-sm)",
  display: "flex",
  alignItems: "center",
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};

const RESIZE_HANDLE_STYLE: React.CSSProperties = {
  position: "absolute",
  right: 0,
  top: 0,
  bottom: 0,
  width: "4px",
  cursor: "col-resize",
  zIndex: 1,
};

// ══════════════════════════════════════════════════════════════
// VirtualTable component
// ══════════════════════════════════════════════════════════════

export function VirtualTable<T = Record<string, unknown>>({
  columns: initialColumns,
  data,
  rowHeight = 36,
  headerHeight = 40,
  overscan = 5,
  height = 600,
  rowKey,
  onRowClick,
  onRowDoubleClick,
  selectedKeys,
  ariaLabel = "Virtual data table",
  enableRowRecycling = false,
  onRowVisibilityChange,
  intersectionThreshold = 0,
}: VirtualTableProps<T>) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [sort, setSort] = useState<SortState>({ columnKey: "", direction: null });
  const [columnWidths, setColumnWidths] = useState<Record<string, number>>(() => {
    const w: Record<string, number> = {};
    for (const col of initialColumns) w[col.key] = col.width ?? 150;
    return w;
  });
  const [focusedRow, setFocusedRow] = useState(-1);

  // ── IntersectionObserver row recycling ─────────────────────
  const { visibleKeys, recycledKeys, observeRow } = useIntersectionRowRecycling(
    containerRef as React.RefObject<HTMLDivElement | null>,
    enableRowRecycling,
    intersectionThreshold,
  );

  // Notify parent of visibility changes
  useEffect(() => {
    if (enableRowRecycling && onRowVisibilityChange) {
      onRowVisibilityChange(visibleKeys, recycledKeys);
    }
  }, [visibleKeys, recycledKeys, enableRowRecycling, onRowVisibilityChange]);

  // ── Column resize state ────────────────────────────────────
  const resizeRef = useRef<{
    columnKey: string;
    startX: number;
    startWidth: number;
  } | null>(null);

  // ── Sorted data ────────────────────────────────────────────
  const sortedData = useMemo(() => {
    if (!sort.direction || !sort.columnKey) return data;
    const col = initialColumns.find((c) => c.key === sort.columnKey);
    if (!col) return data;

    const sorted = [...data];
    const dir = sort.direction === "asc" ? 1 : -1;
    const accessor = col.accessor ?? ((row: T) => (row as Record<string, unknown>)[col.key] as string | number);

    sorted.sort((a, b) => {
      const va = accessor(a);
      const vb = accessor(b);
      if (va < vb) return -1 * dir;
      if (va > vb) return 1 * dir;
      return 0;
    });
    return sorted;
  }, [data, sort, initialColumns]);

  // ── Virtual window calculation ─────────────────────────────
  const totalHeight = sortedData.length * rowHeight;
  const containerHeight = height - headerHeight;
  const startIndex = Math.max(0, Math.floor(scrollTop / rowHeight) - overscan);
  const endIndex = Math.min(
    sortedData.length,
    Math.ceil((scrollTop + containerHeight) / rowHeight) + overscan,
  );
  const visibleRows = sortedData.slice(startIndex, endIndex);
  const offsetY = startIndex * rowHeight;

  // ── Scroll handler ─────────────────────────────────────────
  const handleScroll = useCallback(() => {
    if (containerRef.current) {
      setScrollTop(containerRef.current.scrollTop);
    }
  }, []);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    el.addEventListener("scroll", handleScroll, { passive: true });
    return () => el.removeEventListener("scroll", handleScroll);
  }, [handleScroll]);

  // ── Sort handler ───────────────────────────────────────────
  const handleSort = useCallback(
    (columnKey: string) => {
      setSort((prev) => {
        if (prev.columnKey !== columnKey) return { columnKey, direction: "asc" };
        if (prev.direction === "asc") return { columnKey, direction: "desc" };
        return { columnKey: "", direction: null };
      });
    },
    [],
  );

  // ── Column resize handlers ─────────────────────────────────
  const handleResizeStart = useCallback(
    (e: React.MouseEvent, columnKey: string) => {
      e.preventDefault();
      e.stopPropagation();
      resizeRef.current = {
        columnKey,
        startX: e.clientX,
        startWidth: columnWidths[columnKey] ?? 150,
      };

      const onMouseMove = (ev: MouseEvent) => {
        if (!resizeRef.current) return;
        const diff = ev.clientX - resizeRef.current.startX;
        const col = initialColumns.find((c) => c.key === resizeRef.current!.columnKey);
        const minW = col?.minWidth ?? 60;
        const newW = Math.max(minW, resizeRef.current.startWidth + diff);
        setColumnWidths((prev) => ({ ...prev, [resizeRef.current!.columnKey]: newW }));
      };

      const onMouseUp = () => {
        resizeRef.current = null;
        document.removeEventListener("mousemove", onMouseMove);
        document.removeEventListener("mouseup", onMouseUp);
      };

      document.addEventListener("mousemove", onMouseMove);
      document.addEventListener("mouseup", onMouseUp);
    },
    [columnWidths, initialColumns],
  );

  // ── Keyboard navigation ────────────────────────────────────
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setFocusedRow((prev) => Math.min(prev + 1, sortedData.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setFocusedRow((prev) => Math.max(prev - 1, 0));
      } else if (e.key === "Enter" && focusedRow >= 0) {
        onRowClick?.(sortedData[focusedRow], focusedRow);
      }
    },
    [sortedData, focusedRow, onRowClick],
  );

  // ── Total table width ──────────────────────────────────────
  const totalWidth = useMemo(
    () => Object.values(columnWidths).reduce((s, w) => s + w, 0),
    [columnWidths],
  );

  // ── Render ─────────────────────────────────────────────────

  return (
    <div
      ref={containerRef}
      role="grid"
      aria-label={ariaLabel}
      aria-rowcount={sortedData.length}
      aria-colcount={initialColumns.length}
      tabIndex={0}
      onKeyDown={handleKeyDown}
      style={{ ...CONTAINER_STYLE, height, overflowY: "auto" }}
    >
      {/* ── Header ── */}
      <div
        role="row"
        aria-rowindex={1}
        style={{ ...HEADER_STYLE, height: headerHeight, minWidth: totalWidth }}
      >
        {initialColumns.map((col) => {
          const w = columnWidths[col.key] ?? 150;
          const isSorted = sort.columnKey === col.key && sort.direction;
          return (
            <div
              key={col.key}
              role="columnheader"
              aria-sort={
                isSorted
                  ? sort.direction === "asc"
                    ? "ascending"
                    : "descending"
                  : "none"
              }
              style={{
                ...CELL_STYLE,
                width: w,
                height: headerHeight,
                position: "relative",
                cursor: col.sortable !== false ? "pointer" : "default",
                fontWeight: "var(--ac-weight-medium)",
                color: isSorted ? "var(--ac-accent)" : "var(--ac-fg1)",
                justifyContent: col.align === "right" ? "flex-end" : col.align === "center" ? "center" : "flex-start",
              }}
              onClick={() => col.sortable !== false && handleSort(col.key)}
            >
              <span>{col.label}</span>
              {isSorted && (
                <span style={{ marginLeft: 4, fontSize: 10 }}>
                  {sort.direction === "asc" ? "\u25B2" : "\u25BC"}
                </span>
              )}
              {col.resizable !== false && (
                <div
                  role="separator"
                  aria-orientation="vertical"
                  style={RESIZE_HANDLE_STYLE}
                  onMouseDown={(e) => handleResizeStart(e, col.key)}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* ── Virtual body ── */}
      <div
        role="rowgroup"
        style={{ position: "relative", height: totalHeight, minWidth: totalWidth }}
      >
        <div style={{ position: "absolute", top: offsetY, width: "100%" }}>
          {visibleRows.map((row, vi) => {
            const actualIndex = startIndex + vi;
            const key = rowKey(row, actualIndex);
            const isSelected = selectedKeys?.has(key) ?? false;
            const isFocused = actualIndex === focusedRow;
            return (
              <div
                key={key}
                role="row"
                aria-rowindex={actualIndex + 2}
                aria-selected={isSelected}
                tabIndex={isFocused ? 0 : -1}
                ref={(el) => observeRow(el, key)}
                data-row-key={key}
                style={{
                  ...ROW_STYLE,
                  height: rowHeight,
                  backgroundColor: isSelected
                    ? "var(--ac-highlight)"
                    : isFocused
                      ? "var(--ac-bg2)"
                      : actualIndex % 2 === 0
                        ? "var(--ac-bg0)"
                        : "var(--ac-bg1)",
                }}
                onClick={() => onRowClick?.(row, actualIndex)}
                onDoubleClick={() => onRowDoubleClick?.(row, actualIndex)}
                onMouseEnter={() => setFocusedRow(actualIndex)}
              >
                {/* When row is recycled (off-screen), render lightweight placeholder */} 
                {enableRowRecycling && recycledKeys.has(key) ? (
                  <div style={{ ...CELL_STYLE, width: totalWidth, height: rowHeight }} />
                ) : (
                  initialColumns.map((col) => {
                    const w = columnWidths[col.key] ?? 150;
                    const value = (row as Record<string, unknown>)[col.key];
                    return (
                      <div
                        key={col.key}
                        role="gridcell"
                        style={{
                          ...CELL_STYLE,
                          width: w,
                          height: rowHeight,
                          justifyContent: col.align === "right" ? "flex-end" : col.align === "center" ? "center" : "flex-start", 
                        }}
                        title={String(value ?? "")}
                      >
                        {col.render ? col.render(value, row, actualIndex) : String(value ?? "")}
                      </div>
                    );
                  })
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
