// Adapted from https://reactbits.dev/r/ElectricBorder-TS-TW.json (MIT + Commons Clause).
// Decoration-only overlay: place it inside a `position: relative` frame and it
// draws the electric outline around that frame. The canvas loop only runs while
// on screen at full motion (useMotionBudget "canvas"); otherwise a still glow
// border remains. Callers render it only for real states (e.g. a live run).
import { useEffect, useRef, type CSSProperties } from "react";
import { useMotionBudget } from "../../motion";

const random = (x: number) => (Math.sin(x * 12.9898) * 43758.5453) % 1;

function noise2D(x: number, y: number) {
  const i = Math.floor(x);
  const j = Math.floor(y);
  const fx = x - i;
  const fy = y - j;
  const a = random(i + j * 57);
  const b = random(i + 1 + j * 57);
  const c = random(i + (j + 1) * 57);
  const d = random(i + 1 + (j + 1) * 57);
  const ux = fx * fx * (3 - 2 * fx);
  const uy = fy * fy * (3 - 2 * fy);
  return (
    a * (1 - ux) * (1 - uy) +
    b * ux * (1 - uy) +
    c * (1 - ux) * uy +
    d * ux * uy
  );
}

function octavedNoise(
  x: number,
  amplitude: number,
  time: number,
  seed: number,
) {
  let y = 0;
  let amp = amplitude;
  let frequency = 10;
  for (let i = 0; i < 8; i++) {
    y +=
      (i === 0 ? 0 : amp) *
      noise2D(frequency * x + seed * 100, time * frequency * 0.3);
    frequency *= 1.6;
    amp *= 0.7;
  }
  return y;
}

function roundedRectPoint(
  t: number,
  left: number,
  top: number,
  width: number,
  height: number,
  radius: number,
) {
  const sw = width - 2 * radius;
  const sh = height - 2 * radius;
  const arc = (Math.PI * radius) / 2;
  const total = 2 * sw + 2 * sh + 4 * arc;
  let d = t * total;
  const corner = (cx: number, cy: number, start: number, p: number) => {
    const angle = start + p * (Math.PI / 2);
    return {
      x: cx + radius * Math.cos(angle),
      y: cy + radius * Math.sin(angle),
    };
  };
  if (d <= sw) return { x: left + radius + d, y: top };
  d -= sw;
  if (d <= arc)
    return corner(left + width - radius, top + radius, -Math.PI / 2, d / arc);
  d -= arc;
  if (d <= sh) return { x: left + width, y: top + radius + d };
  d -= sh;
  if (d <= arc)
    return corner(left + width - radius, top + height - radius, 0, d / arc);
  d -= arc;
  if (d <= sw) return { x: left + width - radius - d, y: top + height };
  d -= sw;
  if (d <= arc)
    return corner(left + radius, top + height - radius, Math.PI / 2, d / arc);
  d -= arc;
  if (d <= sh) return { x: left, y: top + height - radius - d };
  d -= sh;
  return corner(left + radius, top + radius, Math.PI, Math.min(1, d / arc));
}

export default function ElectricBorder({
  color = "#8f7dff",
  speed = 1,
  chaos = 0.1,
  borderRadius = 18,
  className = "",
}: {
  color?: string;
  speed?: number;
  chaos?: number;
  borderRadius?: number;
  className?: string;
}) {
  const { ref, active } = useMotionBudget<HTMLDivElement>("canvas");
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = ref.current;
    if (!active || !canvas || !container) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const offset = 40;
    const displacement = 40;
    let width = 0;
    let height = 0;
    const resize = () => {
      const rect = container.getBoundingClientRect();
      width = rect.width + offset * 2;
      height = rect.height + offset * 2;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(container);
    let time = 0;
    let last = performance.now();
    let frame = 0;
    const draw = (now: number) => {
      time += ((now - last) / 1000) * speed;
      last = now;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, width, height);
      ctx.strokeStyle = color;
      ctx.lineWidth = 1;
      ctx.lineJoin = "round";
      const w = width - offset * 2;
      const h = height - offset * 2;
      const radius = Math.min(borderRadius, Math.min(w, h) / 2);
      const samples = Math.floor((2 * (w + h) + 2 * Math.PI * radius) / 3);
      ctx.beginPath();
      for (let i = 0; i <= samples; i++) {
        const p = i / samples;
        const point = roundedRectPoint(p, offset, offset, w, h, radius);
        const x = point.x + octavedNoise(p * 8, chaos, time, 0) * displacement;
        const y = point.y + octavedNoise(p * 8, chaos, time, 1) * displacement;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.stroke();
      frame = requestAnimationFrame(draw);
    };
    frame = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    };
  }, [active, chaos, color, speed, borderRadius, ref]);

  return (
    <div
      ref={ref}
      className={`rb-electric ${className}`}
      aria-hidden="true"
      style={{ "--electric-color": color, borderRadius } as CSSProperties}
    >
      {active && <canvas ref={canvasRef} className="rb-electric-canvas" />}
      <span className="rb-electric-line" />
      <span className="rb-electric-blur" />
    </div>
  );
}
