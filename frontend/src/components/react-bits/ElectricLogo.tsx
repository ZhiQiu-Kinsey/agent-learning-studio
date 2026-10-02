// Adapted from https://reactbits.dev/r/ElectricLogo-TS-TW.json (MIT + Commons Clause).
// Changes: the reduced-motion media query is gone (callers mount this only at
// full motion and through useMotionBudget("webgl")); the canvas is decorative
// (aria-hidden); everything else is upstream.
import { useEffect, useRef } from 'react';
import type { CSSProperties } from 'react';
import { Renderer } from 'ogl';
import { BOLT, ARCS, PULSES, PIXEL_BUDGET } from './ElectricLogo/constants';
import type { Settings, Shape, Pulse, Point, Focus, Spark } from './ElectricLogo/types';
import { hexToRgb } from './ElectricLogo/geometry';
import { useTracedShape } from './ElectricLogo/useTracedShape';
import { spawnArc, writeArcs, writePulses } from './ElectricLogo/sparks';
import { createScene, loadSlot, placeShape } from './ElectricLogo/scene';

export interface ElectricLogoProps {
  src?: string;
  color?: string;
  glowColor?: string;
  scale?: number;
  intensity?: number;
  glow?: number;
  thickness?: number;
  strands?: number;
  bend?: number;
  crackle?: number;
  arcs?: number;
  flicker?: number;
  fill?: number;
  speed?: number;
  interactive?: boolean;
  cursorIntensity?: number;
  cursorRadius?: number;
  theme?: 'dark' | 'light';
  onRender?: (canvas: HTMLCanvasElement) => void;
  className?: string;
  style?: CSSProperties;
}

