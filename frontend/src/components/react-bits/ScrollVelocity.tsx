// Adapted from https://reactbits.dev/r/ScrollVelocity-TS-TW.json (MIT + Commons Clause).
// Rows drift only while on screen at full motion and speed up with page scroll.
// The rows are decorative copies; callers provide the accessible list separately.
// Static motion renders each row once, wrapped, so nothing is clipped away.
import {
  motion,
  useAnimationFrame,
  useMotionValue,
  useScroll,
  useSpring,
  useTransform,
  useVelocity,
} from "motion/react";
import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { useMotionBudget } from "../../motion";

function useElementWidth(ref: React.RefObject<HTMLElement | null>) {
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) return;
    const observer = new ResizeObserver(() => setWidth(element.offsetWidth));
    observer.observe(element);
    setWidth(element.offsetWidth);
    return () => observer.disconnect();
  }, [ref]);
  return width;
}

const wrap = (min: number, max: number, value: number) => {
  const range = max - min;
  return ((((value - min) % range) + range) % range) + min;
};

function VelocityRow({
  children,
  baseVelocity,
  active,
  copies,
  className,
}: {
  children: ReactNode;
  baseVelocity: number;
  active: boolean;
  copies: number;
  className: string;
}) {
  const baseX = useMotionValue(0);
  const { scrollY } = useScroll();
  const smooth = useSpring(useVelocity(scrollY), { damping: 50, stiffness: 400 });
  const factor = useTransform(smooth, [0, 1000], [0, 4], { clamp: false });
  const copyRef = useRef<HTMLSpanElement>(null);
  const copyWidth = useElementWidth(copyRef);
  const x = useTransform(baseX, (value) =>
    copyWidth === 0 ? "0px" : `${wrap(-copyWidth, 0, value)}px`,
  );
  const direction = useRef(1);

  useAnimationFrame((_, delta) => {
    if (!active) return;
    let moveBy = direction.current * baseVelocity * (delta / 1000);
    const boost = factor.get();
    if (boost < 0) direction.current = -1;
    else if (boost > 0) direction.current = 1;
    moveBy += direction.current * moveBy * boost;
    baseX.set(baseX.get() + moveBy);
  });

  return (
    <div className="rb-velocity-row">
      <motion.div className="rb-velocity-scroller" style={{ x }}>
        {Array.from({ length: copies }, (_, index) => (
          <span
            key={index}
            ref={index === 0 ? copyRef : undefined}
            className={`rb-velocity-copy ${className}`}
          >
            {children}
          </span>
        ))}
      </motion.div>
    </div>
  );
}

export default function ScrollVelocity({
  rows,
  velocity = 40,
  copies = 4,
  className = "",
}: {
  rows: ReactNode[];
  velocity?: number;
  copies?: number;
  className?: string;
}) {
  const { ref, active, reduced } = useMotionBudget<HTMLDivElement>("css", {
    margin: "80px",
  });
  return (
    <div
      ref={ref}
      className={`rb-velocity ${reduced ? "is-static" : ""}`}
      aria-hidden="true"
    >
      {reduced
        ? rows.map((row, index) => (
            <div key={index} className={`rb-velocity-static ${className}`}>
              {row}
            </div>
          ))
        : rows.map((row, index) => (
            <VelocityRow
              key={index}
              baseVelocity={index % 2 ? -velocity : velocity}
              active={active}
              copies={copies}
              className={className}
            >
              {row}
            </VelocityRow>
          ))}
    </div>
  );
}
