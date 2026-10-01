// React Bits Magnet, adapted from https://reactbits.dev/r/Magnet-TS-CSS.json.
// Copyright (c) 2026 David Haz. See LICENSE.md. Fine pointers only; bounded displacement.
import { useEffect, useState, type ReactNode } from "react";
import { useMotionBudget } from "../../motion";

export default function Magnet({
  children,
  className = "",
  padding = 25,
  magnetStrength = 14,
}: {
  children: ReactNode;
  className?: string;
  padding?: number;
  magnetStrength?: number;
}) {
  const { ref, active, reduced } = useMotionBudget<HTMLDivElement>();
  const [position, setPosition] = useState({ x: 0, y: 0 });
  useEffect(() => {
    if (!active || !matchMedia("(pointer: fine)").matches) return;
    const move = (event: MouseEvent) => {
      if (!ref.current) return;
      const { left, top, width, height } = ref.current.getBoundingClientRect();
      const x = event.clientX - left - width / 2;
      const y = event.clientY - top - height / 2;
      setPosition(
        Math.abs(x) < width / 2 + padding && Math.abs(y) < height / 2 + padding
          ? {
              x: Math.max(-6, Math.min(6, x / magnetStrength)),
              y: Math.max(-6, Math.min(6, y / magnetStrength)),
            }
          : { x: 0, y: 0 },
      );
    };
    window.addEventListener("mousemove", move, { passive: true });
    return () => window.removeEventListener("mousemove", move);
  }, [active, magnetStrength, padding, ref]);
  return (
    <div ref={ref} className={`rb-magnet ${className}`}>
      <div
        style={{
          transform: active
            ? `translate3d(${position.x}px, ${position.y}px, 0)`
            : "none",
          transition: reduced ? "none" : "transform 0.3s ease-out",
        }}
      >
        {children}
      </div>
    </div>
  );
}