const ElectricLogo = ({
  src = BOLT,
  color = '#ecc7ff',
  glowColor = '#ad6dff',
  scale = 0.7,
  intensity = 1,
  glow = 1,
  thickness = 1.5,
  strands = 4,
  bend = 0.6,
  crackle = 1.5,
  arcs = 1,
  flicker = 0.6,
  fill = 0,
  speed = 2.5,
  interactive = true,
  cursorIntensity = 0.75,
  cursorRadius = 100,
  theme = 'dark',
  onRender,
  className = '',
  style
}: ElectricLogoProps) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const settingsRef = useRef<Settings | null>(null);

  useEffect(() => {
    settingsRef.current = {
      color,
      glowColor,
      scale,
      intensity,
      glow,
      thickness,
      strands,
      bend,
      crackle,
      arcs,
      flicker,
      fill,
      speed,
      interactive,
      cursorIntensity,
      cursorRadius,
      theme,
      onRender
    };
  });

  const shapeRef = useTracedShape(src);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;

    const renderer = new Renderer({
      dpr: Math.min(window.devicePixelRatio || 1, 2),
      alpha: true,
      premultipliedAlpha: true,
      antialias: false
    });
    const gl = renderer.gl;
    if (!renderer.isWebgl2) {
      gl.getExtension('WEBGL_lose_context')?.loseContext();
      return undefined;
    }
    gl.clearColor(0, 0, 0, 0);
    const canvas = gl.canvas;
    canvas.style.display = 'block';
    canvas.style.width = '100%';
    canvas.style.height = '100%';
    container.appendChild(canvas);

    const { slots, arcEnds, arcShape, pulseData, uniforms, mesh } = createScene(gl);

    // Callers only mount this at full motion (see header).
    const reducedMotion = false;
    const pointer = { x: 0, y: 0, over: false };
    const hover = { x: 0, y: 0, vx: 0, vy: 0, power: 0 };
    const sparks: Spark[] = [];
    const pulses: Pulse[] = [];
    let target = 0;
    let pending: Shape | null = null;
    let morph = 1;
    let burst: Point | null = null;
    let progress = 0;
    let ink = 0;
    const hues = [
      [1, 1, 1],
      [1, 1, 1]
    ];
    let settled = false;
    let time = 0;
    let width = 1;
    let height = 1;
    let raf = 0;
    let last = performance.now();
    let visible = true;

    const place = (shape: Shape, s: Settings) => placeShape(shape, s, width, height);

    const resize = () => {
      width = Math.max(1, container.clientWidth);
      height = Math.max(1, container.clientHeight);
      renderer.dpr = Math.min(window.devicePixelRatio || 1, 2, Math.sqrt(PIXEL_BUDGET / (width * height)));
      renderer.setSize(width, height);
      uniforms.uResolution.value = [width, height];
    };

    const frame = (now: number) => {
      raf = 0;
      const s = settingsRef.current;
      const dt = Math.min(0.05, Math.max(0, (now - last) / 1000));
      last = now;

      const incoming = shapeRef.current;
      if (incoming && incoming !== slots[target].shape) pending = incoming;
      if (pending && morph >= 1) {
        if (slots[target].shape) {
          target = 1 - target;
          morph = 0;
          sparks.length = 0;
        }
        loadSlot(slots[target], pending);
        pending = null;
      }
      if (morph < 1) morph = Math.min(1, morph + dt / (pending ? 0.3 : 1.6));

      const to = slots[target].shape;
      const from = morph < 1 ? slots[1 - target].shape : null;
      if (to) progress = Math.min(1, progress + dt / 1.4);
      const presence = progress * progress * (3 - 2 * progress);

      if (to && s) {
        const near = place(to, s);
        const far = from ? place(from, s) : near;
        const blend = morph * morph * (3 - 2 * morph);
        const unit = far.unit + (near.unit - far.unit) * blend;

        const engaged = s.interactive && pointer.over;
        if (engaged && hover.power < 0.01) {
          hover.x = pointer.x;
          hover.y = pointer.y;
          hover.vx = 0;
          hover.vy = 0;
        }
        hover.vx += ((pointer.x - hover.x) * 120 - hover.vx * 19) * dt;
        hover.vy += ((pointer.y - hover.y) * 120 - hover.vy * 19) * dt;
        hover.x += hover.vx * dt;
        hover.y += hover.vy * dt;
        hover.power += ((engaged ? 1 : 0) - hover.power) * (1 - Math.exp(-dt / (engaged ? 0.3 : 0.55)));

        const motion = reducedMotion ? 0.2 : 1;
        time += dt * s.speed * motion;

        for (let i = sparks.length - 1; i >= 0; i--) {
          if (time - sparks[i].born > sparks[i].life) sparks.splice(i, 1);
        }
        const focus = (spot: Point): Focus => ({
          x: (spot.x - near.ox) / near.fit,
          y: (spot.y - near.oy) / near.fit,
          radius: Math.max(1, s.cursorRadius) / near.fit
        });
        if (burst && morph >= 1 && s.arcs > 0) {
          for (let i = 0; i < 3 && sparks.length < ARCS; i++) {
            const spark = spawnArc(to, time, focus(burst));
            if (spark) sparks.push(spark);
          }
        }
        burst = null;
        if (!reducedMotion && presence > 0.8 && morph >= 1 && sparks.length < ARCS) {
          const chance = dt * s.speed * s.arcs;
          if (Math.random() < chance * 6 * hover.power * s.cursorIntensity) {
            const spark = spawnArc(to, time, focus(hover));
            if (spark) sparks.push(spark);
          } else if (Math.random() < chance * 2.2) {
            const spark = spawnArc(to, time, null);
            if (spark) sparks.push(spark);
          }
        }

        writeArcs(sparks, near, time, presence, arcEnds, arcShape);
        const { boost, flash } = writePulses(pulses, now, pulseData);

        const fromSlot = slots[1 - target];
        uniforms.tFieldTo.value = slots[target].field;
        uniforms.tGlowTo.value = slots[target].glow;
        uniforms.tFieldFrom.value = fromSlot.field;
        uniforms.tGlowFrom.value = fromSlot.glow;
        uniforms.uMapTo.value = [near.ox, near.oy, near.fit, to.glowOffset];
        uniforms.uSizeTo.value = [to.width, to.height, to.glowWidth, to.glowHeight];
        if (from) {
          uniforms.uMapFrom.value = [far.ox, far.oy, far.fit, from.glowOffset];
          uniforms.uSizeFrom.value = [from.width, from.height, from.glowWidth, from.glowHeight];
        }
        uniforms.uMorph.value = morph;
        uniforms.uUnit.value = unit;
        uniforms.uTime.value = time;
        uniforms.uPresence.value = presence;
        uniforms.uHover.value = [hover.x, hover.y, hover.power * Math.max(0, s.cursorIntensity)];
        uniforms.uHoverRadius.value = Math.max(1, s.cursorRadius);
        uniforms.uPulseBoost.value = boost;
        uniforms.uFlash.value = flash;
        const targets = [hexToRgb(s.color), hexToRgb(s.glowColor)];
        const shift = settled ? 1 - Math.exp(-dt / 0.35) : 1;
        settled = true;
        for (let i = 0; i < 2; i++) {
          for (let c = 0; c < 3; c++) hues[i][c] += (targets[i][c] - hues[i][c]) * shift;
        }
        uniforms.uColor.value = hues[0].slice();
        uniforms.uGlowColor.value = hues[1].slice();
        uniforms.uIntensity.value = s.intensity;
        uniforms.uGlow.value = s.glow;
        uniforms.uThickness.value = s.thickness;
        uniforms.uStrands.value = Math.max(1, Math.min(6, Math.round(s.strands)));
        uniforms.uBend.value = s.bend;
        uniforms.uCrackle.value = s.crackle;
        uniforms.uFlicker.value = reducedMotion ? 0 : s.flicker;
        ink += ((s.theme === 'light' ? 1 : 0) - ink) * (1 - Math.exp(-dt / 0.25));
        uniforms.uFill.value = s.fill;
        uniforms.uInk.value = ink;
        renderer.render({ scene: mesh });
        s.onRender?.(canvas);
      }

      if (visible) raf = requestAnimationFrame(frame);
    };

    const start = () => {
      if (raf || !visible) return;
      last = performance.now();
      raf = requestAnimationFrame(frame);
    };

    const onMove = (e: PointerEvent) => {
      const rect = container.getBoundingClientRect();
      pointer.x = e.clientX - rect.left;
      pointer.y = e.clientY - rect.top;
      pointer.over = true;
    };
    const onDown = (e: PointerEvent) => {
      onMove(e);
      if (!settingsRef.current?.interactive || reducedMotion) return;
      pulses.push({ x: pointer.x, y: pointer.y, born: performance.now() });
      if (pulses.length > PULSES) pulses.shift();
      burst = { x: pointer.x, y: pointer.y };
    };
    const onLeave = () => {
      pointer.over = false;
    };
    container.addEventListener('pointermove', onMove);
    container.addEventListener('pointerdown', onDown);
    container.addEventListener('pointerleave', onLeave);
    container.addEventListener('pointercancel', onLeave);

    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(container);
    const intersectionObserver = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      start();
    });
    intersectionObserver.observe(container);

    resize();
    start();

    return () => {
      visible = false;
      cancelAnimationFrame(raf);
      resizeObserver.disconnect();
      intersectionObserver.disconnect();
      container.removeEventListener('pointermove', onMove);
      container.removeEventListener('pointerdown', onDown);
      container.removeEventListener('pointerleave', onLeave);
      container.removeEventListener('pointercancel', onLeave);
      gl.getExtension('WEBGL_lose_context')?.loseContext();
      if (canvas.parentNode) canvas.parentNode.removeChild(canvas);
    };
  }, []);

  return (
    <div
      ref={containerRef}
      aria-hidden="true"
      className={`relative w-full h-full overflow-hidden ${className}`.trim()}
      style={style}
    />
  );
};

export default ElectricLogo;
