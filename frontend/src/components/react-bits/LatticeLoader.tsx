// Adapted from https://reactbits.dev/r/LatticeLoader-TS-TW.json (MIT + Commons Clause).
// Changes: the timer only shows an `elapsed` value the caller measured from real
// timestamps (no internal clock); copy comes from the caller (no built-in
// English); the loop pauses off screen and stands still at static motion via
// the app motion level instead of a media query.
import React, { type CSSProperties } from "react";
import { useMotionBudget } from "../../motion";

export type LatticeStatus = "working" | "done" | "error";
export type LatticePatternName =
  | "arrow"
  | "dots"
  | "orbit"
  | "ripple"
  | "snake"
  | "spiral"
  | "sweep"
  | "spin"
  | "rain"
  | "pulse";
export type LatticeGrid = 3 | 4;

export interface LatticeLoaderProps {
  /** Visible text beside the grid; omit for a glyph-only loader. */
  label?: string;
  status?: LatticeStatus;
  pattern?: LatticePatternName;
  grid?: LatticeGrid;
  shape?: "square" | "round";
  color?: string;
  doneColor?: string;
  errorColor?: string;
  cellSize?: number;
  gap?: number;
  fontSize?: number;
  step?: number;
  idleOpacity?: number;
  glow?: boolean;
  /** Hold the grid still (e.g. replaying a wait that is not happening now). */
  paused?: boolean;
  /** Real elapsed seconds measured by the caller; omitted means no timer. */
  elapsed?: number | null;
  /** Formats `elapsed` for display (e.g. localized seconds). */
  formatElapsed?: (seconds: number) => string;
  className?: string;
  style?: CSSProperties;
}

type ResolvedPattern = {
  cells: (number | null)[];
  loop: number;
  scale: number;
  lit?: number;
};

const PATTERNS: Record<
  LatticePatternName,
  Partial<Record<LatticeGrid, ResolvedPattern>>
> = {
  arrow: { 3: { cells: [1, 2, 3, 0, 1, 2, 1, 2, 3], loop: 7.2, scale: 1 } },
  dots: { 3: { cells: [0, 1, 2, 0, 1, 2, 0, 1, 2], loop: 3, scale: 2.4 } },
  ripple: { 3: { cells: [2, 1, 2, 1, 0, 1, 2, 1, 2], loop: 4.8, scale: 1.5 } },
  spiral: {
    3: { cells: [0, 1, 2, 7, 8, 3, 6, 5, 4], loop: 9, scale: 1.2, lit: 0.35 },
  },
  orbit: {
    3: { cells: [0, 1, 2, 7, null, 3, 6, 5, 4], loop: 8, scale: 1.2 },
    4: {
      cells: [0, 1, 2, 3, 11, null, null, 4, 10, null, null, 5, 9, 8, 7, 6],
      loop: 6,
      scale: 1.2,
      lit: 0.45,
    },
  },
  snake: {
    3: { cells: [0, 1, 2, 5, 4, 3, 6, 7, 8], loop: 9, scale: 1, lit: 0.35 },
    4: {
      cells: [0, 1, 2, 3, 7, 6, 5, 4, 8, 9, 10, 11, 15, 14, 13, 12],
      loop: 16,
      scale: 1,
      lit: 0.25,
    },
  },
  sweep: {
    4: {
      cells: [0, 1, 2, 3, 1, 2, 3, 4, 2, 3, 4, 5, 3, 4, 5, 6],
      loop: 5,
      scale: 1,
      lit: 0.45,
    },
  },
  spin: {
    4: {
      cells: [0, 0, 1, 1, 0, 0, 1, 1, 3, 3, 2, 2, 3, 3, 2, 2],
      loop: 4,
      scale: 1.6,
      lit: 0.35,
    },
  },
  rain: {
    4: {
      cells: [0, 2, 1, 3, 1, 3, 2, 4, 2, 4, 3, 5, 3, 5, 4, 6],
      loop: 4,
      scale: 1.2,
      lit: 0.35,
    },
  },
  pulse: {
    4: {
      cells: [2, 1, 1, 2, 1, 0, 0, 1, 1, 0, 0, 1, 2, 1, 1, 2],
      loop: 2.4,
      scale: 2.5,
      lit: 0.45,
    },
  },
};
const DEFAULT_PATTERN: Record<LatticeGrid, LatticePatternName> = {
  3: "orbit",
  4: "sweep",
};
const MARKS: Record<LatticeGrid, Record<"done" | "error", number[]>> = {
  3: { done: [2, 3, 5, 7], error: [0, 2, 4, 6, 8] },
  4: { done: [7, 8, 10, 13], error: [0, 3, 5, 6, 9, 10, 12, 15] },
};
const KEYFRAME: Record<number, string> = {
  62: "lattice-on",
  45: "lattice-on-45",
  35: "lattice-on-35",
  25: "lattice-on-25",
};

