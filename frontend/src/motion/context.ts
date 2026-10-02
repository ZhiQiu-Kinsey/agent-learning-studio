import { createContext, useContext } from "react";
import type { MotionLevel } from "./level";

export interface MotionState {
  /** Effective level: static when the OS asks for reduced motion. */
  level: MotionLevel;
  /** True when nothing should move: skip ambient, looping and entrance effects. */
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

export const useReducedMotion = () => useMotion().reduced;
