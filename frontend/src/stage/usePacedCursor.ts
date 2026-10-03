import { useEffect, useRef, useState } from "react";
import { useMotion } from "../motion";

/** About one signal dot per step (SignalDot runs ~0.45 s), so each edge is seen. */
const STEP_MS = 450;
/** At most this many events are stepped through; an older backlog shows at once. */
const MAX_STEPS = 5;

/**
 * Live, the events after a model response (tool calls, results, the answer,
 * done) arrive within milliseconds, and the stage would jump straight to
 * "completed". The stage steps through the end of such a burst one event at a
 * time (at most MAX_STEPS, about two seconds), so the flow stays visible. A
 * lone event shows at once; replays, seeks and reduced motion are never paced
 * (the replay clock already paces replays). Only the stage is paced: the event
 * list, metrics and answer show every event as it arrives.
 */
export function usePacedCursor(cursor: number, live: boolean) {
  const { reduced } = useMotion();
  const [shown, setShown] = useState(cursor);
  // Pacing covers a live run and the tail it leaves when it ends.
  const pacing = useRef(false);
  const lastStep = useRef(Number.NEGATIVE_INFINITY);
  useEffect(() => {
    if (live) pacing.current = true;
  }, [live]);
  useEffect(() => {
    if (reduced || !pacing.current || cursor <= shown) {
      if (shown !== cursor) setShown(cursor);
      if (!live) pacing.current = false;
      return;
    }
    if (cursor - shown > MAX_STEPS) {
      setShown(cursor - MAX_STEPS);
      return;
    }
    const wait = Math.max(0, STEP_MS - (performance.now() - lastStep.current));
    const timer = window.setTimeout(() => {
      lastStep.current = performance.now();
      setShown((value) => value + 1);
    }, wait);
    return () => window.clearTimeout(timer);
  }, [cursor, shown, live, reduced]);
  return Math.min(shown, cursor);
}
