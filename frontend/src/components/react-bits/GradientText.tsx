// React Bits GradientText, adapted from https://reactbits.dev/r/GradientText-TS-CSS.json.
// Copyright (c) 2026 David Haz. See LICENSE.md. CSS loop pauses outside the viewport.
import type { ReactNode } from "react";
import { useExperienceMotion } from "../learning/useExperienceMotion";

export default function GradientText({
  children,
  className = "",
  colors = ["#7562e9", "#a572da", "#278d9d", "#7562e9"],
  animationSpeed = 8,
}: {
  children: ReactNode;
  className?: string;
  colors?: string[];
  animationSpeed?: number;
}) {
  const { ref, active } = useExperienceMotion<HTMLSpanElement>();
  return (
    <span
      ref={ref}
      className={`rb-gradient-text ${className}`}
      style={{
        backgroundImage: `linear-gradient(to right, ${[...colors, colors[0]].join(", ")})`,
        animationDuration: `${animationSpeed}s`,
        animationPlayState: active ? "running" : "paused",
      }}
    >
      {children}
    </span>
  );
}
