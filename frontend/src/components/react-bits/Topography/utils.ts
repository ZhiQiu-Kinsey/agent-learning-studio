// Adapted from https://reactbits.dev/r/Topography-TS-TW.json (MIT + Commons Clause).
import type { ColorMode } from '../Topography';

export const hexToRgb = (hex: string): [number, number, number] => {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  if (!result) return [1, 1, 1];
  return [parseInt(result[1], 16) / 255, parseInt(result[2], 16) / 255, parseInt(result[3], 16) / 255];
};

export const colorModeToFloat = (mode: ColorMode): number => {
  if (mode === 'uniform') return 1.0;
  if (mode === 'alternating') return 2.0;
  return 0.0;
};

export const CTRL_INDICES = [
  [1, -2, 3, -4],
  [9, -8, 7, -6],
  [5, 2, 5, -5],
  [-1, -3, 8, 9]
];
