// Adapted from https://reactbits.dev/r/SwipeToast-TS-TW.json (MIT + Commons Clause).
import {
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type PointerEvent,
} from "react";
import { animate, useMotionValue, useTransform } from "motion/react";
import { useReducedMotion } from "../../../motion";
import {
  type Phase,
  type Drag,
  EASE_OUT,
  FLICK,
  DEAD_ZONE,
  RESIST_PX,
  COLLAPSE_MS,
  EXIT,
  BURN,
  HAS_STARTING_STYLE,
  rubberband,
  velocityOf,
} from "./swipe";
import type { SwipeToastCloseReason, SwipeToastProps } from "../SwipeToast";

interface SwipeToastOptions {
  open: boolean;
  onClose: SwipeToastProps["onClose"];
  duration: number;
  slideMs: number;
  swipeDistance: number;
}

/** Open/closing/gone phases, the fuse timer (paused on hover, focus, drag or a hidden tab) and the swipe-down gesture. */
export function useSwipeToast({
  open,
  onClose,
  duration,
  slideMs,
  swipeDistance,
}: SwipeToastOptions) {
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
  return {
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
  };
}
