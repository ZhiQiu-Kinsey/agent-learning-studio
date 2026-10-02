import { motionTokens } from "../../motion";

export const easeOut = motionTokens.ease;
/** Chapter tab indicator sliding between tabs. */
export const tabSpring = {
  type: "spring",
  stiffness: 380,
  damping: 32,
} as const;
