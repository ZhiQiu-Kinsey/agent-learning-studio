// Adapted from https://reactbits.dev/r/GooeyNav-TS-TW.json (MIT + Commons Clause).
// Decoration layer for an existing tab list (keeps its tab semantics, keyboard
// handling and test ids): drop it inside the tablist and it tracks the active
// `[role="tab"]`. On each real switch a burst of droplets leaves the active tab
// and melts back into it through an SVG goo filter (works on light and dark
// surfaces, unlike the upstream contrast/blend trick). Static motion: the blob
// just sits under the active tab, no particles.
import { useEffect, useId, useLayoutEffect, useRef } from "react";
import { useMotionBudget } from "../../motion";
import "./GooeyNav.css";

const BRAND = ["#b98aff", "#6d5dfc", "#49dec6", "#ff9473"];
const DISTANCES: [number, number] = [64, 8];
const noise = (n = 1) => n / 2 - Math.random() * n;

export default function GooeyNav({
  activeKey,
  particleCount = 12,
  particleDistances = DISTANCES,
  particleR = 90,
  animationTime = 560,
  timeVariance = 260,
  colors = BRAND,
  className = "",
}: {
  activeKey: string;
  particleCount?: number;
  particleDistances?: [number, number];
  particleR?: number;
  animationTime?: number;
  timeVariance?: number;
  colors?: string[];
  className?: string;
}) {
  const { ref, granted } = useMotionBudget<HTMLSpanElement>("css");
  const blobRef = useRef<HTMLSpanElement>(null);
  const burstRef = useRef<HTMLSpanElement>(null);
  const previous = useRef<string | null>(null);
  const timers = useRef<number[]>([]);
  const filterId = `gooey-${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;

  // Keep the blob under the active tab.
  useLayoutEffect(() => {
    const root = ref.current;
    const list = root?.parentElement;
    if (!root || !list) return;
    const place = () => {
      const active = list.querySelector<HTMLElement>(
        '[role="tab"][data-state="active"]',
      );
      const blob = blobRef.current;
      const burst = burstRef.current;
      if (!active || !blob || !burst) return;
      const parent = root.getBoundingClientRect();
      const box = active.getBoundingClientRect();
      const style = {
        left: `${box.left - parent.left}px`,
        top: `${box.top - parent.top}px`,
        width: `${box.width}px`,
        height: `${box.height}px`,
      };
      Object.assign(blob.style, style);
      Object.assign(burst.style, style);
    };
    place();
    const observer = new ResizeObserver(place);
    observer.observe(list);
    return () => observer.disconnect();
  }, [activeKey, ref]);

  // Burst only on a real switch (not on first render).
  useEffect(() => {
    const from = previous.current;
    previous.current = activeKey;
    const burst = burstRef.current;
    if (from === null || from === activeKey || !granted || !burst) return;
    burst.replaceChildren();
    for (let i = 0; i < particleCount; i += 1) {
      const time = animationTime * 2 + noise(timeVariance * 2);
      const angle =
        ((360 + noise(8)) / particleCount) *
        (particleCount - i) *
        (Math.PI / 180);
      const [far, near] = particleDistances;
      const end = near + noise(7);
      const rotate = noise(particleR / 10);
      const particle = document.createElement("span");
      particle.className = "rb-gooey-particle";
      particle.style.setProperty("--start-x", `${far * Math.cos(angle)}px`);
      particle.style.setProperty("--start-y", `${far * Math.sin(angle)}px`);
      particle.style.setProperty("--end-x", `${end * Math.cos(angle)}px`);
      particle.style.setProperty("--end-y", `${end * Math.sin(angle)}px`);
      particle.style.setProperty("--time", `${time}ms`);
      particle.style.setProperty("--scale", `${1 + noise(0.2)}`);
      particle.style.setProperty("--color", colors[i % colors.length]);
      particle.style.setProperty(
        "--rotate",
        `${rotate > 0 ? (rotate + particleR / 20) * 10 : (rotate - particleR / 20) * 10}deg`,
      );
      const point = document.createElement("span");
      point.className = "rb-gooey-point";
      particle.appendChild(point);
      burst.appendChild(particle);
      timers.current.push(window.setTimeout(() => particle.remove(), time));
    }
  }, [
    activeKey,
    animationTime,
    colors,
    granted,
    particleCount,
    particleDistances,
    particleR,
    timeVariance,
  ]);

  useEffect(
    () => () => {
      timers.current.forEach((timer) => window.clearTimeout(timer));
    },
    [],
  );

  return (
    <span
      ref={ref}
      className={`rb-gooey ${className}`}
      aria-hidden="true"
      style={{ filter: `url(#${filterId})` }}
    >
      <svg className="rb-gooey-defs" width="0" height="0">
        <filter id={filterId}>
          <feGaussianBlur in="SourceGraphic" stdDeviation="5" result="blur" />
          <feColorMatrix
            in="blur"
            mode="matrix"
            values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 22 -9"
            result="goo"
          />
          <feComposite in="SourceGraphic" in2="goo" operator="atop" />
        </filter>
      </svg>
      <span ref={blobRef} className="rb-gooey-blob" />
      <span ref={burstRef} className="rb-gooey-burst" />
    </span>
  );
}
