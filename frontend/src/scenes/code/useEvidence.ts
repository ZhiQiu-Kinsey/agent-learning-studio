import { useCallback, useState } from "react";
import type { StudioState } from "../../hooks/useStudio";
import { requestScene } from "../LessonScenes";
import { latestToolResult } from "./model";

/** Why a tool's evidence could not be opened, shown next to the button that asked. */
export type Evidence = {
  name: string;
  at: string;
  reason: "noRun" | "notCalled";
};

/**
 * "See it in the lab": only real events. Selects the latest tool_result of
 * the tool in the learner's run and switches to 实验, or records why there is
 * none (no run yet / the tool was not called).
 */
export function useEvidence(studio: StudioState) {
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const openEvidence = (name: string, at: string) => {
    if (!studio.events.length) {
      setEvidence({ name, at, reason: "noRun" });
      return;
    }
    const index = latestToolResult(studio.events, name);
    if (index < 0) {
      setEvidence({ name, at, reason: "notCalled" });
      return;
    }
    setEvidence(null);
    if (index < studio.cursor) studio.selectEvent(index);
    else studio.seek(index + 1);
    requestScene("lab");
  };
  const clearEvidence = useCallback(() => setEvidence(null), []);
  return { evidence, openEvidence, clearEvidence };
}
