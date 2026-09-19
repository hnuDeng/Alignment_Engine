/**
 * @file components/ui/theme.ts
 * @brief CSS Variables-based theme engine -- FiftyOne dark mode style.
 *
 * Injects a <style> tag with CSS custom properties into document head.
 * Supports runtime toggle between "dark" and "light" modes.
 *
 * No external dependencies.
 */

// ══════════════════════════════════════════════════════════════
// Theme token interfaces
// ══════════════════════════════════════════════════════════════

export interface ColorTokens {
  bg0: string;      // deepest background (panels)
  bg1: string;      // elevated background (cards)
  bg2: string;      // interactive background (inputs)
  bg3: string;      // hover background
  border0: string;  // subtle border
  border1: string;  // active border
  fg0: string;      // primary text
  fg1: string;      // secondary text
  fg2: string;      // muted text
  fg3: string;      // disabled text
  accent: string;   // primary accent (blue)
  accentHover: string;
  danger: string;   // error / critical
  dangerHover: string;
  success: string;  // success / pass
  warning: string;  // warning / medium
  info: string;     // informational
  highlight: string; // selection highlight
  shadow: string;   // box-shadow color
}

export interface SpacingTokens {
  xxs: string;
  xs: string;
  sm: string;
  md: string;
  lg: string;
  xl: string;
  xxl: string;
}

export interface TypographyTokens {
  fontFamily: string;
  fontFamilyMono: string;
  fontSizeXs: string;
  fontSizeSm: string;
  fontSizeMd: string;
  fontSizeLg: string;
  fontSizeXl: string;
  fontWeightNormal: number;
  fontWeightMedium: number;
  fontWeightBold: number;
  lineHeight: number;
}

export interface RadiusTokens {
  sm: string;
  md: string;
  lg: string;
  full: string;
}

export interface TransitionTokens {
  fast: string;
  normal: string;
  slow: string;
}

export interface ThemeTokens {
  colors: ColorTokens;
  spacing: SpacingTokens;
  typography: TypographyTokens;
  radius: RadiusTokens;
  transition: TransitionTokens;
}

export type ThemeMode = "dark" | "light";

// ══════════════════════════════════════════════════════════════
// Dark theme (FiftyOne style)
// ══════════════════════════════════════════════════════════════

const DARK_COLORS: ColorTokens = {
  bg0:           "#020617",
  bg1:           "#0f172a",
  bg2:           "#1e293b",
  bg3:           "#334155",
  border0:       "#1e293b",
  border1:       "#334155",
  fg0:           "#e2e8f0",
  fg1:           "#94a3b8",
  fg2:           "#64748b",
  fg3:           "#475569",
  accent:        "#3b82f6",
  accentHover:   "#60a5fa",
  danger:        "#ef4444",
  dangerHover:   "#f87171",
  success:       "#22c55e",
  warning:       "#eab308",
  info:          "#38bdf8",
  highlight:     "rgba(59,130,246,0.15)",
  shadow:        "rgba(0,0,0,0.4)",
};

const LIGHT_COLORS: ColorTokens = {
  bg0:           "#ffffff",
  bg1:           "#f8fafc",
  bg2:           "#f1f5f9",
  bg3:           "#e2e8f0",
  border0:       "#e2e8f0",
  border1:       "#cbd5e1",
  fg0:           "#0f172a",
  fg1:           "#475569",
  fg2:           "#64748b",
  fg3:           "#94a3b8",
  accent:        "#2563eb",
  accentHover:   "#3b82f6",
  danger:        "#dc2626",
  dangerHover:   "#ef4444",
  success:       "#16a34a",
  warning:       "#ca8a04",
  info:          "#0284c7",
  highlight:     "rgba(37,99,235,0.1)",
  shadow:        "rgba(0,0,0,0.1)",
};

// ══════════════════════════════════════════════════════════════
// Shared tokens (not mode-dependent)
// ══════════════════════════════════════════════════════════════

const SPACING: SpacingTokens = {
  xxs: "2px",
  xs:  "4px",
  sm:  "8px",
  md:  "12px",
  lg:  "16px",
  xl:  "24px",
  xxl: "32px",
};

const TYPOGRAPHY: TypographyTokens = {
  fontFamily:     'system-ui, -apple-system, "Segoe UI", sans-serif',
  fontFamilyMono: 'Consolas, "Fira Code", "JetBrains Mono", monospace',
  fontSizeXs:     "11px",
  fontSizeSm:     "12px",
  fontSizeMd:     "13px",
  fontSizeLg:     "14px",
  fontSizeXl:     "16px",
  fontWeightNormal: 400,
  fontWeightMedium: 600,
  fontWeightBold:   700,
  lineHeight: 1.5,
};

const RADIUS: RadiusTokens = {
  sm:   "4px",
  md:   "6px",
  lg:   "8px",
  full: "9999px",
};

