import { useEffect, useRef, type RefObject } from "react";
import { useReducedMotion } from "../../motion";

/** Keys that scroll the page; pressing one outside a text field means the learner is steering. */
const SCROLL_KEYS = new Set([
  "ArrowUp",
  "ArrowDown",
  "PageUp",
  "PageDown",
  "Home",
  "End",
  " ",
]);
/** A fast run still stays on the observatory long enough to be seen finishing. */
const MIN_STAY_MS = 1200;
/** Pause on the finished stage before going back. */
const SETTLE_MS = 400;

const editable = (target: EventTarget | null) =>
  target instanceof HTMLElement &&
  (target.isContentEditable ||
    ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName));

/**
 * The view follows a run. When it starts, the run observatory (the element
 * marked `data-run-focus` inside `frame`) scrolls in under the sticky toolbar;
 * when it ends, the page returns to where the learner started it. Scrolling by
 * hand at any point hands the view back to the learner for that run.
 */
export function useRunFollow(
  running: boolean,
  enabled: boolean,
  frame: RefObject<HTMLElement | null>,
) {
  const reduced = useReducedMotion();
  const behavior = useRef<ScrollBehavior>("smooth");
  behavior.current = reduced ? "instant" : "smooth";
  const trip = useRef<{ origin: number; since: number } | null>(null);

  useEffect(() => {
    const release = () => {
      trip.current = null;
    };
    const onKey = (event: KeyboardEvent) => {
      if (SCROLL_KEYS.has(event.key) && !editable(event.target)) release();
    };
    window.addEventListener("wheel", release, { passive: true });
    window.addEventListener("touchmove", release, { passive: true });
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("wheel", release);
      window.removeEventListener("touchmove", release);
      window.removeEventListener("keydown", onKey);
    };
  }, []);

  useEffect(() => {
    if (!enabled) {
      trip.current = null;
      return;
    }
    if (running) {
      const target =
        frame.current?.querySelector<HTMLElement>("[data-run-focus]") ??
        frame.current;
      if (!target) return;
      trip.current = { origin: window.scrollY, since: performance.now() };
      target.scrollIntoView({ block: "start", behavior: behavior.current });
      return;
    }
    const current = trip.current;
    if (!current) return;
    const wait =
      Math.max(0, MIN_STAY_MS - (performance.now() - current.since)) +
      SETTLE_MS;
    const timer = window.setTimeout(() => {
      // Released meanwhile: the learner scrolled, leave the page where it is.
      if (trip.current !== current) return;
      trip.current = null;
      window.scrollTo({ top: current.origin, behavior: behavior.current });
    }, wait);
    return () => window.clearTimeout(timer);
  }, [running, enabled, frame]);
}
