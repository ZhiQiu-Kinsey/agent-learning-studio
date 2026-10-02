// Adapted from https://reactbits.dev/r/GlareHover-TS-TW.json (MIT + Commons Clause).
// Sizes to its content; the glare sweeps on hover or keyboard focus within and is
// skipped entirely when motion is reduced.
import { useRef, type CSSProperties, type ReactNode } from "react";
import { useReducedMotion } from "../../motion";

export default function GlareHover({
  children,
  className = "",
  glareColor = "255, 255, 255",
  glareOpacity = 0.28,
  glareAngle = -45,
  glareSize = 250,
  transitionDuration = 700,
  style,
}: {
  children: ReactNode;
  className?: string;
  /** "r, g, b" so the opacity can be applied separately. */
  glareColor?: string;
  glareOpacity?: number;
  glareAngle?: number;
  glareSize?: number;
  transitionDuration?: number;
  style?: CSSProperties;
}) {
  const reduced = useReducedMotion();
  const overlay = useRef<HTMLSpanElement>(null);
  const sweep = (to: string) => {
    const element = overlay.current;
    if (!element || reduced) return;
    element.style.transition = `background-position ${transitionDuration}ms ease`;
    element.style.backgroundPosition = to;
  };
  return (
    <div
      className={`rb-glare-hover ${className}`}
      style={style}
      onPointerEnter={() => sweep("100% 100%")}
      onPointerLeave={() => sweep("-100% -100%")}
      onFocus={() => sweep("100% 100%")}
      onBlur={() => sweep("-100% -100%")}
    >
      <span
        ref={overlay}
        aria-hidden="true"
        className="rb-glare-overlay"
        style={{
          backgroundImage: `linear-gradient(${glareAngle}deg, transparent 60%, rgba(${glareColor}, ${glareOpacity}) 70%, transparent 100%)`,
          backgroundSize: `${glareSize}% ${glareSize}%`,
          backgroundRepeat: "no-repeat",
          backgroundPosition: "-100% -100%",
        }}
      />
      {children}
    </div>
  );
}
