import { createContext, useContext } from "react";
import type { MotionLevel, MotionSetting } from "./level";

export interface MotionState {
  /** What the learner chose. */
  setting: MotionSetting;
  setSetting: (setting: MotionSetting) => void;
  /** Effective level after merging the OS preference. */
  level: MotionLevel;
  /** True for reduced and static: skip ambient, looping and entrance effects. */
  reduced: boolean;
  webgl: boolean;
  pageVisible: boolean;
}

export const MotionContext = createContext<MotionState | null>(null);

export function useMotion(): MotionState {
  const state = useContext(MotionContext);
  if (!state) throw new Error("useMotion must be used inside <MotionProvider>");
  return state;
}

/** Drop-in replacement for the old OS-only hook. */
export const useReducedMotion = () => useMotion().reduced;
