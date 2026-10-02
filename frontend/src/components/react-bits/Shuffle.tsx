// Adapted from https://reactbits.dev/r/Shuffle-TS-TW.json (MIT + Commons Clause).
// Lightweight take on the same effect without GSAP SplitText: each character
// is a slot whose strip of random glyphs slides once into the real character
// when the text first enters the viewport. Latin eyebrows only; anything else
// (or static motion) renders as plain text. Screen readers get the plain text.
import { useMemo, useRef, type CSSProperties } from "react";
import { useInView } from "motion/react";
import { useReducedMotion } from "../../motion";
import "./Shuffle.css";

const CHARSET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/#*+";
const LATIN = /^[\x20-\x7E]+$/;

export default function Shuffle({
  text,
  className = "",
  shuffleTimes = 3,
  stagger = 0.028,
  duration = 0.5,
}: {
  text: string;
  className?: string;
  shuffleTimes?: number;
  stagger?: number;
  duration?: number;
}) {
  const reduced = useReducedMotion();
  const ref = useRef<HTMLSpanElement>(null);
  const play = useInView(ref, { once: true, margin: "0px 0px -8% 0px" });
  const latin = LATIN.test(text);
  const strips = useMemo(
    () =>
      Array.from(text).map((char) =>
        char === " "
          ? null
          : [
              ...Array.from(
                { length: shuffleTimes },
                () => CHARSET[Math.floor(Math.random() * CHARSET.length)],
              ),
              char,
            ],
      ),
    [text, shuffleTimes],
  );
  if (reduced || !latin) return <span className={className}>{text}</span>;
  return (
    <span
      ref={ref}
      className={`rb-shuffle ${className}`}
      data-play={play || undefined}
    >
      <span className="sr-only">{text}</span>
      <span aria-hidden="true">
        {strips.map((strip, index) =>
          strip ? (
            <span
              key={index}
              className="rb-shuffle-slot"
              style={
                {
                  "--n": strip.length - 1,
                  "--delay": `${index * stagger}s`,
                  "--duration": `${duration}s`,
                } as CSSProperties
              }
            >
              <span className="rb-shuffle-ghost">
                {strip[strip.length - 1]}
              </span>
              <span className="rb-shuffle-strip">
                {strip.map((glyph, i) => (
                  <span key={i}>{glyph}</span>
                ))}
              </span>
            </span>
          ) : (
            <span key={index}> </span>
          ),
        )}
      </span>
    </span>
  );
}
