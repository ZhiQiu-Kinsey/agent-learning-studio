import type { StudioState } from "../../../hooks/useStudio";
import { openApprovalSpan, openLlmSpan } from "../../../stage/spans";
import { useStageProjection } from "../../../stage/useStageProjection";
import { streamProgress } from "./streaming";

/**
 * One projection of the real events feeds the stage, film, cards, chips and
 * timeline. `openLlm` is the model request being waited on right now; a
 * replayed open request is not a live wait.
 */
export function useRunView(s: StudioState) {
  const { stage, final } = useStageProjection(s.events, s.cursor);
  const last = s.events.at(-1);
  const live = s.running && s.cursor === s.events.length;
  return {
    stage,
    finalSpans: final.spans,
    last,
    live,
    openLlm: live ? openLlmSpan(stage.spans) : undefined,
    /** The approval gate the live run is paused at right now. */
    openApproval: live ? openApprovalSpan(stage.spans) : undefined,
    /** The latest streamed request up to the cursor and what has arrived for it. */
    stream: streamProgress(s.visible),
    completed: last?.type === "done" && last.data.status === "completed",
  };
}

export type RunView = ReturnType<typeof useRunView>;
