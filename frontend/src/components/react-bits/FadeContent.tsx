// Adapted from https://reactbits.dev/r/FadeContent-TS-TW.json (MIT + Commons Clause).
// Rebuilt on motion's whileInView (no GSAP ScrollTrigger per block): blur + rise
// once when scrolled into view. Static motion renders the final state directly.
import { motion, type HTMLMotionProps } from "motion/react";
import type { ReactNode } from "react";
import { useReducedMotion } from "../../motion";

type Tag = "div" | "section" | "li" | "article" | "aside";
const tags = {
  div: motion.div,
  section: motion.section,
  li: motion.li,
  article: motion.article,
  aside: motion.aside,
} as const;

export default function FadeContent({
  as = "div",
  children,
  blur = true,
  distance = 22,
  duration = 0.7,
  delay = 0,
  amount = 0.15,
  ...props
}: {
  as?: Tag;
  children?: ReactNode;
  blur?: boolean;
  distance?: number;
  duration?: number;
  delay?: number;
  /** Fraction of the element that must be visible before it plays. */
  amount?: number;
} & Omit<HTMLMotionProps<"div">, "children">) {
  const reduced = useReducedMotion();
  const Component = tags[as] as typeof motion.div;
  return (
    <Component
      {...props}
      initial={
        reduced
          ? false
          : {
              opacity: 0,
              y: distance,
              filter: blur ? "blur(10px)" : "blur(0px)",
            }
      }
      whileInView={
        reduced ? undefined : { opacity: 1, y: 0, filter: "blur(0px)" }
      }
      viewport={{ once: true, amount }}
      transition={{ duration, delay, ease: [0.16, 1, 0.3, 1] }}
    >
      {children}
    </Component>
  );
}
