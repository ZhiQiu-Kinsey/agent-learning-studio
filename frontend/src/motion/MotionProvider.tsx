import {
  useLayoutEffect,
  useMemo,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import { MotionConfig } from "motion/react";
import { MotionContext, type MotionState } from "./context";
import { resolveMotionLevel } from "./level";

const reduceQuery = "(prefers-reduced-motion: reduce)";
const subscribeReduce = (onChange: () => void) => {
  const media = matchMedia(reduceQuery);
  media.addEventListener("change", onChange);
  return () => media.removeEventListener("change", onChange);
};
const getReduce = () => matchMedia(reduceQuery).matches;

const subscribeVisibility = (onChange: () => void) => {
  document.addEventListener("visibilitychange", onChange);
  return () => document.removeEventListener("visibilitychange", onChange);
};
const getVisible = () => !document.hidden;

let webglSupport: boolean | undefined;
function detectWebgl() {
  if (webglSupport === undefined) {
    try {
      const canvas = document.createElement("canvas");
      const gl = canvas.getContext("webgl2") ?? canvas.getContext("webgl");
      webglSupport = !!gl;
      gl?.getExtension("WEBGL_lose_context")?.loseContext();
    } catch {
      webglSupport = false;
    }
  }
  return webglSupport;
}

/** Single source for every motion decision: OS preference, WebGL and page visibility. */
export function MotionProvider({ children }: { children: ReactNode }) {
  const systemReduced = useSyncExternalStore(
    subscribeReduce,
    getReduce,
    () => true,
  );
  const pageVisible = useSyncExternalStore(
    subscribeVisibility,
    getVisible,
    () => false,
  );
  const [webgl] = useState(detectWebgl);
  const level = resolveMotionLevel(systemReduced);

  // Before paint so CSS gates never lag behind React state.
  useLayoutEffect(() => {
    document.documentElement.dataset.motion = level;
  }, [level]);

  const value = useMemo<MotionState>(
    () => ({ level, reduced: level !== "full", webgl, pageVisible }),
    [level, webgl, pageVisible],
  );

  return (
    <MotionContext.Provider value={value}>
      <MotionConfig reducedMotion={level === "full" ? "never" : "always"}>
        {children}
      </MotionConfig>
    </MotionContext.Provider>
  );
}