const STYLE = `
@keyframes lattice-on { 0%, 100% { opacity: var(--ll-idle); } 18%, 42% { opacity: 1; } 62% { opacity: var(--ll-idle); } }
@keyframes lattice-on-45 { 0%, 100% { opacity: var(--ll-idle); } 13%, 31% { opacity: 1; } 45% { opacity: var(--ll-idle); } }
@keyframes lattice-on-35 { 0%, 100% { opacity: var(--ll-idle); } 10%, 24% { opacity: 1; } 35% { opacity: var(--ll-idle); } }
@keyframes lattice-on-25 { 0%, 100% { opacity: var(--ll-idle); } 7%, 17% { opacity: 1; } 25% { opacity: var(--ll-idle); } }
.ll-root { display: inline-flex; align-items: center; gap: calc(var(--ll-font) * 0.6); font-size: var(--ll-font); line-height: 1; }
.ll-grid { display: grid; flex: none; grid-template-columns: repeat(var(--ll-n), var(--ll-cell)); gap: var(--ll-gap); }
.ll-cell { width: var(--ll-cell); height: var(--ll-cell); border-radius: max(1px, calc(var(--ll-cell) * 0.25)); background: var(--ll-color); opacity: var(--ll-idle); }
.ll-root[data-shape="round"] .ll-cell { border-radius: 999px; }
.ll-cell[data-hole] { opacity: calc(var(--ll-idle) * 0.47); }
.ll-root[data-status="working"] .ll-cell[data-unit] { animation: var(--ll-key) var(--ll-cycle) cubic-bezier(0.77, 0, 0.175, 1) infinite; }
.ll-root[data-paused] .ll-cell[data-unit] { animation-play-state: paused; }
.ll-root[data-glow] .ll-cell[data-unit] { box-shadow: 0 0 calc(var(--ll-cell) * 1.2) calc(var(--ll-cell) * 0.12) var(--ll-color); }
.ll-root[data-status="done"] .ll-cell[data-on], .ll-root[data-status="error"] .ll-cell[data-on] { opacity: 1; background: var(--ll-mark); transition: opacity 200ms ease, background-color 200ms ease; }
.ll-timer { font-family: "Cascadia Code", ui-monospace, monospace; font-variant-numeric: tabular-nums; opacity: 0.72; font-size: calc(var(--ll-font) * 0.9); }
:root:not([data-motion="full"]) .ll-root[data-status="working"] .ll-cell[data-unit] { animation: none; opacity: 0.55; }
`;

const LatticeLoader: React.FC<LatticeLoaderProps> = ({
  label,
  status = "working",
  pattern,
  grid = 3,
  shape = "round",
  color = "currentColor",
  doneColor = "var(--success, #22c55e)",
  errorColor = "var(--danger, #ef4444)",
  cellSize = 5,
  gap = 2,
  fontSize = 13,
  step = 90,
  idleOpacity = 0.18,
  glow = false,
  paused = false,
  elapsed,
  formatElapsed = (seconds) => `${seconds.toFixed(1)}s`,
  className = "",
  style,
}) => {
  const { ref, active } = useMotionBudget<HTMLSpanElement>("css");
  const n: LatticeGrid = grid === 4 ? 4 : 3;
  const pat =
    (pattern && PATTERNS[pattern][n]) ||
    (PATTERNS[DEFAULT_PATTERN[n]][n] as ResolvedPattern);
  const d = step * pat.scale;
  const cycle = Math.round(pat.loop * d);
  const key = KEYFRAME[Math.round((pat.lit ?? 0.62) * 100)] ?? KEYFRAME[62];
  const marks = status === "working" ? [] : MARKS[n][status];
  return (
    <span
      ref={ref}
      className={`ll-root${className ? ` ${className}` : ""}`}
      data-status={status}
      data-shape={shape}
      data-glow={glow ? "" : undefined}
      data-paused={active && !paused ? undefined : ""}
      style={
        {
          "--ll-n": n,
          "--ll-cell": `${cellSize}px`,
          "--ll-gap": `${gap}px`,
          "--ll-font": `${fontSize}px`,
          "--ll-color": color,
          "--ll-mark": status === "error" ? errorColor : doneColor,
          "--ll-idle": idleOpacity,
          "--ll-cycle": `${cycle}ms`,
          "--ll-key": key,
          ...style,
        } as CSSProperties
      }
    >
      <style>{STYLE}</style>
      <span className="ll-grid" aria-hidden="true">
        {pat.cells.map((unit, index) => (
          <span
            key={index}
            className="ll-cell"
            data-hole={unit == null ? "" : undefined}
            data-unit={unit == null ? undefined : ""}
            data-on={marks.includes(index) ? "" : undefined}
            style={
              unit == null
                ? undefined
                : { animationDelay: `${Math.round(unit * d)}ms` }
            }
          />
        ))}
      </span>
      {label ? <span className="ll-label">{label}</span> : null}
      {elapsed != null ? (
        <span className="ll-timer">{formatElapsed(elapsed)}</span>
      ) : null}
    </span>
  );
};

export default LatticeLoader;
