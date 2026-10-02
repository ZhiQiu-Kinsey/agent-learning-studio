// Adapted from https://reactbits.dev/r/RubberSegment-TS-TW.json (MIT + Commons Clause, see LICENSE.md).
import type { RubberSegmentSize } from "../RubberSegment";

export type Slot = { l: number; r: number };
type Sample = [number, number];
export type Drag = {
  id: number;
  x0: number;
  slot: number;
  onThumb: boolean;
  live: boolean;
  offset: number;
  w: number;
  hist: Sample[];
};

export const EASE_OUT: [number, number, number, number] = [0.23, 1, 0.32, 1];
export const SPRING_UI = { type: "spring" as const, duration: 0.3, bounce: 0 };
export const SPRING_MOMENTUM = {
  type: "spring" as const,
  duration: 0.4,
  bounce: 0.2,
};
export const SPRING_RELAX = {
  type: "spring" as const,
  duration: 0.16,
  bounce: 0,
};
export const DILATE = 0.19;
export const HANDOFF = 0.15;
export const FLICK = 110;
export const MAX_VELOCITY = 2000;
export const DEADZONE = 4;
export const SLOP = 10;
const RUBBER = 0.55;
export const SIZES: Record<
  RubberSegmentSize,
  { height: number; font: number; pad: number; min: number }
> = {
  sm: { height: 28, font: 12, pad: 10, min: 36 },
  md: { height: 36, font: 13, pad: 14, min: 44 },
  lg: { height: 44, font: 14, pad: 18, min: 48 },
};

export const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value));
export const rubber = (over: number, dim: number) =>
  (over * dim * RUBBER) / (dim + RUBBER * Math.abs(over));
export const project = (v: number, glide: number) => {
  const d = 1 - 0.1 * Math.pow(0.05, glide / 100);
  return ((v / 1000) * d) / (1 - d);
};
export const velocityOf = (hist: Sample[], now: number) => {
  const recent = hist.filter(([t]) => now - t <= 100);
  if (recent.length < 2) return 0;
  const [t0, x0] = recent[0];
  const [t1, x1] = recent[recent.length - 1];
  return t1 - t0 >= 8 ? ((x1 - x0) / (t1 - t0)) * 1000 : 0;
};
export const nearestSlot = (slots: Slot[], x: number) => {
  let best = 0;
  for (let i = 1; i < slots.length; i++) {
    if (
      Math.abs((slots[i].l + slots[i].r) / 2 - x) <
      Math.abs((slots[best].l + slots[best].r) / 2 - x)
    )
      best = i;
  }
  return best;
};
