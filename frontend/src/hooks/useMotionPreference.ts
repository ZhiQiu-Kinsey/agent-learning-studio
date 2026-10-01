import { useSyncExternalStore } from "react";

const query = "(prefers-reduced-motion: reduce)";
const subscribe = (onChange: () => void) => {
  const media = window.matchMedia(query);
  media.addEventListener("change", onChange);
  return () => media.removeEventListener("change", onChange);
};
const getSnapshot = () => window.matchMedia(query).matches;

/** Keep the OS preference live; the installed Motion hook captures it on mount. */
export function useMotionPreference() {
  return useSyncExternalStore(subscribe, getSnapshot, () => true);
}
