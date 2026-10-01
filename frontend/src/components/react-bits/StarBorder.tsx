// React Bits StarBorder, adapted from https://reactbits.dev/r/StarBorder-TS-CSS.json.
// Copyright (c) 2026 David Haz. See LICENSE.md. Decorations pause when hidden.
import type { ReactNode } from "react";
import { useMotionBudget } from "../../motion";

export default function StarBorder({
  children,
  className = "",
  color = "var(--accent)",
  speed = "8s",
}: {
  children: ReactNode;
  className?: string;
  color?: string;
  speed?: string;
}) {
  const { ref, active } = useMotionBudget<HTMLDivElement>();
  const style = {
    background: `radial-gradient(circle, ${color}, transparent 15%)`,
    animationDuration: speed,
    animationPlayState: active ? ("running" as const) : ("paused" as const),
  };
  return (
    <div ref={ref} className={`rb-star-border ${className}`}>
      <span className="rb-star-bottom" aria-hidden="true" style={style} />
      <span className="rb-star-top" aria-hidden="true" style={style} />
      <div className="rb-star-inner">{children}</div>
    </div>
  );
}
