// Adapted from https://reactbits.dev/r/SwipeToast-TS-TW.json (MIT + Commons Clause).

export type Phase = "open" | "closing" | "gone";
type Sample = [number, number];
export interface Drag {
  id: number;
  startY: number;
  grab: number | null;
  moved: boolean;
  hist: Sample[];
}

export const EASE_OUT: [number, number, number, number] = [0.23, 1, 0.32, 1];
export const FLICK = 0.11;
export const DEAD_ZONE = 3;
export const RESIST_PX = 24;
export const COLLAPSE_MS = 200;
export const EXIT = 0.7;
export const BURN = [{ transform: "scaleX(1)" }, { transform: "scaleX(0)" }];
export const HAS_STARTING_STYLE =
  typeof window !== "undefined" && "CSSStartingStyleRule" in window;

export const rubberband = (over: number, dim: number, c = 0.55) =>
  (over * dim * c) / (dim + c * Math.abs(over));
export const velocityOf = (hist: Sample[]) => {
  if (hist.length < 2) return 0;
  const [t0, y0] = hist[0];
  const [t1, y1] = hist[hist.length - 1];
  return performance.now() - t1 > 100 ? 0 : (y1 - y0) / Math.max(1, t1 - t0);
};
