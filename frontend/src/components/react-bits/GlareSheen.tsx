// Adapted from https://reactbits.dev/r/GlareHover-TS-TW.json (MIT + Commons Clause).
// Wrapper form: no fixed size or colours (the child card keeps its own styles);
// the glare sweep is pure CSS (.rb-glare) and is disabled at static motion.
import type { CSSProperties, ReactNode } from "react";

export default function GlareSheen({
  children,
  className = "",
  glareColor = "255 255 255",
  glareOpacity = 0.22,
  glareAngle = -45,
  duration = 700,
}: {
  children: ReactNode;
  className?: string;
  /** Space-separated RGB channels, e.g. "185 138 255". */
  glareColor?: string;
  glareOpacity?: number;
  glareAngle?: number;
  duration?: number;
}) {
  return (
    <div
      className={`rb-glare ${className}`}
      style={
        {
          "--glare-color": `rgb(${glareColor} / ${glareOpacity})`,
          "--glare-angle": `${glareAngle}deg`,
          "--glare-duration": `${duration}ms`,
        } as CSSProperties
      }
    >
      {children}
      <span className="rb-glare-sheen" aria-hidden="true" />
    </div>
  );
}
