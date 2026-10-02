/**
 * Motion levels, decided only by the OS "reduce motion" preference:
 * - full: every effect, still subject to viewport and WebGL budgets.
 * - static: nothing moves; state changes apply instantly.
 */
export type MotionLevel = "full" | "static";

export const resolveMotionLevel = (systemReduced: boolean): MotionLevel =>
  systemReduced ? "static" : "full";

/** Synchronous check for imperative code; MotionProvider keeps the attribute current. */
export function motionLevelNow(): MotionLevel {
  return document.documentElement.dataset.motion === "full" ? "full" : "static";
}

export const prefersReducedMotionNow = () => motionLevelNow() !== "full";
