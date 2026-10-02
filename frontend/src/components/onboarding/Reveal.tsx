import type { ReactNode } from "react";
import { motion } from "motion/react";
import { revealProps, useReducedMotion } from "../../motion";
import { easeOut } from "./transitions";

/** Scroll reveal for reading blocks; static motion shows them as they are. */
export function Reveal({
  children,
  className,
  delay = 0,
  as = "div",
  ...rest
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
  as?: "div" | "section";
  [data: `data-${string}`]: string | undefined;
}) {
  const reduced = useReducedMotion();
  const Tag = as === "section" ? motion.section : motion.div;
  return (
    <Tag
      className={className}
      {...rest}
      {...revealProps(
        reduced,
        { opacity: 0, y: 22, filter: "blur(6px)" },
        {
          opacity: 1,
          y: 0,
          filter: "blur(0px)",
          transitionEnd: { filter: "none" },
        },
        { duration: 0.6, delay, ease: easeOut },
      )}
      viewport={{ once: true, amount: 0.12 }}
    >
      {children}
    </Tag>
  );
}
