// Adapted from https://reactbits.dev/r/JellyRadio-TS-TW.json (MIT + Commons Clause).
import type { JellyRadioItem } from "../JellyRadio";

export interface Config {
  swell: number;
  barge: number;
  shrink: number;
  jelly: number;
  bounce: number;
  stagger: number;
  stiffness: number;
  reduce: boolean | null;
  count: number;
}

export const DEFAULT_ITEMS: JellyRadioItem[] = [
  "Off",
  "Low",
  "Medium",
  "High",
  "Max",
];
export const SIZES: Record<string, [number, number, number]> = {
  sm: [28, 12, 12],
  md: [36, 13, 16],
  lg: [44, 14, 20],
};

export const spring = (k: number, m: number, bounce: number) => ({
  type: "spring" as const,
  stiffness: k,
  damping: 2 * Math.sqrt(k * m) * (1 - bounce),
  mass: m,
});
