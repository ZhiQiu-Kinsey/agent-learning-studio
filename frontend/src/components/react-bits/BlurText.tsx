// React Bits BlurText, adapted from https://reactbits.dev/r/BlurText-TS-CSS.json.
// Copyright (c) 2026 David Haz. See LICENSE.md. Adds semantic text and reduced motion.
import { motion, useInView } from "motion/react";
import { useReducedMotion } from "../../motion";
import { useRef } from "react";

export default function BlurText({
  text,
  className = "",
  delay = 35,
}: {
  text: string;
  className?: string;
  delay?: number;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.1 });
  const reduced = useReducedMotion();
  return (
    <span ref={ref} className={`rb-blur-text ${className}`} aria-label={text}>
      {reduced
        ? text
        : Array.from(text).map((letter, index) => (
            <motion.span
              key={index}
              aria-hidden="true"
              style={{ display: "inline-block" }}
              initial={{ filter: "blur(9px)", opacity: 0, y: 16 }}
              animate={
                inView
                  ? {
                      filter: ["blur(9px)", "blur(3px)", "blur(0px)"],
                      opacity: [0, 0.6, 1],
                      y: [16, -2, 0],
                    }
                  : undefined
              }
              transition={{
                duration: 0.55,
                delay: (index * delay) / 1000,
                times: [0, 0.5, 1],
              }}
            >
              {letter === " " ? "\u00a0" : letter}
            </motion.span>
          ))}
    </span>
  );
}
