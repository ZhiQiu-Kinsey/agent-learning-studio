import type { TargetAndTransition, Transition } from "motion/react";

/**
 * Props for a scroll-in reveal. With motion reduced the element renders in its
 * shown state, and if the OS preference flips mid-session, content that has not
 * been scrolled to yet snaps to shown instead of staying half-transparent.
 */
export function revealProps(
  reduced: boolean,
  hidden: TargetAndTransition,
  shown: TargetAndTransition,
  transition?: Transition,
) {
  return reduced
    ? { initial: false as const, animate: shown, transition: { duration: 0 } }
    : { initial: hidden, whileInView: shown, transition };
}
