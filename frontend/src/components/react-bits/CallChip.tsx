// Adapted from https://reactbits.dev/r/CallChip-TS-CSS.json (MIT + Commons Clause).
// Changes for real tool calls: the timer never runs its own clock — while a
// call is open it shows the real time since that call's event (`startAt`, a
// server timestamp); once closed it shows the server timestamp difference
// (`durationMs`). The estimated progress fill is replaced by an indeterminate
// sweep (it never implies how far along a call is). Copy comes from the caller,
// it renders as a button when `onClick` is given, and motion follows the app
// motion level.
import React, {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import { HugeiconsIcon } from "@hugeicons/react";
import {
  Cancel01Icon,
  CommandLineIcon,
  HelpCircleIcon,
  StopIcon,
  Tick02Icon,
} from "@hugeicons/core-free-icons";
import { prefersReducedMotionNow } from "../../motion/level";
import { useElapsedMs } from "../../stage/useElapsed";

import "./CallChip.css";

/** `unknown`: the call closed but its result declared no ok/failed status. */
export type CallChipStatus =
  "running" | "done" | "error" | "stopped" | "unknown";

export interface CallChipProps {
  name: string;
  argument?: string;
  status: CallChipStatus;
  /** Server timestamp of the call event; drives the live timer while running. */
  startAt?: string | null;
  /** Server timestamp difference once the call closed; null when unreadable. */
  durationMs?: number | null;
  /** Accessible status words, already translated. */
  statusLabel: string;
  formatMs?: (ms: number) => string;
  icon?: ReactNode;
  onClick?: () => void;
  pressed?: boolean;
  size?: number;
  radius?: number;
  color?: string;
  surfaceColor?: string;
  doneColor?: string;
  errorColor?: string;
  shake?: number;
  className?: string;
  style?: CSSProperties;
  "data-testid"?: string;
}

const SHAKE = [0, -1, 1, -0.66, 0.66, -0.33, 0];
const defaultFormat = (ms: number) =>
  ms < 10000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`;
const GLYPHS: Record<CallChipStatus, typeof CommandLineIcon> = {
  running: CommandLineIcon,
  done: Tick02Icon,
  error: Cancel01Icon,
  stopped: StopIcon,
  unknown: HelpCircleIcon,
};

const CallChip: React.FC<CallChipProps> = ({
  name,
  argument = "",
  status,
  startAt,
  durationMs = null,
  statusLabel,
  formatMs = defaultFormat,
  icon,
  onClick,
  pressed,
  size = 30,
  radius = 9,
  color = "currentColor",
  surfaceColor = "var(--surface-muted)",
  doneColor = "var(--success, #22c55e)",
  errorColor = "var(--danger, #ef4444)",
  shake = 5,
  className = "",
  style,
  "data-testid": testId,
}) => {
  const rootRef = useRef<HTMLElement | null>(null);
  const previous = useRef(status);
  const [settled, setSettled] = useState(false);
  const live = useElapsedMs(status === "running" ? startAt : null);
  const ms = status === "running" ? live : durationMs;
  const timer = ms == null ? "—" : formatMs(ms);

  // Shake once when a call that was running comes back with an error.
  useEffect(() => {
    const from = previous.current;
    previous.current = status;
    if (from === "running" && status !== "running") setSettled(true);
    if (
      from === "running" &&
      status === "error" &&
      shake > 0 &&
      !prefersReducedMotionNow() &&
      rootRef.current?.animate
    ) {
      rootRef.current.animate(
        SHAKE.map((k) => ({ transform: `translateX(${k * shake}px)` })),
        { duration: 450, easing: "cubic-bezier(0.77, 0, 0.175, 1)" },
      );
    }
  }, [status, shake]);

  const font = Math.max(11, Math.round(size * 0.4));
  const vars = {
    "--cc-size": `${size}px`,
    "--cc-font": `${font}px`,
    "--cc-pad": `${Math.round(size * 0.34)}px`,
    "--cc-gap": `${Math.round(font * 0.55)}px`,
    "--cc-radius": `${radius}px`,
    "--cc-color": color,
    "--cc-surface": surfaceColor,
    "--cc-done": doneColor,
    "--cc-error": errorColor,
    ...style,
  } as CSSProperties;
  const content = (
    <>
      <span className="call-chip__fill" aria-hidden="true" />
      <span className="call-chip__glyph" aria-hidden="true" key={status}>
        {status === "running" && icon ? (
          icon
        ) : (
          <HugeiconsIcon
            icon={GLYPHS[status]}
            size={font + 2}
            strokeWidth={status === "running" ? 1.8 : 2.2}
          />
        )}
      </span>
      {/* Visual text is hidden from assistive tech; statusLabel names the chip. */}
      <span className="call-chip__name" aria-hidden="true">
        {name}
      </span>
      {argument ? (
        <span className="call-chip__arg" aria-hidden="true">
          {argument}
        </span>
      ) : null}
      <span className="call-chip__timer" aria-hidden="true">
        {timer}
      </span>
      <span className="call-chip__sr">{statusLabel}</span>
    </>
  );
  const common = {
    className: `call-chip${className ? ` ${className}` : ""}`,
    "data-status": status,
    "data-settled": settled ? "" : undefined,
    "data-testid": testId,
    style: vars,
  };
  return onClick ? (
    <button
      {...common}
      ref={(node) => {
        rootRef.current = node;
      }}
      type="button"
      aria-pressed={pressed}
      onClick={onClick}
    >
      {content}
    </button>
  ) : (
    <span
      {...common}
      ref={(node) => {
        rootRef.current = node;
      }}
    >
      {content}
    </span>
  );
};

export default CallChip;
