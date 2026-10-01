/**
 * Motion levels:
 * - full: every effect, still subject to viewport and WebGL budgets.
 * - reduced: no ambient loops, WebGL or entrance choreography; short UI transitions stay.
 * - static: nothing moves; state changes apply instantly.
 * The OS "reduce motion" preference maps to static when following the system.
 */
export const motionSettings = ["system", "full", "reduced", "static"] as const;
export type MotionSetting = (typeof motionSettings)[number];
export type MotionLevel = Exclude<MotionSetting, "system">;

export const motionStorageKey = "agent-lab-motion";

export function parseMotionSetting(value: unknown): MotionSetting {
  return motionSettings.includes(value as MotionSetting)
    ? (value as MotionSetting)
    : "system";
}

export function resolveMotionLevel(
  setting: MotionSetting,
  systemReduced: boolean,
): MotionLevel {
  if (setting === "system") return systemReduced ? "static" : "full";
  return setting;
}

/** Synchronous check for imperative code; MotionProvider keeps the attribute current. */
export function motionLevelNow(): MotionLevel {
  const level = document.documentElement.dataset.motion;
  return level === "full" || level === "reduced" || level === "static"
    ? level
    : "static";
}

export const prefersReducedMotionNow = () => motionLevelNow() !== "full";
