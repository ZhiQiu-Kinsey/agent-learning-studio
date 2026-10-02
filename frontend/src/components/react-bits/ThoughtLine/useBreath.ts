// Adapted from https://reactbits.dev/r/ThoughtLine-TS-TW.json (MIT + Commons Clause).
import { useEffect, type RefObject } from "react";
import { animate, type AnimationPlaybackControls } from "motion/react";
import { EASE_OUT, EASE_IN_OUT, GLYPH_DONE } from "./utils";
import type { ThoughtLineGlyph } from "../ThoughtLine";

interface BreathOptions {
  glyphRef: RefObject<HTMLSpanElement | null>;
  breathRef: RefObject<HTMLSpanElement | null>;
  isWorking: boolean;
  period: number;
  depth: number;
  trough: number;
  settleDuration: number;
  glyph: ThoughtLineGlyph;
  sheen: boolean;
}

/** Breathing glyph and label while working (a shimmer replaces the label breath), settling to rest when done. */
export function useBreath({
  glyphRef,
  breathRef,
  isWorking,
  period,
  depth,
  trough,
  settleDuration,
  glyph,
  sheen,
}: BreathOptions) {
  useEffect(() => {
    const glyphEl = glyphRef.current;
    const breathEl = breathRef.current;
    if (!breathEl) return undefined;
    const s = settleDuration / 1000;
    const loop = (el: HTMLElement, delay: number) =>
      animate(
        el,
        { opacity: [trough, 1, trough] },
        { duration: period, ease: EASE_IN_OUT, repeat: Infinity, delay },
      );
    let cancelled = false;
    const running: AnimationPlaybackControls[] = [];
    if (isWorking) {
      if (depth > 0) {
        if (sheen)
          running.push(
            animate(
              breathEl,
              { opacity: 1 },
              { duration: 0.2, ease: EASE_OUT },
            ),
          );
        if (glyphEl) {
          const lead = animate(
            glyphEl,
            { opacity: trough },
            { duration: 0.2, ease: EASE_OUT },
          );
          running.push(lead);
          lead.then(() => {
            if (cancelled) return;
            running.push(loop(glyphEl, 0));
            if (!sheen) running.push(loop(breathEl, 0.14));
          });
        } else if (!sheen) {
          running.push(loop(breathEl, 0.14));
        }
      } else {
        if (glyphEl)
          running.push(
            animate(glyphEl, { opacity: 1 }, { duration: 0.2, ease: EASE_OUT }),
          );
        running.push(
          animate(breathEl, { opacity: 1 }, { duration: 0.2, ease: EASE_OUT }),
        );
      }
    } else {
      if (glyphEl)
        running.push(
          animate(
            glyphEl,
            { opacity: GLYPH_DONE },
            { duration: s, ease: EASE_OUT },
          ),
        );
      running.push(
        animate(breathEl, { opacity: 1 }, { duration: s, ease: EASE_OUT }),
      );
    }
    return () => {
      cancelled = true;
      running.forEach((a) => a.stop());
    };
  }, [isWorking, period, depth, trough, settleDuration, glyph, sheen]);
}
