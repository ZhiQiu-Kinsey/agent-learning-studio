import { useEffect, useMemo, useState } from "react";
import type { CurriculumGraph } from "../graph";
import {
  layoutRoadmap,
  NODE_HEIGHT,
  NODE_WIDTH,
  type Positions,
} from "../layout";

/**
 * ELK positions for the graph (null while laying out), the layout error if
 * any, and each node's centre for spatial keyboard navigation.
 */
export function useRoadmapLayout(graph: CurriculumGraph) {
  const [positions, setPositions] = useState<Positions | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let ignore = false;
    setPositions(null);
    setError("");
    layoutRoadmap(graph)
      .then((value) => {
        if (!ignore) setPositions(value);
      })
      .catch((reason) => {
        if (!ignore)
          setError(reason instanceof Error ? reason.message : String(reason));
      });
    return () => {
      ignore = true;
    };
  }, [graph]);

  const centers = useMemo(
    () =>
      positions
        ? [...positions].map(([id, point]) => ({
            id,
            x: point.x + NODE_WIDTH / 2,
            y: point.y + NODE_HEIGHT / 2,
          }))
        : [],
    [positions],
  );

  return { positions, error, centers };
}
