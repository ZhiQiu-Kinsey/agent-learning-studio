import type { ReactNode } from "react";
import { motion } from "motion/react";
import { useReducedMotion } from "../../motion";
import { easeOut } from "./transitions";

/** A view arriving after a switch: rises out of a soft blur. */
export function ViewPanel({ children }: { children: ReactNode }) {
  const reduced = useReducedMotion();
  return (
    <motion.div
      className="curriculum-view-panel"
      initial={reduced ? false : { opacity: 0, y: 14, filter: "blur(8px)" }}
      // Drop the filter afterwards: even blur(0) creates a containing block.
      animate={{
        opacity: 1,
        y: 0,
        filter: "blur(0px)",
        transitionEnd: { filter: "none" },
      }}
      transition={{ duration: 0.45, ease: easeOut }}
    >
      {children}
    </motion.div>
  );
}
