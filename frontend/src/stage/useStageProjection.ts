import { useMemo } from "react";
import type { Trace } from "../types";
import { deriveStage } from "./derive";

/**
 * The stage at the replay cursor plus the whole run's projection. Views that
 * scrub (timeline bars, recorded waits) read `final` so nothing jumps around.
 */
export function useStageProjection(events: readonly Trace[], cursor: number) {
  const stage = useMemo(() => deriveStage(events, cursor), [events, cursor]);
  const final = useMemo(() => deriveStage(events, events.length), [events]);
  return { stage, final };
}
