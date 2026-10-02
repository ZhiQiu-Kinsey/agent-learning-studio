// Adapted from https://reactbits.dev/r/SwipeToast-TS-TW.json (MIT + Commons Clause).
// Changes: motion level comes from the app's MotionProvider (static motion keeps a
// plain fade and hides the burning fuse, the timer itself still runs); always
// inline so a host can stack several; translated close label; caller-chosen live
// role; lucide close icon.
import type { CSSProperties, ReactNode } from "react";
import { motion } from "motion/react";
import { X } from "lucide-react";
import { useSwipeToast } from "./SwipeToast/useSwipeToast";

export type SwipeToastCloseReason =
  "timeout" | "swipe" | "close" | "escape" | "programmatic";

export interface SwipeToastProps {
  title: ReactNode;
  description?: ReactNode;
  icon?: ReactNode;
  open?: boolean;
  onClose?: (reason: SwipeToastCloseReason) => void;
  /** Accent for the fuse and the icon. */
  accent?: string;
  /** Milliseconds before the toast leaves on its own (0 keeps it). */
  duration?: number;
  slideMs?: number;
  swipeDistance?: number;
  closeLabel: string;
  role?: "status" | "alert";
  className?: string;
}

export default function SwipeToast({
  title,
  description,
  icon,
  open = true,
  onClose,
  accent = "#6d5dfc",
  duration = 5000,
  slideMs = 420,
  swipeDistance = 40,
  closeLabel,
  role = "status",
  className = "",
}: SwipeToastProps) {
  const {
    phase,
    instant,
    mounted,
    cardRef,
    fuseRef,
    flags,
    lastInput,
    fade,
    transform,
    syncFuse,
    close,
    onPointerDown,
    onPointerMove,
    onPointerUp,
    onKeyDown,
  } = useSwipeToast({ open, onClose, duration, slideMs, swipeDistance });

  return (
    <div
      className={`rb-swipe-toast group grid w-full [grid-template-rows:1fr] [transition:grid-template-rows_var(--st-slide)_cubic-bezier(0.23,1,0.32,1)] starting:[grid-template-rows:0fr] data-[mounted=false]:[grid-template-rows:0fr] data-[phase=closing]:[grid-template-rows:0fr] data-[phase=gone]:[grid-template-rows:0fr] data-[phase=closing]:[transition-duration:calc(var(--st-slide)*0.7)] data-[phase=gone]:[transition-duration:200ms] ${className}`}
      data-phase={phase}
      data-instant={instant ? "" : undefined}
      data-mounted={mounted ? "true" : "false"}
      style={
        {
          "--st-accent": accent,
          "--st-slide": `${slideMs}ms`,
        } as CSSProperties
      }
    >
      <div className="min-h-0">
        <div className="rb-swipe-toast-lift mt-2.5 opacity-100 [transform:translateY(0)] [transition:transform_var(--st-slide)_cubic-bezier(0.23,1,0.32,1),opacity_calc(var(--st-slide)*0.6)_ease] starting:opacity-0 starting:[transform:translateY(100%)] group-data-[mounted=false]:opacity-0 group-data-[mounted=false]:[transform:translateY(100%)] group-data-[phase=closing]:opacity-0 group-data-[phase=closing]:[transform:translateY(100%)] group-data-[phase=gone]:invisible group-data-[phase=gone]:opacity-0 group-data-[instant]:[transition-duration:0s] motion-reduce:[transform:none]! motion-reduce:[transition:opacity_200ms_ease]">
          <motion.div
            ref={cardRef}
            className="rb-swipe-toast-card relative flex cursor-grab touch-none items-start gap-3 overflow-hidden outline-none select-none data-[swiping]:cursor-grabbing"
            role={role}
            aria-live={role === "alert" ? "assertive" : "polite"}
            aria-atomic="true"
            tabIndex={0}
            style={{ transform, opacity: fade }}
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerCancel={onPointerUp}
            onPointerEnter={(e) => {
              if (e.pointerType === "mouse") {
                flags.current.hover = true;
                syncFuse();
              }
            }}
            onPointerLeave={(e) => {
              if (e.pointerType === "mouse") {
                flags.current.hover = false;
                syncFuse();
              }
            }}
            onFocus={() => {
              flags.current.focus = true;
              syncFuse();
            }}
            onBlur={(e) => {
              if (!e.currentTarget.contains(e.relatedTarget as Node | null)) {
                flags.current.focus = false;
                syncFuse();
              }
            }}
            onKeyDown={onKeyDown}
          >
            {icon ? (
              <span className="rb-swipe-toast-icon" aria-hidden="true">
                {icon}
              </span>
            ) : null}
            <span className="flex min-w-0 flex-auto flex-col gap-0.5">
              <span className="rb-swipe-toast-title">{title}</span>
              {description ? (
                <span className="rb-swipe-toast-description">
                  {description}
                </span>
              ) : null}
            </span>
            <button
              type="button"
              className="rb-swipe-toast-close"
              aria-label={closeLabel}
              onKeyDown={() => {
                lastInput.current = "keyboard";
              }}
              onPointerDown={() => {
                lastInput.current = "pointer";
              }}
              onClick={() => close("close")}
            >
              <X size={13} strokeWidth={2.5} aria-hidden="true" />
            </button>
            {duration > 0 && (
              <i
                ref={fuseRef}
                className="rb-swipe-toast-fuse"
                aria-hidden="true"
              />
            )}
          </motion.div>
        </div>
      </div>
    </div>
  );
}
