// Adapted from https://reactbits.dev/r/SwipeToast-TS-TW.json (MIT + Commons Clause).
// Changes: motion level comes from the app's MotionProvider (static motion keeps a
// plain fade and hides the burning fuse, the timer itself still runs); always
// inline so a host can stack several; translated close label; caller-chosen live
// role; lucide close icon.
import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent,
  type PointerEvent,
  type ReactNode,
} from "react";
import { animate, motion, useMotionValue, useTransform } from "motion/react";
import { X } from "lucide-react";
import { useReducedMotion } from "../../motion";

export type SwipeToastCloseReason =
  "timeout" | "swipe" | "close" | "escape" | "programmatic";
type Phase = "open" | "closing" | "gone";
type Sample = [number, number];
interface Drag {
  id: number;
  startY: number;
  grab: number | null;
  moved: boolean;
  hist: Sample[];
}

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

const EASE_OUT: [number, number, number, number] = [0.23, 1, 0.32, 1];
const FLICK = 0.11;
const DEAD_ZONE = 3;
const RESIST_PX = 24;
const COLLAPSE_MS = 200;
const EXIT = 0.7;
const BURN = [{ transform: "scaleX(1)" }, { transform: "scaleX(0)" }];
const HAS_STARTING_STYLE =
  typeof window !== "undefined" && "CSSStartingStyleRule" in window;

const rubberband = (over: number, dim: number, c = 0.55) =>
  (over * dim * c) / (dim + c * Math.abs(over));
