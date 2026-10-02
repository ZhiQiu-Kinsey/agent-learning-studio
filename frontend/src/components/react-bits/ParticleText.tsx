// Adapted from https://reactbits.dev/r/ParticleText-TS-TW.json (MIT + Commons Clause).
// Canvas 2D: the text is sampled into particles that gather once, then drift
// and part around the pointer. The loop runs only while on screen at full
// motion (useMotionBudget "canvas"); otherwise — and for assistive tech — the
// same words render as ordinary text. No glow pass (shadowBlur per particle is
// too costly), particle count capped.
import { useEffect, useRef, type CSSProperties } from "react";
import { useMotionBudget } from "../../motion";
import "./ParticleText.css";

type Rgb = { r: number; g: number; b: number };
type Particle = {
  x: number;
  y: number;
  startX: number;
  startY: number;
  targetX: number;
  targetY: number;
  size: number;
  color: string;
  seed: number;
  depth: number;
};

const hexToRgb = (hex: string): Rgb => {
  const clean = hex.replace("#", "");
  return {
    r: parseInt(clean.slice(0, 2), 16),
    g: parseInt(clean.slice(2, 4), 16),
    b: parseInt(clean.slice(4, 6), 16),
  };
};
const DEFAULT_COLORS = ["#b98aff", "#6d5dfc", "#49dec6"];
const clamp = (value: number, min: number, max: number) =>
  Math.min(Math.max(value, min), max);
const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3);

