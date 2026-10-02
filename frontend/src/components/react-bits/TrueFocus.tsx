// Adapted from https://reactbits.dev/r/TrueFocus-TS-TW.json (MIT + Commons Clause).
// Generalised from words to any items: a corner-bracket frame glides from item
// to item (matched by `itemSelector`) and the current one gets
// `data-focused`. It cycles only while on screen at full motion, follows the
// pointer / keyboard focus, and pauses while the learner is on an item. Static
// motion: no frame, no cycling. The frame is aria-hidden decoration.
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import { motion } from "motion/react";
import { useMotionBudget } from "../../motion";
import "./TrueFocus.css";

interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export default function TrueFocus({
  children,
  itemSelector,
  className = "",
  borderColor = "#b98aff",
  glowColor = "rgba(185, 138, 255, 0.55)",
  animationDuration = 0.5,
  pauseBetweenAnimations = 1.6,
}: {
  children: ReactNode;
  itemSelector: string;
  className?: string;
  borderColor?: string;
  glowColor?: string;
  animationDuration?: number;
  pauseBetweenAnimations?: number;
}) {
  const { ref, active, reduced } = useMotionBudget<HTMLDivElement>("css");
  const [index, setIndex] = useState(0);
  const [held, setHeld] = useState(false);
  const [rect, setRect] = useState<Rect | null>(null);

  const items = useCallback(
    () =>
      Array.from(
        ref.current?.querySelectorAll<HTMLElement>(itemSelector) ?? [],
      ),
    [itemSelector, ref],
  );

  // Cycle while visible and nobody is pointing at an item.
  useEffect(() => {
    if (!active || held) return;
    const timer = setInterval(
      () => setIndex((value) => (value + 1) % Math.max(1, items().length)),
      (animationDuration + pauseBetweenAnimations) * 1000,
    );
    return () => clearInterval(timer);
  }, [active, held, animationDuration, pauseBetweenAnimations, items]);

  // Measure the focused item and mark it.
  useLayoutEffect(() => {
    const container = ref.current;
    if (!container || reduced) return;
    const list = items();
    const measure = () => {
      const target = list[index];
      if (!target) return setRect(null);
      const parent = container.getBoundingClientRect();
      const box = target.getBoundingClientRect();
      setRect({
        x: box.left - parent.left,
        y: box.top - parent.top,
        width: box.width,
        height: box.height,
      });
    };
    list.forEach((item, i) => {
      if (i === index) item.setAttribute("data-focused", "true");
      else item.removeAttribute("data-focused");
    });
    measure();
    // Items may still be settling from an entrance transform; re-measure once.
    const settle = setTimeout(measure, 1200);
    const observer = new ResizeObserver(measure);
    observer.observe(container);
    return () => {
      clearTimeout(settle);
      observer.disconnect();
      list.forEach((item) => item.removeAttribute("data-focused"));
    };
  }, [index, items, reduced, ref]);

  const follow = (target: EventTarget | null) => {
    const item = (target as HTMLElement | null)?.closest?.(itemSelector);
    const at = item ? items().indexOf(item as HTMLElement) : -1;
    if (at < 0) return;
    setIndex(at);
    setHeld(true);
  };

  return (
    <div
      ref={ref}
      className={`rb-true-focus ${className}`}
      onPointerOver={reduced ? undefined : (event) => follow(event.target)}
      onPointerLeave={reduced ? undefined : () => setHeld(false)}
      onFocus={reduced ? undefined : (event) => follow(event.target)}
      onBlur={reduced ? undefined : () => setHeld(false)}
    >
      {children}
      {!reduced && rect && (
        <motion.div
          className="rb-true-focus-frame"
          aria-hidden="true"
          initial={false}
          animate={{
            x: rect.x,
            y: rect.y,
            width: rect.width,
            height: rect.height,
          }}
          transition={{ duration: animationDuration, ease: [0.16, 1, 0.3, 1] }}
          style={
            {
              "--focus-border": borderColor,
              "--focus-glow": glowColor,
            } as CSSProperties
          }
        >
          <span data-corner="tl" />
          <span data-corner="tr" />
          <span data-corner="bl" />
          <span data-corner="br" />
        </motion.div>
      )}
    </div>
  );
}
