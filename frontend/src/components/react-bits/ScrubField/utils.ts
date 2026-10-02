// Adapted from https://reactbits.dev/r/ScrubField-TS-TW.json (MIT + Commons Clause, see LICENSE.md).
import type { ScrubFieldSize } from "../ScrubField";

export interface DragState {
  id: number;
  x: number;
  raw: number;
  mult: number;
  moved: boolean;
  before: number;
  slack: number;
  left: number;
}

export type Modifiers = { shiftKey: boolean; altKey: boolean };

export const SPRING_UI = { type: "spring" as const, duration: 0.3, bounce: 0 };
export const LEAN = 4;
export const SIZES: Record<
  ScrubFieldSize,
  { height: number; font: number; radius: number; width: number }
> = {
  sm: { height: 28, font: 12, radius: 6, width: 104 },
  md: { height: 34, font: 13, radius: 8, width: 128 },
  lg: { height: 44, font: 16, radius: 10, width: 160 },
};

export const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value));
export const decimalsOf = (n: number) => {
  const s = String(n);
  const i = s.indexOf(".");
  return i < 0 ? 0 : s.length - i - 1;
};
export const onColor = (hex: string) => {
  const raw = hex.replace("#", "");
  const full =
    raw.length === 3 ? [...raw].map((ch) => ch + ch).join("") : raw.slice(0, 6);
  const n = parseInt(full, 16);
  if (Number.isNaN(n)) return "#ffffff";
  const yiq =
    (((n >> 16) & 255) * 299 + ((n >> 8) & 255) * 587 + (n & 255) * 114) / 1000;
  return yiq >= 128 ? "#111111" : "#ffffff";
};
