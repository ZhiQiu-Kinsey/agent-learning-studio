import { useEffect, useState } from "react";
import { useMotionBudget } from "../../../motion";

/**
 * Motion gating for the canvas. `flowActive` runs the edge current only while
 * the canvas is on screen in a visible tab; `entered` flips once, the first
 * time the canvas is seen, so node entrances never replay.
 */
export function useRoadmapEntrance() {
  const { ref, active } = useMotionBudget<HTMLDivElement>("css");
  const [entered, setEntered] = useState(false);
  useEffect(() => {
    if (active) setEntered(true);
  }, [active]);
  return { ref, flowActive: active, entered };
}
