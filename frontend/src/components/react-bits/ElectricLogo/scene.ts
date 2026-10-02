// Adapted from https://reactbits.dev/r/ElectricLogo-TS-TW.json (MIT + Commons Clause).
import { Program, Mesh, Triangle, Texture } from 'ogl';
import type { OGLRenderingContext } from 'ogl';
import { ARCS, PULSES } from './constants';
import type { Placement, Settings, Shape, Slot } from './types';
import { vertex, fragment } from './shaders';

/** Two texture slots (morph from/to), the uniform table and the full-screen mesh. */
export const createScene = (gl: OGLRenderingContext) => {
  const gl2 = gl as WebGL2RenderingContext;
  const makeSlot = (): Slot => ({
    shape: null,
    field: new Texture(gl, {
      image: new Float32Array([1000]),
      width: 1,
      height: 1,
      internalFormat: gl2.R16F,
      format: gl2.RED,
      type: gl.FLOAT,
      minFilter: gl.LINEAR,
      magFilter: gl.LINEAR,
      generateMipmaps: false,
      flipY: false,
      unpackAlignment: 1
    }),
    glow: new Texture(gl, {
      image: new Float32Array([0, 0]),
      width: 1,
      height: 1,
      internalFormat: gl2.RG16F,
      format: gl2.RG,
      type: gl.FLOAT,
      minFilter: gl.LINEAR,
      magFilter: gl.LINEAR,
      generateMipmaps: false,
      flipY: false,
      unpackAlignment: 1
    })
  });
  const slots = [makeSlot(), makeSlot()];

  const arcEnds = Array.from({ length: ARCS * 4 }, () => 0);
  const arcShape = Array.from({ length: ARCS * 4 }, () => 0);
  const pulseData = Array.from({ length: PULSES * 4 }, () => 0);
  const uniforms = {
    tFieldFrom: { value: slots[1].field },
    tGlowFrom: { value: slots[1].glow },
    tFieldTo: { value: slots[0].field },
    tGlowTo: { value: slots[0].glow },
    uMapFrom: { value: [0, 0, 1, 0] },
    uSizeFrom: { value: [1, 1, 1, 1] },
    uMapTo: { value: [0, 0, 1, 0] },
    uSizeTo: { value: [1, 1, 1, 1] },
    uMorph: { value: 1 },
    uResolution: { value: [1, 1] },
    uUnit: { value: 1 },
    uTime: { value: 0 },
    uPresence: { value: 0 },
    uHover: { value: [0, 0, 0] },
    uHoverRadius: { value: 120 },
    uPulses: { value: pulseData },
    uPulseBoost: { value: 0 },
    uFlash: { value: 0 },
    uColor: { value: [1, 1, 1] },
    uGlowColor: { value: [0.43, 0.48, 1] },
    uIntensity: { value: 1 },
    uGlow: { value: 1 },
    uThickness: { value: 1.8 },
    uStrands: { value: 3 },
    uBend: { value: 1 },
    uCrackle: { value: 1 },
    uFlicker: { value: 0.4 },
    uFill: { value: 0.5 },
    uInk: { value: 0 },
    uArcEnds: { value: arcEnds },
    uArcShape: { value: arcShape }
  };
  const mesh = new Mesh(gl, {
    geometry: new Triangle(gl),
    program: new Program(gl, { vertex, fragment, uniforms, depthTest: false, depthWrite: false })
  });
  return { slots, arcEnds, arcShape, pulseData, uniforms, mesh };
};

export const loadSlot = (slot: Slot, next: Shape) => {
  slot.shape = next;
  slot.field.image = next.field;
  slot.field.width = next.width;
  slot.field.height = next.height;
  slot.field.needsUpdate = true;
  slot.glow.image = next.glow;
  slot.glow.width = next.glowWidth;
  slot.glow.height = next.glowHeight;
  slot.glow.needsUpdate = true;
};

export const placeShape = (shape: Shape, s: Settings, width: number, height: number): Placement => {
  const fit = Math.max(1e-4, Math.min((width * s.scale) / shape.logoWidth, (height * s.scale) / shape.logoHeight));
  return {
    fit,
    ox: width / 2 - (shape.pad + shape.logoWidth / 2) * fit,
    oy: height / 2 - (shape.pad + shape.logoHeight / 2) * fit,
    unit: (Math.max(shape.logoWidth, shape.logoHeight) * fit) / 100
  };
};