export default function ParticleText({
  text,
  particleSize = 2,
  density = 3,
  colors = DEFAULT_COLORS,
  scatter = 160,
  gatherDuration = 1500,
  stagger = 380,
  pointerRepel = 34,
  repelRadius = 110,
  idleDrift = 0.6,
  fontWeight = 800,
  className = "",
  style,
}: {
  text: string;
  particleSize?: number;
  density?: number;
  colors?: string[];
  scatter?: number;
  gatherDuration?: number;
  stagger?: number;
  pointerRepel?: number;
  repelRadius?: number;
  idleDrift?: number;
  fontWeight?: number;
  className?: string;
  style?: CSSProperties;
}) {
  const { ref, active } = useMotionBudget<HTMLDivElement>("canvas");
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const textRef = useRef<HTMLSpanElement>(null);
  // Gather only the first time; coming back on screen resumes the drift.
  const gathered = useRef(false);

  useEffect(() => {
    const container = ref.current;
    const canvas = canvasRef.current;
    const label = textRef.current;
    if (!active || !container || !canvas || !label) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    let particles: Particle[] = [];
    let frame = 0;
    let build = 0;
    let gatherStart = 0;
    let gathering = false;
    let width = 0;
    let height = 0;
    const pointer = { active: false, x: 0, y: 0, sx: 0, sy: 0 };
    const palette = colors.map(hexToRgb);

    const render = (now: number) => {
      ctx.clearRect(0, 0, width, height);
      pointer.sx += (pointer.x - pointer.sx) * 0.18;
      pointer.sy += (pointer.y - pointer.sy) * 0.18;
      let complete = true;
      for (const particle of particles) {
        let baseX = particle.targetX;
        let baseY = particle.targetY;
        let progress = 1;
        if (gathering) {
          progress = clamp(
            (now - gatherStart - particle.seed * stagger) / gatherDuration,
            0,
            1,
          );
          const eased = easeOutCubic(progress);
          baseX =
            particle.startX + (particle.targetX - particle.startX) * eased;
          baseY =
            particle.startY + (particle.targetY - particle.startY) * eased;
          if (progress < 1) complete = false;
        } else if (idleDrift > 0) {
          const t = now * 0.001;
          baseX +=
            Math.sin(t * 0.9 + particle.seed * 10) * idleDrift * particle.depth;
          baseY +=
            Math.cos(t * 0.75 + particle.depth * 10) *
            idleDrift *
            particle.depth;
        }
        if (pointer.active) {
          const dx = baseX - pointer.sx;
          const dy = baseY - pointer.sy;
          const distance = Math.hypot(dx, dy);
          if (distance > 0 && distance < repelRadius) {
            const force =
              Math.pow(1 - distance / repelRadius, 2) * pointerRepel;
            baseX += (dx / distance) * force;
            baseY += (dy / distance) * force;
          }
        }
        particle.x += (baseX - particle.x) * 0.22;
        particle.y += (baseY - particle.y) * 0.22;
        ctx.globalAlpha = 0.35 + progress * 0.65;
        ctx.fillStyle = particle.color;
        ctx.fillRect(
          particle.x - particle.size / 2,
          particle.y - particle.size / 2,
          particle.size,
          particle.size,
        );
      }
      ctx.globalAlpha = 1;
      if (gathering && complete) gathering = false;
      frame = requestAnimationFrame(render);
    };

    const sample = async () => {
      const current = ++build;
      const rect = container.getBoundingClientRect();
      width = Math.floor(rect.width);
      height = Math.floor(rect.height);
      if (width <= 0 || height <= 0) return;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      // Same font as the fallback label, so both read identically.
      const computed = getComputedStyle(label);
      let size = parseFloat(computed.fontSize) || 96;
      let font = `${fontWeight} ${size}px ${computed.fontFamily}`;
      await document.fonts?.ready;
      if (current !== build) return;
      const off = document.createElement("canvas");
      const offCtx = off.getContext("2d", { willReadFrequently: true });
      if (!offCtx) return;
      offCtx.font = font;
      let metrics = offCtx.measureText(text);
      if (metrics.width > width * 0.94) {
        size = Math.max(18, size * ((width * 0.94) / metrics.width));
        font = `${fontWeight} ${size}px ${computed.fontFamily}`;
        offCtx.font = font;
        metrics = offCtx.measureText(text);
      }
      const left = Math.ceil(metrics.actualBoundingBoxLeft || 0);
      const right = Math.ceil(metrics.actualBoundingBoxRight || metrics.width);
      const ascent = Math.ceil(metrics.actualBoundingBoxAscent || size * 0.8);
      const descent = Math.ceil(metrics.actualBoundingBoxDescent || size * 0.2);
      const pad = 12;
      off.width = left + right + pad * 2;
      off.height = ascent + descent + pad * 2;
      offCtx.font = font;
      offCtx.fillStyle = "#fff";
      offCtx.fillText(text, pad - left, pad + ascent);
      const data = offCtx.getImageData(0, 0, off.width, off.height).data;
      const targets: { x: number; y: number; alpha: number }[] = [];
      const step = Math.max(2, Math.floor(density));
      for (let y = 0; y < off.height; y += step)
        for (let x = 0; x < off.width; x += step) {
          const alpha = data[(y * off.width + x) * 4 + 3];
          if (alpha > 40)
            targets.push({
              x: width / 2 - off.width / 2 + x,
              y: height / 2 - off.height / 2 + y,
              alpha: alpha / 255,
            });
        }
      const cap = Math.max(
        800,
        Math.min(4200, Math.floor((width * height) / 80)),
      );
      const stride = Math.max(1, Math.ceil(targets.length / cap));
      particles = targets
        .filter((_, index) => index % stride === 0)
        .map((target, index) => {
          const seed = ((index * 9301 + 49297) % 233280) / 233280;
          const depth = 0.45 + (((index * 233 + 97) % 1000) / 1000) * 0.9;
          const along = clamp(
            target.x / Math.max(1, width) + (seed - 0.5) * 0.3,
            0,
            0.999,
          );
          const position = along * (palette.length - 1);
          const from = palette[Math.floor(position)];
          const to =
            palette[Math.min(palette.length - 1, Math.floor(position) + 1)];
          const mix = position - Math.floor(position);
          const color = `rgb(${Math.round(from.r + (to.r - from.r) * mix)}, ${Math.round(from.g + (to.g - from.g) * mix)}, ${Math.round(from.b + (to.b - from.b) * mix)})`;
          const angle = seed * Math.PI * 2;
          const distance = gathered.current
            ? 0
            : scatter * (0.35 + depth * 0.75);
          const startX = target.x + Math.cos(angle) * distance;
          const startY = target.y + Math.sin(angle) * distance;
          return {
            x: startX,
            y: startY,
            startX,
            startY,
            targetX: target.x,
            targetY: target.y,
            size: Math.max(0.8, particleSize * (0.75 + target.alpha * 0.45)),
            color,
            seed,
            depth,
          };
        });
      gathering = !gathered.current;
      gathered.current = true;
      gatherStart = performance.now();
      if (!frame) frame = requestAnimationFrame(render);
    };

    const move = (event: PointerEvent) => {
      const rect = canvas.getBoundingClientRect();
      pointer.x = event.clientX - rect.left;
      pointer.y = event.clientY - rect.top;
      pointer.active = event.pointerType === "mouse";
    };
    const leave = () => {
      pointer.active = false;
    };
    canvas.addEventListener("pointermove", move);
    canvas.addEventListener("pointerleave", leave);
    const observer = new ResizeObserver(() => void sample());
    observer.observe(container);
    return () => {
      build += 1;
      observer.disconnect();
      canvas.removeEventListener("pointermove", move);
      canvas.removeEventListener("pointerleave", leave);
      cancelAnimationFrame(frame);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    };
  }, [
    active,
    colors,
    density,
    fontWeight,
    gatherDuration,
    idleDrift,
    particleSize,
    pointerRepel,
    ref,
    repelRadius,
    scatter,
    stagger,
    text,
  ]);

  return (
    <div
      ref={ref}
      className={`rb-particle-text ${className}`}
      data-live={active || undefined}
      style={style}
    >
      <canvas ref={canvasRef} aria-hidden="true" />
      <span ref={textRef} className="rb-particle-text-label">
        {text}
      </span>
    </div>
  );
}
