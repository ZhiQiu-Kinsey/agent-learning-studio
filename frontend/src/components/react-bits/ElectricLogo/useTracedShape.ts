// Adapted from https://reactbits.dev/r/ElectricLogo-TS-TW.json (MIT + Commons Clause).
import { useEffect, useRef } from 'react';
import { BOLT } from './constants';
import { traceShape } from './geometry';
import type { Shape } from './types';

/** Rasterises and traces the logo image; the frame loop picks the latest shape up from the ref. */
export const useTracedShape = (src: string) => {
  const shapeRef = useRef<Shape | null>(null);

  useEffect(() => {
    let alive = true;
    const image = new Image();
    image.crossOrigin = 'anonymous';
    image.decoding = 'async';
    image.onload = () => {
      if (!alive) return;
      let traced: Shape | null = null;
      try {
        traced = traceShape(image);
      } catch {
        traced = null;
      }
      if (traced) shapeRef.current = traced;
    };
    image.src = src || BOLT;
    return () => {
      alive = false;
      image.onload = null;
    };
  }, [src]);

  return shapeRef;
};
