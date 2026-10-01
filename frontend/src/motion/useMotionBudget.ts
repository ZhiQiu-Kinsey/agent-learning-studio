import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { useInView } from "motion/react";
import { useMotion } from "./context";
import { createSlotPool } from "./slotPool";

/** css: transforms/opacity; canvas: 2D loops; webgl: GPU contexts (one at a time). */
export type MotionCost = "css" | "canvas" | "webgl";

export const webglSlots = createSlotPool(1);

/**
 * Per-effect budget. `granted` means the effect may exist at all (level, WebGL
 * support and the shared WebGL slot); `active` additionally requires the element
 * to be on screen in a visible tab, so recurring work pauses otherwise.
 */
export function useMotionBudget<T extends HTMLElement>(
  cost: MotionCost = "css",
  { margin = "20px" }: { margin?: string } = {},
) {
  const ref = useRef<T>(null);
  const { level, reduced, webgl, pageVisible } = useMotion();
  const inView = useInView(ref, { margin: margin as `${number}px` });
  const [token] = useState(() => Symbol("motion-budget"));
  const wantsSlot = cost === "webgl" && level === "full" && webgl;

  useEffect(() => {
    if (!wantsSlot) return;
    webglSlots.request(token);
    return () => webglSlots.release(token);
  }, [wantsSlot, token]);

  const hasSlot = useSyncExternalStore(
    webglSlots.subscribe,
    () => webglSlots.has(token),
    () => false,
  );
  const granted = !reduced && (cost !== "webgl" || (wantsSlot && hasSlot));

  return {
    ref,
    granted,
    active: granted && inView && pageVisible,
    reduced,
    inView,
  };
}
