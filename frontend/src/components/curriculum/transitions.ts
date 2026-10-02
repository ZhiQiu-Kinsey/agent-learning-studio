import { motionTokens } from "../../motion";

/** Spring shared by the map's sliding indicators (view switch, filter chips). */
export const pillSpring = {
  type: "spring",
  stiffness: 420,
  damping: 34,
  mass: 0.8,
} as const;

export const easeOut = motionTokens.ease;
