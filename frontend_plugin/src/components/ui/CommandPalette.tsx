/**
 * @file components/ui/CommandPalette.tsx
 * @brief Mac Spotlight-style global command palette.
 *
 * Features:
 *  - Fuzzy search across registered commands
 *  - Keyboard navigation (arrows, Enter, Escape)
 *  - Recent commands history
 *  - Command categories with icons
 *  - ARIA combobox pattern
 *  - Backdrop overlay with click-outside-to-close
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

export interface Command {
  /** Unique command ID */
  id: string;
  /** Display label */
  label: string;
  /** Optional description */
  description?: string;
  /** Category for grouping */
  category?: string;
  /** Icon character or emoji */
  icon?: string;
  /** Keyboard shortcut display text */
  shortcut?: string;
  /** Whether this command is currently available */
  enabled?: boolean;
  /** Action to execute */
  action: () => void;
}

export interface CommandPaletteProps {
  /** All registered commands */
  commands: Command[];
  /** Whether the palette is open */
  isOpen: boolean;
  /** Close handler */
  onClose: () => void;
  /** ARIA label */
  ariaLabel?: string;
  /** Max visible results (default 10) */
  maxResults?: number;
}

// ══════════════════════════════════════════════════════════════
// Fuzzy match
// ══════════════════════════════════════════════════════════════

interface FuzzyMatchResult {
  score: number;
  matches: number[]; // matched char indices
}

function fuzzyMatch(query: string, target: string): FuzzyMatchResult | null {
  if (!query) return { score: 0, matches: [] };

  const q = query.toLowerCase();
  const t = target.toLowerCase();
  let qi = 0;
  let score = 0;
  let lastMatch = -2;
  const matches: number[] = [];

  for (let ti = 0; ti < t.length && qi < q.length; ti++) {
    if (t[ti] === q[qi]) {
      matches.push(ti);
      // Consecutive match bonus
      score += ti === lastMatch + 1 ? 10 : 1;
      // Start-of-word bonus
      if (ti === 0 || t[ti - 1] === " " || t[ti - 1] === "_") score += 5;
      lastMatch = ti;
      qi++;
    }
  }

  if (qi < q.length) return null; // not all chars matched
  return { score, matches };
}

function highlightMatches(text: string, matches: number[]): React.ReactNode {
  if (matches.length === 0) return text;
  const parts: React.ReactNode[] = [];
  let mi = 0;
  for (let i = 0; i < text.length; i++) {
    if (mi < matches.length && matches[mi] === i) {
      parts.push(
        <span key={i} style={{ color: "var(--ac-accent)", fontWeight: 600 }}>
          {text[i]}
        </span>,
      );
      mi++;
    } else {
      parts.push(text[i]);
    }
  }
  return <>{parts}</>;
}

// ══════════════════════════════════════════════════════════════
// Recent commands (localStorage)
// ══════════════════════════════════════════════════════════════

const STORAGE_KEY = "ac-command-palette-recent";
const MAX_RECENT = 5;

function getRecentIds(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}

function pushRecentId(id: string): void {
  const ids = getRecentIds().filter((x) => x !== id);
  ids.unshift(id);
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(ids.slice(0, MAX_RECENT)));
  } catch { /* quota */ }
}

