// Adapted from https://reactbits.dev/r/MagicBento-TS-TW.json (MIT + Commons Clause).
import { useEffect, useState } from "react";

const MOBILE_BREAKPOINT = 768;

export const useMobileDetection = () => {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const coarse = matchMedia("(pointer: coarse)");
    const checkMobile = () =>
      setIsMobile(window.innerWidth <= MOBILE_BREAKPOINT || coarse.matches);

    checkMobile();
    window.addEventListener("resize", checkMobile);
    coarse.addEventListener("change", checkMobile);

    return () => {
      window.removeEventListener("resize", checkMobile);
      coarse.removeEventListener("change", checkMobile);
    };
  }, []);

  return isMobile;
};
