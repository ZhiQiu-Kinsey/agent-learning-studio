// Adapted from https://reactbits.dev/r/MoltenMetal-TS-TW.json (MIT + Commons Clause).
import type { MoltenMetalColorMode } from '../MoltenMetal';

export const hexToRgb = (hex: string): [number, number, number] => {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  if (!result) return [1, 1, 1];
  return [parseInt(result[1], 16) / 255, parseInt(result[2], 16) / 255, parseInt(result[3], 16) / 255];
};

export const colorModeToFloat = (mode: MoltenMetalColorMode): number => (mode === 'ember' ? 1 : mode === 'frost' ? 2 : 0);