const velocityOf = (hist: Sample[]) => {
  if (hist.length < 2) return 0;
  const [t0, y0] = hist[0];
  const [t1, y1] = hist[hist.length - 1];
  return performance.now() - t1 > 100 ? 0 : (y1 - y0) / Math.max(1, t1 - t0);
};

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
  const reduce = useReducedMotion();
  const [phase, setPhase] = useState<Phase>("open");
  const [instant, setInstant] = useState(false);
  const [mounted, setMounted] = useState(HAS_STARTING_STYLE);
  const cardRef = useRef<HTMLDivElement>(null);
  const fuseRef = useRef<HTMLElement>(null);
  const anim = useRef<Animation | null>(null);
  const drag = useRef<Drag | null>(null);
  const flags = useRef({
    hover: false,
    interacting: false,
    focus: false,
    hidden: false,
  });
  const lastInput = useRef<"pointer" | "keyboard">("pointer");
  const pendingClose = useRef<SwipeToastCloseReason | null>(null);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | undefined>(
    undefined,
  );
  const leaving = useRef(false);
  const phaseRef = useRef(phase);
  phaseRef.current = phase;
  const latest = useRef({ onClose, slideMs });
  latest.current = { onClose, slideMs };

  const y = useMotionValue(0);
  const fade = useMotionValue(1);
  const transform = useTransform(y, (v) => `translateY(${v}px)`);

  const syncFuse = () => {
    const a = anim.current;
    if (!a) return;
    const f = flags.current;
    if (f.hover || f.interacting || f.focus || f.hidden) a.pause();
    else if (a.playState === "paused") a.play();
  };
  const finish = (why: SwipeToastCloseReason) => {
    setPhase("gone");
    leaving.current = false;
    closeTimer.current = setTimeout(
      () => latest.current.onClose?.(why),
      COLLAPSE_MS,
    );
  };
  const close = (why: SwipeToastCloseReason) => {
    if (phaseRef.current !== "open" || leaving.current) return;
    if (drag.current) {
      pendingClose.current = why;
      return;
    }
    anim.current?.pause();
    const now =
      why === "escape" || (why === "close" && lastInput.current === "keyboard");
    setInstant(now);
    setPhase("closing");
    clearTimeout(closeTimer.current);
    closeTimer.current = setTimeout(
      () => finish(why),
      now ? 0 : latest.current.slideMs * EXIT + 60,
    );
  };
  const rescue = () => {
    clearTimeout(closeTimer.current);
    setInstant(false);
    y.set(0);
    fade.set(1);
    setPhase("open");
  };

  useEffect(() => {
    if (!open) close("programmatic");
    else if (phaseRef.current !== "open") rescue();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);
  useEffect(() => {
    if (!HAS_STARTING_STYLE) requestAnimationFrame(() => setMounted(true));
  }, []);
  // The fuse is the timer: a WAAPI scaleX burn whose end closes the toast.
  useEffect(() => {
    if (phase !== "open" || duration <= 0 || !fuseRef.current) return;
    anim.current?.cancel();
    const a = fuseRef.current.animate(BURN, {
      duration,
      easing: "linear",
      fill: "forwards",
    });
    a.onfinish = () => close("timeout");
    anim.current = a;
    syncFuse();
    return () => {
      a.onfinish = null;
      a.pause();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, duration]);
  useEffect(() => {
    const onVisibility = () => {
      flags.current.hidden = document.hidden;
      syncFuse();
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      clearTimeout(closeTimer.current);
      anim.current?.cancel();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const swipeOut = (dy: number, v: number) => {
    anim.current?.pause();
    leaving.current = true;
    pendingClose.current = null;
    if (!reduce && cardRef.current) {
      animate(y, dy + cardRef.current.offsetHeight, {
        type: "spring",
        duration: 0.3,
        bounce: 0,
        velocity: v * 1000,
      });
    }
    animate(fade, 0, { duration: 0.2, ease: EASE_OUT }).then(() =>
      finish("swipe"),
    );
  };
  const onPointerDown = (e: PointerEvent<HTMLDivElement>) => {
    lastInput.current = "pointer";
    if (
      e.button !== 0 ||
      drag.current ||
      leaving.current ||
      (e.target as HTMLElement).closest("button")
    )
      return;
    if (phaseRef.current === "closing") rescue();
    try {
      cardRef.current?.setPointerCapture(e.pointerId);
    } catch {
      /* Capture is a nicety; dragging still works inside the card. */
    }
    y.stop();
    drag.current = {
      id: e.pointerId,
      startY: e.clientY,
      grab: null,
      moved: false,
      hist: [[performance.now(), y.get()]],
    };
    flags.current.interacting = true;
    syncFuse();
  };
  const onPointerMove = (e: PointerEvent<HTMLDivElement>) => {
    const d = drag.current;
    if (!d || d.id !== e.pointerId) return;
    if (d.grab === null) {
      if (Math.abs(e.clientY - d.startY) < DEAD_ZONE) return;
      d.grab = e.clientY - y.get();
      if (cardRef.current) cardRef.current.dataset.swiping = "";
    }
    const raw = e.clientY - d.grab;
    const next = raw >= 0 ? raw : rubberband(raw, RESIST_PX);
    y.set(next);
    d.moved = true;
    d.hist.push([performance.now(), next]);
    if (d.hist.length > 4) d.hist.shift();
  };
  const onPointerUp = (e: PointerEvent<HTMLDivElement>) => {
    const d = drag.current;
    if (!d || d.id !== e.pointerId) return;
    drag.current = null;
    if (cardRef.current) delete cardRef.current.dataset.swiping;
    try {
      cardRef.current?.releasePointerCapture(e.pointerId);
    } catch {
      /* Already released. */
    }
    flags.current.interacting = false;
    const dy = y.get();
    const v = velocityOf(d.hist);
    if (dy > 0 && (v > FLICK || (dy >= swipeDistance && v >= 0))) {
      swipeOut(dy, v);
      return;
    }
    if (d.moved) {
      animate(
        y,
        0,
        reduce
          ? { duration: 0.2, ease: EASE_OUT }
          : { type: "spring", duration: 0.5, bounce: 0.2, velocity: v * 1000 },
      );
    }
    const queued = pendingClose.current;
    pendingClose.current = null;
    if (queued) close(queued);
    else syncFuse();
  };
  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Enter" || e.key === " ") lastInput.current = "keyboard";
    if (e.key === "Escape" || e.key === "Delete") {
      e.stopPropagation();
      close("escape");
    }
  };

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
