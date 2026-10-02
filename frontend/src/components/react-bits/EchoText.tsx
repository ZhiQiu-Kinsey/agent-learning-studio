// Adapted from https://reactbits.dev/r/EchoText-TS-TW.json (MIT + Commons Clause).
// Entrance mode only: trailing echoes of the text slide in, settle onto the
// real text and fade; the frame loop stops once settled (no pointer tracking,
// so nothing runs at rest). Wraps like normal text. Static motion renders the
// text alone. Echo copies are aria-hidden; the front copy is the real text.
import { useEffect, useMemo, useRef, type CSSProperties } from "react";
import { useReducedMotion } from "../../motion";
import "./EchoText.css";

type Direction = "right" | "left" | "up" | "down" | "diagonal";

const vectors: Record<Direction, { x: number; y: number }> = {
  right: { x: 1, y: 0 },
  left: { x: -1, y: 0 },
  up: { x: 0, y: -1 },
  down: { x: 0, y: 1 },
  diagonal: { x: 0.72, y: 0.72 },
};

const clamp = (value: number, min: number, max: number) =>
  Math.min(Math.max(value, min), max);
const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);

export default function EchoText({
  text,
  echoes = 7,
  lag = 0.22,
  offset = 22,
  direction = "right",
  fade = 0.66,
  blur = 2.5,
  tint = "#b98aff",
  duration = 1100,
  className = "",
}: {
  text: string;
  echoes?: number;
  lag?: number;
  offset?: number;
  direction?: Direction;
  fade?: number;
  blur?: number;
  tint?: string;
  duration?: number;
  className?: string;
}) {
  const reduced = useReducedMotion();
  const copies = useRef<Array<HTMLSpanElement | null>>([]);
  const count = reduced ? 0 : clamp(Math.round(echoes), 0, 16);
  const indexes = useMemo(
    () => Array.from({ length: count }, (_, index) => index + 1),
    [count],
  );

  useEffect(() => {
    if (!count) return;
    const vector = vectors[direction];
    const positions = Array.from({ length: count + 1 }, (_, index) => ({
      x: vector.x * offset * (index + 0.35),
      y: vector.y * offset * (index + 0.35),
    }));
    const start = performance.now();
    let activity = 1;
    let frame = 0;
    const render = (now: number) => {
      const progress = clamp((now - start) / duration, 0, 1);
      const rest = 1 - easeOut(progress);
      let separation = 0;
      for (let index = 0; index <= count; index += 1) {
        const copy = copies.current[index];
        const current = positions[index];
        if (!copy) continue;
        const amount = rest * offset * (index + 0.35);
        const lerp = clamp(0.34 / (1 + index * lag * 4.2), 0.018, 0.36);
        current.x += (vector.x * amount - current.x) * lerp;
        current.y += (vector.y * amount - current.y) * lerp;
        copy.style.transform = `translate3d(${current.x.toFixed(2)}px, ${current.y.toFixed(2)}px, 0)`;
        if (index > 0) {
          separation = Math.max(
            separation,
            Math.hypot(current.x - positions[0].x, current.y - positions[0].y),
          );
          copy.style.filter = `blur(${((blur * index) / count).toFixed(2)}px)`;
        }
      }
      const target = Math.max(rest, clamp(separation / (offset * 2.25), 0, 1));
      activity += (target - activity) * 0.18;
      for (let index = 1; index <= count; index += 1) {
        const copy = copies.current[index];
        if (copy) copy.style.opacity = String(Math.pow(fade, index) * activity);
      }
      if (progress < 1 || activity > 0.004) {
        frame = requestAnimationFrame(render);
      } else {
        for (let index = 0; index <= count; index += 1) {
          const copy = copies.current[index];
          if (!copy) continue;
          copy.style.transform = "";
          if (index > 0) copy.style.opacity = "0";
        }
      }
    };
    frame = requestAnimationFrame(render);
    return () => cancelAnimationFrame(frame);
  }, [blur, count, direction, duration, fade, lag, offset, text]);

  if (!count) return <span className={className}>{text}</span>;
  return (
    <span className={`rb-echo ${className}`}>
      {indexes
        .slice()
        .reverse()
        .map((index) => (
          <span
            key={index}
            aria-hidden="true"
            className="rb-echo-copy"
            // Painted from the attribute so the heading's text content (copy,
            // find-in-page, tests) holds the title once.
            data-text={text}
            ref={(element) => {
              copies.current[index] = element;
            }}
            style={
              {
                color: `color-mix(in srgb, ${tint} ${Math.min(72, 18 + index * 6)}%, currentColor)`,
                opacity: 0,
              } as CSSProperties
            }
          />
        ))}
      <span
        className="rb-echo-front"
        ref={(element) => {
          copies.current[0] = element;
        }}
      >
        {text}
      </span>
    </span>
  );
}
