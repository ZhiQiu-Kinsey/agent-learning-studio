import { useEffect, useMemo, useState } from "react";
import { jsonFetch } from "../../api";
import type { CurriculumData } from "../../types";
import {
  buildCurriculumGraph,
  CurriculumGraphError,
  type CurriculumGraph,
} from "./graph";

export type GraphResult = { graph: CurriculumGraph } | { error: string };

/** Loads `/api/curriculum` (with retry) and derives the prerequisite graph. */
export function useCurriculumData() {
  const [curriculum, setCurriculum] = useState<CurriculumData | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let ignore = false;
    setError("");
    jsonFetch<CurriculumData>("/api/curriculum")
      .then((data) => {
        if (!ignore) setCurriculum(data);
      })
      .catch((reason) => {
        if (!ignore)
          setError(reason instanceof Error ? reason.message : String(reason));
      });
    return () => {
      ignore = true;
    };
  }, [attempt]);

  const graphResult = useMemo<GraphResult | null>(() => {
    if (!curriculum) return null;
    try {
      return { graph: buildCurriculumGraph(curriculum.lessons) };
    } catch (reason) {
      if (reason instanceof CurriculumGraphError)
        return { error: reason.message };
      throw reason;
    }
  }, [curriculum]);

  const retry = () => setAttempt((previous) => previous + 1);
  return { curriculum, error, retry, graphResult };
}