// ══════════════════════════════════════════════════════════════
// CommandPalette component
// ══════════════════════════════════════════════════════════════

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  commands,
  isOpen,
  onClose,
  ariaLabel = "Command palette",
  maxResults = 10,
}) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [recentIds] = useState(getRecentIds);

  // ── Focus input on open ────────────────────────────────────
  useEffect(() => {
    if (isOpen) {
      setQuery("");
      setSelectedIndex(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [isOpen]);

  // ── Filtered and scored results ────────────────────────────
  const results = useMemo(() => {
    const enabled = commands.filter((c) => c.enabled !== false);

    if (!query.trim()) {
      // Show recent commands first, then all
      const recent = recentIds
        .map((id) => enabled.find((c) => c.id === id))
        .filter(Boolean) as Command[];
      const rest = enabled.filter((c) => !recentIds.includes(c.id));
      return [...recent, ...rest].slice(0, maxResults);
    }

    // Fuzzy match
    const scored: Array<{ command: Command; score: number; matches: number[] }> = [];
    for (const cmd of enabled) {
      const labelMatch = fuzzyMatch(query, cmd.label);
      const descMatch = cmd.description ? fuzzyMatch(query, cmd.description) : null;
      const catMatch = cmd.category ? fuzzyMatch(query, cmd.category) : null;

      const bestMatch = [labelMatch, descMatch, catMatch]
        .filter(Boolean)
        .sort((a, b) => b!.score - a!.score)[0];

      if (bestMatch) {
        scored.push({
          command: cmd,
          score: bestMatch.score + (labelMatch?.score ?? 0) * 2,
          matches: labelMatch?.matches ?? [],
        });
      }
    }

    scored.sort((a, b) => b.score - a.score);
    return scored.slice(0, maxResults).map((s) => s.command);
  }, [commands, query, recentIds, maxResults]);

  // Get matches for highlighting
  const getMatches = useCallback(
    (cmd: Command): number[] => {
      if (!query.trim()) return [];
      return fuzzyMatch(query, cmd.label)?.matches ?? [];
    },
    [query],
  );

  // ── Execute command ────────────────────────────────────────
  const executeCommand = useCallback(
    (cmd: Command) => {
      pushRecentId(cmd.id);
      onClose();
      cmd.action();
    },
    [onClose],
  );

  // ── Keyboard navigation ────────────────────────────────────
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      switch (e.key) {
        case "ArrowDown":
          e.preventDefault();
          setSelectedIndex((prev) => Math.min(prev + 1, results.length - 1));
          break;
        case "ArrowUp":
          e.preventDefault();
          setSelectedIndex((prev) => Math.max(prev - 1, 0));
          break;
        case "Enter":
          e.preventDefault();
          if (results[selectedIndex]) executeCommand(results[selectedIndex]);
          break;
        case "Escape":
          e.preventDefault();
          onClose();
          break;
        case "Tab":
          e.preventDefault();
          if (e.shiftKey) {
            setSelectedIndex((prev) => Math.max(prev - 1, 0));
          } else {
            setSelectedIndex((prev) => Math.min(prev + 1, results.length - 1));
          }
          break;
      }
    },
    [results, selectedIndex, executeCommand, onClose],
  );

  // ── Scroll selected into view ──────────────────────────────
  useEffect(() => {
    const list = listRef.current;
    if (!list) return;
    const items = list.querySelectorAll('[role="option"]');
    items[selectedIndex]?.scrollIntoView({ block: "nearest" });
  }, [selectedIndex]);

  // ── Reset index on query change ────────────────────────────
  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  // ── Group by category ──────────────────────────────────────
  const grouped = useMemo(() => {
    const groups = new Map<string, Command[]>();
    for (const cmd of results) {
      const cat = cmd.category ?? "";
      if (!groups.has(cat)) groups.set(cat, []);
      groups.get(cat)!.push(cmd);
    }
    return groups;
  }, [results]);

  // ── Render ─────────────────────────────────────────────────

  if (!isOpen) return null;

  let globalIndex = -1;

  return (
    <>
      {/* Backdrop */}
      <div
        role="presentation"
        onClick={onClose}
        style={{
          position: "fixed",
          inset: 0,
          backgroundColor: "rgba(0,0,0,0.5)",
          zIndex: 9998,
        }}
      />

      {/* Palette */}
      <div
        role="dialog"
        aria-label={ariaLabel}
        aria-modal="true"
        style={{
          position: "fixed",
          top: "20%",
          left: "50%",
          transform: "translateX(-50%)",
          width: 520,
          maxHeight: 420,
          backgroundColor: "var(--ac-bg1)",
          border: "1px solid var(--ac-border1)",
          borderRadius: "var(--ac-radius-lg)",
          boxShadow: "0 16px 48px var(--ac-shadow)",
          zIndex: 9999,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          fontFamily: "var(--ac-font)",
        }}
      >
        {/* Input */}
        <div style={{ display: "flex", alignItems: "center", padding: "var(--ac-space-sm)", borderBottom: "1px solid var(--ac-border0)" }}>
          <span style={{ color: "var(--ac-fg3)", marginRight: "var(--ac-space-sm)", fontSize: "var(--ac-text-lg)" }}>
            {"\u2315"}
          </span>
          <input
            ref={inputRef}
            type="text"
            role="combobox"
            aria-expanded={true}
            aria-controls="command-list"
            aria-activedescendant={results[selectedIndex] ? `cmd-${results[selectedIndex].id}` : undefined}
            aria-label="Search commands"
            placeholder="Type a command..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            style={{
              flex: 1,
              background: "none",
              border: "none",
              outline: "none",
              color: "var(--ac-fg0)",
              fontSize: "var(--ac-text-lg)",
              fontFamily: "var(--ac-font)",
            }}
          />
          <span style={{ color: "var(--ac-fg3)", fontSize: "var(--ac-text-xs)", marginLeft: "var(--ac-space-sm)" }}>
            ESC
          </span>
        </div>

        {/* Results list */}
        <div
          ref={listRef}
          id="command-list"
          role="listbox"
          aria-label="Command results"
          style={{ overflowY: "auto", flex: 1, padding: "var(--ac-space-xs) 0" }}
        >
          {results.length === 0 ? (
            <div style={{ padding: "var(--ac-space-lg)", color: "var(--ac-fg3)", textAlign: "center" }}>
              No matching commands
            </div>
          ) : (
            Array.from(grouped.entries()).map(([category, cmds]) => (
              <div key={category}>
                {category && (
                  <div
                    role="presentation"
                    style={{
                      padding: "var(--ac-space-xs) var(--ac-space-md)",
                      fontSize: "var(--ac-text-xs)",
                      color: "var(--ac-fg3)",
                      fontWeight: 600,
                      textTransform: "uppercase",
                      letterSpacing: "0.05em",
                    }}
                  >
                    {category}
                  </div>
                )}
                {cmds.map((cmd) => {
                  globalIndex++;
                  const idx = globalIndex;
                  const isSelected = idx === selectedIndex;
                  return (
                    <div
                      key={cmd.id}
                      id={`cmd-${cmd.id}`}
                      role="option"
                      aria-selected={isSelected}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        padding: "var(--ac-space-xs) var(--ac-space-md)",
                        cursor: "pointer",
                        backgroundColor: isSelected ? "var(--ac-highlight)" : "transparent",
                        transition: "background-color var(--ac-transition-fast)",
                      }}
                      onClick={() => executeCommand(cmd)}
                      onMouseEnter={() => setSelectedIndex(idx)}
                    >
                      {/* Icon */}
                      <span style={{ width: 24, textAlign: "center", marginRight: "var(--ac-space-sm)", fontSize: "var(--ac-text-lg)" }}>
                        {cmd.icon ?? "\u2022"}
                      </span>

                      {/* Label + description */}
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ color: "var(--ac-fg0)", fontSize: "var(--ac-text-md)" }}>
                          {highlightMatches(cmd.label, getMatches(cmd))}
                        </div>
                        {cmd.description && (
                          <div style={{ color: "var(--ac-fg2)", fontSize: "var(--ac-text-xs)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                            {cmd.description}
                          </div>
                        )}
                      </div>

                      {/* Shortcut */}
                      {cmd.shortcut && (
                        <span style={{ color: "var(--ac-fg3)", fontSize: "var(--ac-text-xs)", marginLeft: "var(--ac-space-sm)" }}>
                          {cmd.shortcut}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            ))
          )}
        </div>
      </div>
    </>
  );
};

// ══════════════════════════════════════════════════════════════
// Hook: useCommandPalette
// ══════════════════════════════════════════════════════════════

export function useCommandPalette(_commands: Command[]) {
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setIsOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  return {
    isOpen,
    open: () => setIsOpen(true),
    close: () => setIsOpen(false),
    toggle: () => setIsOpen((prev) => !prev),
  };
}
