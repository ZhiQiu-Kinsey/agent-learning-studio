// Adapted from https://reactbits.dev/r/ElectricLogo-TS-TW.json (MIT + Commons Clause).
import type { Texture } from 'ogl';
import type { ElectricLogoProps } from '../ElectricLogo';

export type Rgb = [number, number, number];

export type Settings = Required<Omit<ElectricLogoProps, 'src' | 'className' | 'style' | 'onRender'>> &
  Pick<ElectricLogoProps, 'onRender'>;

export interface Shape {
  field: Float32Array;
  edges: number[];
  width: number;
  height: number;
  pad: number;
  logoWidth: number;
  logoHeight: number;
  glow: Float32Array;
  glowWidth: number;
  glowHeight: number;
  glowOffset: number;
}

export interface Slot {
  shape: Shape | null;
  field: Texture;
  glow: Texture;
}

export interface Placement {
  fit: number;
  ox: number;
  oy: number;
  unit: number;
}

export interface Pulse {
  x: number;
  y: number;
  born: number;
}

export interface Point {
  x: number;
  y: number;
}

export interface Focus {
  x: number;
  y: number;
  radius: number;
}

export interface Spark {
  ax: number;
  ay: number;
  bx: number;
  by: number;
  bow: number;
  seed: number;
  born: number;
  life: number;
}
