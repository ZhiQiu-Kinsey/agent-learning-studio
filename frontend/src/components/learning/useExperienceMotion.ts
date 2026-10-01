import { useEffect, useRef, useState } from "react";
import { useInView } from "motion/react";
import { useMotionPreference as useReducedMotion } from "../../hooks/useMotionPreference";

/** Shared motion budget: no recurring work outside the viewport or hidden tab. */
export function useExperienceMotion<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const inView = useInView(ref, { margin: "20px" });
  const reduced = useReducedMotion();
  const [pageVisible, setPageVisible] = useState(() => !document.hidden);
  useEffect(() => {
    const update = () => setPageVisible(!document.hidden);
    document.addEventListener("visibilitychange", update);
    return () => document.removeEventListener("visibilitychange", update);
  }, []);
  return {
    ref,
    active: inView && pageVisible && !reduced,
    reduced: !!reduced,
    inView,
  };
}
