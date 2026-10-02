// Adapted from https://reactbits.dev/r/WakeSlider-TS-TW.json (MIT + Commons Clause).

export const SETTLE = 9.23;
export const FULL_SPEED = 320;
export const MIN_REACH = 1.5;
export const FLAT = 0.002;

export const clamp = (v: number, lo: number, hi: number) =>
  Math.min(hi, Math.max(lo, v));
export const smoothstep = (s: number) => s * s * (3 - 2 * s);
export const toPct = (v: number, min: number, max: number) =>
  max > min ? ((v - min) / (max - min)) * 100 : 0;
export const snap = (v: number, min: number, max: number, step: number) => {
  if (!(max > min)) return min;
  if (!(step > 0)) return clamp(v, min, max);
  const lastWhole = min + Math.floor(+((max - min) / step).toFixed(6)) * step;
  const grid = clamp(Math.round((v - min) / step) * step + min, min, lastWhole);
  return +(
    lastWhole < max && Math.abs(v - max) <= Math.abs(v - grid) ? max : grid
  ).toFixed(6);
};
