// Adapted from https://reactbits.dev/r/ClickSpark-TS-TW.json (MIT + Commons Clause).
// Copyright (c) 2026 David Haz. See LICENSE.md.
// App-wide variant: one fixed, viewport-sized canvas instead of a canvas the
// size of the wrapped content, so long pages never allocate huge bitmaps. The
// spark colour is read from a CSS custom property at click time (follows the
// theme). Nothing is drawn in static motion; the loop runs only while sparks live.
import { useEffect, useRef, type RefObject } from "react";
import { useReducedMotion } from "../../motion";

interface Spark {
  x: number;
  y: number;
  angle: number;
  start: number;
  color: string;
}

export default function ClickSparkLayer({
  scope,
  colorVar = "--spark",
  sparkSize = 9,
  sparkRadius = 18,
  sparkCount = 8,
  duration = 420,
  extraScale = 1,
}: {
  /** Only clicks inside this element spark. */
  scope: RefObject<HTMLElement | null>;
  colorVar?: string;
  sparkSize?: number;
  sparkRadius?: number;
  sparkCount?: number;
  duration?: number;
  extraScale?: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const reduced = useReducedMotion();

  useEffect(() => {
    const canvas = canvasRef.current;
    const root = scope.current;
    if (reduced || !canvas || !root) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    let sparks: Spark[] = [];
    let frame = 0;
    let dpr = 1;

    const resize = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(window.innerWidth * dpr);
      canvas.height = Math.round(window.innerHeight * dpr);
    };
    resize();

    const draw = (now: number) => {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      sparks = sparks.filter((spark) => {
        const elapsed = now - spark.start;
        if (elapsed >= duration) return false;
        const t = elapsed / duration;
        const eased = t * (2 - t);
        const distance = eased * sparkRadius * extraScale;
        const length = sparkSize * (1 - eased);
        const cos = Math.cos(spark.angle);
        const sin = Math.sin(spark.angle);
        ctx.strokeStyle = spark.color;
        ctx.globalAlpha = 1 - t * 0.6;
        ctx.lineWidth = 2;
        ctx.lineCap = "round";
        ctx.beginPath();
        ctx.moveTo(spark.x + distance * cos, spark.y + distance * sin);
        ctx.lineTo(
          spark.x + (distance + length) * cos,
          spark.y + (distance + length) * sin,
        );
        ctx.stroke();
        return true;
      });
      ctx.globalAlpha = 1;
      frame = sparks.length ? requestAnimationFrame(draw) : 0;
    };

    const onClick = (event: MouseEvent) => {
      // Keyboard activation reports detail 0: no sparks without a pointer.
      if (!sparkCount || event.detail === 0) return;
      const color =
        getComputedStyle(root).getPropertyValue(colorVar).trim() || "#8f7dff";
      const start = performance.now();
      for (let i = 0; i < sparkCount; i++)
        sparks.push({
          x: event.clientX,
          y: event.clientY,
          angle: (2 * Math.PI * i) / sparkCount,
          start,
          color,
        });
      if (!frame) frame = requestAnimationFrame(draw);
    };

    root.addEventListener("click", onClick);
    window.addEventListener("resize", resize);
    return () => {
      root.removeEventListener("click", onClick);
      window.removeEventListener("resize", resize);
      cancelAnimationFrame(frame);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    };
  }, [
    reduced,
    scope,
    colorVar,
    sparkSize,
    sparkRadius,
    sparkCount,
    duration,
    extraScale,
  ]);

  if (reduced) return null;
  return (
    <canvas ref={canvasRef} className="click-spark-layer" aria-hidden="true" />
  );
}
