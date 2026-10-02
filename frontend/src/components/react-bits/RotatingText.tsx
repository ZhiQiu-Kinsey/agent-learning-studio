// Adapted from https://reactbits.dev/r/RotatingText-TS-TW.json (MIT + Commons Clause).
// Rotates only on screen at full motion; static motion shows every phrase at once,
// and screen readers always get the full list instead of the current word.
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";
import { useMotionBudget } from "../../motion";

export default function RotatingText({
  texts,
  interval = 2600,
  staggerDuration = 0.025,
  separator = " · ",
  className = "",
}: {
  texts: string[];
  interval?: number;
  staggerDuration?: number;
  separator?: string;
  className?: string;
}) {
  const { ref, active, reduced } = useMotionBudget<HTMLSpanElement>();
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (!active || texts.length < 2) return;
    const id = window.setInterval(
      () => setIndex((value) => (value + 1) % texts.length),
      interval,
    );
    return () => window.clearInterval(id);
  }, [active, interval, texts.length]);

  if (reduced || texts.length < 2)
    return (
      <span ref={ref} className={`rb-rotating-text is-static ${className}`}>
        {texts.join(separator)}
      </span>
    );

  const current = texts[index % texts.length] ?? "";
  return (
    <motion.span
      ref={ref}
      layout
      transition={{ type: "spring", damping: 30, stiffness: 300 }}
      className={`rb-rotating-text ${className}`}
    >
      <span className="sr-only">{texts.join(separator)}</span>
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={index}
          layout
          className="rb-rotating-word"
          aria-hidden="true"
        >
          {Array.from(current).map((char, charIndex) => (
            <motion.span
              key={charIndex}
              className="rb-rotating-char"
              initial={{ y: "110%", opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ y: "-120%", opacity: 0 }}
              transition={{
                type: "spring",
                damping: 26,
                stiffness: 320,
                delay: charIndex * staggerDuration,
              }}
            >
              {char === " " ? " " : char}
            </motion.span>
          ))}
        </motion.span>
      </AnimatePresence>
    </motion.span>
  );
}
