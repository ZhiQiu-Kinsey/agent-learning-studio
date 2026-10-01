import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import { MotionConfig } from "motion/react";
import { MotionContext, type MotionState } from "./context";
import {
  motionStorageKey,
  parseMotionSetting,
  resolveMotionLevel,
  type MotionSetting,
} from "./level";

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

function readSetting(): MotionSetting {
  try {
    return parseMotionSetting(localStorage.getItem(motionStorageKey));
  } catch {
    return parseMotionSetting(
      document.documentElement.dataset.motionPreference,
    );
  }
}

/** Single source for every motion decision: OS preference, learner setting, WebGL and page visibility. */
export function MotionProvider({ children }: { children: ReactNode }) {
  const [setting, setSettingState] = useState(readSetting);
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
  const level = resolveMotionLevel(setting, systemReduced);

  // Before paint so CSS gates never lag behind React state.
  useLayoutEffect(() => {
    const root = document.documentElement;
    root.dataset.motion = level;
    root.dataset.motionPreference = setting;
  }, [level, setting]);

  useEffect(() => {
    const sync = (event: StorageEvent) => {
      if (event.key === motionStorageKey || event.key === null)
        setSettingState(parseMotionSetting(event.newValue));
    };
    window.addEventListener("storage", sync);
    return () => window.removeEventListener("storage", sync);
  }, []);

  const setSetting = useCallback((next: MotionSetting) => {
    setSettingState(next);
    try {
      localStorage.setItem(motionStorageKey, next);
    } catch {
      /* Keep the session choice. */
    }
  }, []);

  const value = useMemo<MotionState>(
    () => ({
      setting,
      setSetting,
      level,
      reduced: level !== "full",
      webgl,
      pageVisible,
    }),
    [setting, setSetting, level, webgl, pageVisible],
  );

  return (
    <MotionContext.Provider value={value}>
      <MotionConfig reducedMotion={level === "full" ? "never" : "always"}>
        {children}
      </MotionConfig>
    </MotionContext.Provider>
  );
}
