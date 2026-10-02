// Adapted from https://reactbits.dev/r/ClickSpark-TS-TW.json (MIT + Commons Clause).
// One-shot celebration: instead of sparking on every click, it bursts once when
// mounted. Mount it only for a real outcome (e.g. the learner's answer was
// correct). Nothing is drawn at static motion. Parent needs position: relative.
import { useEffect, useRef } from "react";
import { useReducedMotion } from "../../motion";

export default function SparkBurst({
  colors = ["#6fd39a", "#49dec6", "#b98aff", "#ffd36e"],
  count = 14,
  radius = 46,
  size = 9,
  duration = 700,
  className = "",
}: {
  colors?: string[];
  count?: number;
  radius?: number;
  size?: number;
  duration?: number;
  className?: string;
}) {
  const reduced = useReducedMotion();
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (reduced || !canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const box = radius * 2 + size * 4;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = box * dpr;
    canvas.height = box * dpr;
    canvas.style.width = `${box}px`;
    canvas.style.height = `${box}px`;
    const sparks = Array.from({ length: count }, (_, i) => ({
      angle: (2 * Math.PI * i) / count + (i % 2 ? 0.18 : -0.12),
      reach: i % 2 ? 1 : 0.68,
      color: colors[i % colors.length],
    }));
    const start = performance.now();
    let frame = 0;
    const draw = (now: number) => {
      const progress = Math.min(1, (now - start) / duration);
      const eased = progress * (2 - progress);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, box, box);
      ctx.lineWidth = 2;
      ctx.lineCap = "round";
      for (const spark of sparks) {
        const distance = eased * radius * spark.reach + size * 0.6;
        const length = size * (1 - eased);
        const cx = box / 2;
        const cy = box / 2;
        ctx.strokeStyle = spark.color;
        ctx.globalAlpha = 1 - progress * 0.6;
        ctx.beginPath();
        ctx.moveTo(
          cx + distance * Math.cos(spark.angle),
          cy + distance * Math.sin(spark.angle),
        );
        ctx.lineTo(
          cx + (distance + length) * Math.cos(spark.angle),
          cy + (distance + length) * Math.sin(spark.angle),
        );
        ctx.stroke();
      }
      if (progress < 1) frame = requestAnimationFrame(draw);
      else ctx.clearRect(0, 0, box, box);
    };
    frame = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frame);
    // Fires once per mount by design.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reduced]);

  if (reduced) return null;
  return (
    <canvas
      ref={canvasRef}
      className={`rb-spark-burst ${className}`}
      aria-hidden="true"
    />
  );
}
