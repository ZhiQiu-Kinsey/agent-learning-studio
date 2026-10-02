// Adapted from https://reactbits.dev/r/WebThreads-TS-TW.json (MIT + Commons Clause).
import type { FanMode } from '../WebThreads';

export const hexToRgb = (hex: string): [number, number, number] => {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  if (!result) return [1, 1, 1];
  return [parseInt(result[1], 16) / 255, parseInt(result[2], 16) / 255, parseInt(result[3], 16) / 255];
};

export const FAN_MODE: Record<FanMode, number> = { center: 0, left: 1, right: 2 };
