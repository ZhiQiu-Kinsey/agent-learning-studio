// Adapted from https://reactbits.dev/r/ElectricLogo-TS-TW.json (MIT + Commons Clause).
import { ARCS, PULSES } from './constants';
import type { Shape, Focus, Spark, Pulse, Placement } from './types';
import { sampleField } from './geometry';

export const spawnArc = (shape: Shape, time: number, focus: Focus | null): Spark | null => {
  const { edges, logoWidth, logoHeight } = shape;
  const count = edges.length / 2;
  if (count < 2) return null;
  const size = Math.max(logoWidth, logoHeight);
  let i = Math.floor(Math.random() * count);
  if (focus) {
    let found = false;
    for (let attempt = 0; attempt < 40 && !found; attempt++) {
      const j = Math.floor(Math.random() * count);
      if (Math.hypot(edges[j * 2] - focus.x, edges[j * 2 + 1] - focus.y) < focus.radius) {
        i = j;
        found = true;
      }
    }
    if (!found) return null;
  }
  const ax = edges[i * 2];
  const ay = edges[i * 2 + 1];
  for (let attempt = 0; attempt < 24; attempt++) {
    const j = Math.floor(Math.random() * count);
    const bx = edges[j * 2];
    const by = edges[j * 2 + 1];
    const len = Math.hypot(bx - ax, by - ay);
    if (len < size * 0.08 || len > size * 0.3) continue;
    const nx = -(by - ay) / len;
    const ny = (bx - ax) / len;
    const bow = len * (0.2 + Math.random() * 0.3);
    const mx = (ax + bx) / 2;
    const my = (ay + by) / 2;
    const left = sampleField(shape, mx + nx * bow, my + ny * bow);
    const right = sampleField(shape, mx - nx * bow, my - ny * bow);
    if (Math.max(left, right) <= 0) continue;
    return {
      ax,
      ay,
      bx,
      by,
      bow: left >= right ? bow : -bow,
      seed: 1 + Math.random() * 60,
      born: time,
      life: 0.35 + Math.random() * 0.45
    };
  }
  return null;
};

/** Packs the live sparks into the arc uniforms, mapped through the current placement. */
export const writeArcs = (
  sparks: Spark[],
  near: Placement,
  time: number,
  presence: number,
  arcEnds: number[],
  arcShape: number[]
) => {
  for (let i = 0; i < ARCS; i++) {
    const o = i * 4;
    const spark = sparks[i];
    if (!spark) {
      arcShape[o + 1] = 0;
      continue;
    }
    const k = (time - spark.born) / spark.life;
    arcEnds[o] = near.ox + spark.ax * near.fit;
    arcEnds[o + 1] = near.oy + spark.ay * near.fit;
    arcEnds[o + 2] = near.ox + spark.bx * near.fit;
    arcEnds[o + 3] = near.oy + spark.by * near.fit;
    arcShape[o] = spark.bow * near.fit;
    arcShape[o + 1] = Math.sin(Math.PI * Math.min(1, Math.max(0, k))) * presence;
    arcShape[o + 2] = spark.seed;
  }
};

/** Drops expired click pulses, packs the rest and returns their combined boost and flash. */
export const writePulses = (pulses: Pulse[], now: number, pulseData: number[]) => {
  let boost = 0;
  let flash = 0;
  for (let i = pulses.length - 1; i >= 0; i--) {
    if ((now - pulses[i].born) / 1000 > 2) pulses.splice(i, 1);
  }
  for (let i = 0; i < PULSES; i++) {
    const o = i * 4;
    const pulse = pulses[i];
    if (!pulse) {
      pulseData[o + 3] = 0;
      continue;
    }
    const age = (now - pulse.born) / 1000;
    pulseData[o] = pulse.x;
    pulseData[o + 1] = pulse.y;
    pulseData[o + 2] = age;
    pulseData[o + 3] = 1;
    boost = Math.max(boost, Math.exp(-age * 1.7));
    flash += Math.exp(-age * 7);
  }
  return { boost, flash };
};
