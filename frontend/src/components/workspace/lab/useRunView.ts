import type { StudioState } from "../../../hooks/useStudio";
import { openLlmSpan } from "../../../stage/spans";
import { useStageProjection } from "../../../stage/useStageProjection";

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
    completed: last?.type === "done" && last.data.status === "completed",
  };
}

export type RunView = ReturnType<typeof useRunView>;
