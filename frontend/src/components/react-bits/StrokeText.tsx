// Adapted from https://reactbits.dev/r/StrokeText-TS-TW.json (MIT + Commons Clause).
// Draws the outline of each glyph (staggered stroke-dash), then wipes the fill
// in, once on mount. Sized from the parent's computed font so it sits in a
// heading at its natural size; SVG text cannot wrap, so `onOverflow` fires
// when the line is wider than the parent and the caller should fall back.
// Decorative: the SVG is aria-hidden; the caller keeps the real text for
// assistive tech. Static motion is handled by the caller (render plain text).
import {
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { gsap } from "gsap";

interface Box {
  x: number;
  y: number;
  width: number;
  height: number;
}

export default function StrokeText({
  text,
  strokeColor = "#b98aff",
  fillColor = "#ffffff",
  strokeWidth = 1.2,
  drawDuration = 1.3,
  fillDelay = 0.1,
  stagger = 0.045,
  className = "",
  onOverflow,
}: {
  text: string;
  strokeColor?: string;
  fillColor?: string;
  strokeWidth?: number;
  drawDuration?: number;
  fillDelay?: number;
  stagger?: number;
  className?: string;
  onOverflow?: () => void;
}) {
  const rootRef = useRef<HTMLSpanElement>(null);
  const strokeRef = useRef<SVGTextElement>(null);
  const wipeRef = useRef<SVGRectElement>(null);
  const [fontSize, setFontSize] = useState<number | null>(null);
  const [box, setBox] = useState<Box | null>(null);
  const wipeId = `stroke-wipe-${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;
  const characters = useMemo(() => Array.from(text), [text]);

  useLayoutEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    setFontSize(parseFloat(getComputedStyle(root).fontSize) || 40);
  }, [text]);

  useLayoutEffect(() => {
    const node = strokeRef.current;
    const root = rootRef.current;
    if (!node || !root || !fontSize) return;
    let cancelled = false;
    const measure = () => {
      if (cancelled) return;
      let bbox: DOMRect;
      try {
        bbox = node.getBBox();
      } catch {
        return;
      }
      if (!bbox.width) return;
      const pad = Math.max(strokeWidth, fontSize * 0.08);
      const next = {
        x: bbox.x - pad,
        y: bbox.y - pad,
        width: bbox.width + pad * 2,
        height: bbox.height + pad * 2,
      };
      const available = root.parentElement?.clientWidth ?? Infinity;
      if (next.width > available + 1) onOverflow?.();
      setBox((prev) =>
        prev &&
        Math.abs(prev.width - next.width) < 0.5 &&
        Math.abs(prev.y - next.y) < 0.5
          ? prev
          : next,
      );
    };
    measure();
    document.fonts?.ready.then(measure).catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [characters, fontSize, strokeWidth, onOverflow]);

  useEffect(() => {
    const root = rootRef.current;
    if (!root || !box || !fontSize) return;
    const strokes = Array.from(root.querySelectorAll("[data-stroke-char]"));
    const wipe = wipeRef.current;
    const dash = Math.max(fontSize * 7, 200);
    // (also set as attributes on <text> so the first paint is undrawn)
    gsap.set(strokes, { strokeDasharray: dash, strokeDashoffset: dash });
    if (wipe) gsap.set(wipe, { attr: { width: 0 } });
    const timeline = gsap.timeline();
    timeline.to(
      strokes,
      {
        strokeDashoffset: 0,
        duration: drawDuration,
        ease: "power2.out",
        stagger,
      },
      0,
    );
    if (wipe)
      timeline.to(
        wipe,
        {
          attr: { width: box.width },
          duration: Math.max(0.45, drawDuration * 0.55),
          ease: "power2.inOut",
        },
        drawDuration * 0.55 + fillDelay,
      );
    return () => {
      timeline.kill();
    };
  }, [box, fontSize, drawDuration, fillDelay, stagger]);

  const fontStyle = fontSize ? { fontSize: `${fontSize}px` } : undefined;
  const dash = Math.max((fontSize ?? 40) * 7, 200);
  return (
    <span
      ref={rootRef}
      className={`rb-stroke-text ${className}`}
      aria-hidden="true"
    >
      {fontSize && (
        <svg
          width={box ? box.width : 1}
          height={box ? box.height : fontSize * 1.3}
          viewBox={
            box
              ? `${box.x} ${box.y} ${box.width} ${box.height}`
              : `0 ${-fontSize} 1 ${fontSize * 1.3}`
          }
          overflow="visible"
        >
          {box && (
            <defs>
              <clipPath id={wipeId} clipPathUnits="userSpaceOnUse">
                <rect
                  ref={wipeRef}
                  x={box.x}
                  y={box.y}
                  width="0"
                  height={box.height}
                />
              </clipPath>
            </defs>
          )}
          <text
            ref={strokeRef}
            x="0"
            y="0"
            fill="none"
            stroke={strokeColor}
            strokeWidth={strokeWidth}
            strokeLinejoin="round"
            strokeLinecap="round"
            strokeDasharray={dash}
            strokeDashoffset={dash}
            style={fontStyle}
          >
            {characters.map((char, index) => (
              <tspan data-stroke-char key={index}>
                {char}
              </tspan>
            ))}
          </text>
          {box && (
            <text
              x="0"
              y="0"
              fill={fillColor}
              style={fontStyle}
              clipPath={`url(#${wipeId})`}
            >
              {text}
            </text>
          )}
        </svg>
      )}
    </span>
  );
}
