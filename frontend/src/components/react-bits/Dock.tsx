// React Bits Dock, adapted from https://reactbits.dev/r/Dock-TS-CSS.json.
// Copyright (c) 2026 David Haz. See LICENSE.md. Changes: real <button> items,
// floats at the bottom of its container (no in-flow height animation),
// no magnification at static motion, theme-aware styles.
import {
  AnimatePresence,
  motion,
  useMotionValue,
  useSpring,
  useTransform,
  type MotionValue,
  type SpringOptions,
} from "motion/react";
import { useRef, useState, type ReactNode } from "react";
import { useReducedMotion } from "../../motion";
import "./Dock.css";

export type DockItemData = {
  icon: ReactNode;
  label: string;
  onClick: () => void;
  className?: string;
  testId?: string;
};

function DockItem({
  item,
  mouseX,
  spring,
  distance,
  baseItemSize,
  magnification,
}: {
  item: DockItemData;
  mouseX: MotionValue<number>;
  spring: SpringOptions;
  distance: number;
  baseItemSize: number;
  magnification: number;
}) {
  const ref = useRef<HTMLButtonElement>(null);
  const [labelled, setLabelled] = useState(false);
  const mouseDistance = useTransform(mouseX, (value) => {
    const rect = ref.current?.getBoundingClientRect() ?? {
      x: 0,
      width: baseItemSize,
    };
    return value - rect.x - rect.width / 2;
  });
  const targetSize = useTransform(
    mouseDistance,
    [-distance, 0, distance],
    [baseItemSize, magnification, baseItemSize],
  );
  const size = useSpring(targetSize, spring);

  return (
    <motion.button
      ref={ref}
      type="button"
      style={{ width: size, height: size }}
      onHoverStart={() => setLabelled(true)}
      onHoverEnd={() => setLabelled(false)}
      onFocus={() => setLabelled(true)}
      onBlur={() => setLabelled(false)}
      onClick={item.onClick}
      className={`dock-item ${item.className ?? ""}`}
      aria-label={item.label}
      data-testid={item.testId}
    >
      <span className="dock-icon" aria-hidden="true">
        {item.icon}
      </span>
      <AnimatePresence>
        {labelled && (
          <motion.span
            className="dock-label"
            aria-hidden="true"
            initial={{ opacity: 0, y: 0 }}
            animate={{ opacity: 1, y: -8 }}
            exit={{ opacity: 0, y: 0 }}
            transition={{ duration: 0.18 }}
            style={{ x: "-50%" }}
          >
            {item.label}
          </motion.span>
        )}
      </AnimatePresence>
    </motion.button>
  );
}

export default function Dock({
  items,
  label,
  className = "",
  spring = { mass: 0.1, stiffness: 150, damping: 12 },
  magnification = 62,
  distance = 140,
  baseItemSize = 44,
}: {
  items: DockItemData[];
  label: string;
  className?: string;
  spring?: SpringOptions;
  magnification?: number;
  distance?: number;
  baseItemSize?: number;
}) {
  const reduced = useReducedMotion();
  const mouseX = useMotionValue(Infinity);
  return (
    <div className={`dock-outer ${className}`}>
      <div
        className="dock-panel"
        role="toolbar"
        aria-label={label}
        onMouseMove={({ clientX }) => mouseX.set(clientX)}
        onMouseLeave={() => mouseX.set(Infinity)}
      >
        {items.map((item) => (
          <DockItem
            key={item.label}
            item={item}
            mouseX={mouseX}
            spring={spring}
            distance={distance}
            baseItemSize={baseItemSize}
            magnification={reduced ? baseItemSize : magnification}
          />
        ))}
      </div>
    </div>
  );
}