const TRANSITION: TransitionTokens = {
  fast:   "0.1s ease",
  normal: "0.15s ease",
  slow:   "0.3s ease",
};

// ══════════════════════════════════════════════════════════════
// Theme builder
// ══════════════════════════════════════════════════════════════

function buildTheme(mode: ThemeMode): ThemeTokens {
  return {
    colors: mode === "dark" ? DARK_COLORS : LIGHT_COLORS,
    spacing: SPACING,
    typography: TYPOGRAPHY,
    radius: RADIUS,
    transition: TRANSITION,
  };
}

// ══════════════════════════════════════════════════════════════
// CSS Variable injection
// ══════════════════════════════════════════════════════════════

const STYLE_TAG_ID = "agent-copilot-theme";

function buildCssVariables(theme: ThemeTokens): string {
  const c = theme.colors;
  const s = theme.spacing;
  const t = theme.typography;
  const r = theme.radius;
  const tr = theme.transition;

  return `
    :root {
      /* Colors */
      --ac-bg0: ${c.bg0};
      --ac-bg1: ${c.bg1};
      --ac-bg2: ${c.bg2};
      --ac-bg3: ${c.bg3};
      --ac-border0: ${c.border0};
      --ac-border1: ${c.border1};
      --ac-fg0: ${c.fg0};
      --ac-fg1: ${c.fg1};
      --ac-fg2: ${c.fg2};
      --ac-fg3: ${c.fg3};
      --ac-accent: ${c.accent};
      --ac-accent-hover: ${c.accentHover};
      --ac-danger: ${c.danger};
      --ac-danger-hover: ${c.dangerHover};
      --ac-success: ${c.success};
      --ac-warning: ${c.warning};
      --ac-info: ${c.info};
      --ac-highlight: ${c.highlight};
      --ac-shadow: ${c.shadow};

      /* Spacing */
      --ac-space-xxs: ${s.xxs};
      --ac-space-xs: ${s.xs};
      --ac-space-sm: ${s.sm};
      --ac-space-md: ${s.md};
      --ac-space-lg: ${s.lg};
      --ac-space-xl: ${s.xl};
      --ac-space-xxl: ${s.xxl};

      /* Typography */
      --ac-font: ${t.fontFamily};
      --ac-font-mono: ${t.fontFamilyMono};
      --ac-text-xs: ${t.fontSizeXs};
      --ac-text-sm: ${t.fontSizeSm};
      --ac-text-md: ${t.fontSizeMd};
      --ac-text-lg: ${t.fontSizeLg};
      --ac-text-xl: ${t.fontSizeXl};
      --ac-weight-normal: ${t.fontWeightNormal};
      --ac-weight-medium: ${t.fontWeightMedium};
      --ac-weight-bold: ${t.fontWeightBold};
      --ac-line-height: ${t.lineHeight};

      /* Radius */
      --ac-radius-sm: ${r.sm};
      --ac-radius-md: ${r.md};
      --ac-radius-lg: ${r.lg};
      --ac-radius-full: ${r.full};

      /* Transitions */
      --ac-transition-fast: ${tr.fast};
      --ac-transition-normal: ${tr.normal};
      --ac-transition-slow: ${tr.slow};
    }
  `;
}

/** Inject or update the theme <style> tag in document head. */
export function injectTheme(mode: ThemeMode): void {
  const theme = buildTheme(mode);
  const css = buildCssVariables(theme);

  let tag = document.getElementById(STYLE_TAG_ID) as HTMLStyleElement | null;
  if (!tag) {
    tag = document.createElement("style");
    tag.id = STYLE_TAG_ID;
    document.head.appendChild(tag);
  }
  tag.textContent = css;

  // Also set data attribute for CSS selectors
  document.documentElement.setAttribute("data-ac-theme", mode);
}

/** Read the current theme mode from the DOM. */
export function getCurrentTheme(): ThemeMode {
  return (document.documentElement.getAttribute("data-ac-theme") as ThemeMode) ?? "dark";
}

/** Toggle between dark and light. Returns the new mode. */
export function toggleTheme(): ThemeMode {
  const next = getCurrentTheme() === "dark" ? "light" : "dark";
  injectTheme(next);
  return next;
}

/** Get the raw theme token object (useful for JS-side styling). */
export function getThemeTokens(mode?: ThemeMode): ThemeTokens {
  return buildTheme(mode ?? getCurrentTheme());
}

// ══════════════════════════════════════════════════════════════
// Utility: CSS variable reference shorthand
// ══════════════════════════════════════════════════════════════

/** Returns `var(--ac-<name>)` for use in inline styles. */
export function cssVar(name: string): string {
  return `var(--ac-${name})`;
}

// Auto-inject dark theme on module load
if (typeof document !== "undefined") {
  injectTheme("dark");
}
