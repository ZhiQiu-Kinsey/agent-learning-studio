import { useEffect, useState } from "react";

/**
 * A counter that ticks every `interval` ms while `active`, for highlights that
 * step through a short sequence. Pass `useMotionBudget().active` so it only
 * runs on screen at full motion.
 */
export function useBeat(active: boolean, interval = 1400) {
  const [beat, setBeat] = useState(0);
  useEffect(() => {
    if (!active) return;
    const id = window.setInterval(
      () => setBeat((value) => value + 1),
      interval,
    );
    return () => window.clearInterval(id);
  }, [active, interval]);
  return beat;
}
