import { useRef } from "react";
import { useInView } from "motion/react";
import { useMotion } from "./context";
import type { MotionLevel } from "./level";

/** css: transforms/opacity; canvas: 2D loops; webgl: GPU contexts. */
export type MotionCost = "css" | "canvas" | "webgl";

/**
 * Whether an effect of this cost may exist at all. There is no on-screen WebGL
 * cap (maintainer decision 2026-10-06): every WebGL effect runs at full motion
 * when the browser supports WebGL, and the viewport gate in useMotionBudget
 * unmounts off-screen ones so their GPU contexts are released.
 */
export function motionGranted(
  cost: MotionCost,
  { level, webgl }: { level: MotionLevel; webgl: boolean },
): boolean {
  if (level !== "full") return false;
  return cost !== "webgl" || webgl;
}

/**
 * Per-effect budget. `granted` means the effect may exist at all (level and
 * WebGL support); `active` additionally requires the element to be on screen in
 * a visible tab, so recurring work pauses and WebGL effects unmount otherwise.
 */
export function useMotionBudget<T extends HTMLElement>(
  cost: MotionCost = "css",
  { margin = "20px" }: { margin?: string } = {},
) {
  const ref = useRef<T>(null);
  const { level, reduced, webgl, pageVisible } = useMotion();
  const inView = useInView(ref, { margin: margin as `${number}px` });
  const granted = motionGranted(cost, { level, webgl });

  return {
    ref,
    granted,
    active: granted && inView && pageVisible,
    reduced,
    inView,
  };
}
