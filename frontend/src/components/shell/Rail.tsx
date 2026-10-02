import {
  createContext,
  useContext,
  useState,
  type ComponentProps,
  type CSSProperties,
  type ReactNode,
} from "react";
import { AnimatePresence, LayoutGroup, motion } from "motion/react";
import { useReducedMotion } from "../../motion";
import { Button } from "../ui/button";

/**
 * Sidebar highlight: one hover pill and one active pill per rail, both moved
 * between items with motion `layoutId` springs (LineSidebar-like feel). Each
 * rail instance (desktop aside, mobile sheet) gets its own LayoutGroup so the
 * two copies never trade pills.
 */
const spring = {
  type: "spring",
  stiffness: 520,
  damping: 40,
  mass: 0.7,
} as const;

interface RailState {
  hovered: string | null;
  setHovered: (key: string | null) => void;
  reduced: boolean;
}
const RailContext = createContext<RailState | null>(null);

export function RailGroup({
  id,
  children,
}: {
  id: string;
  children: ReactNode;
}) {
  const [hovered, setHovered] = useState<string | null>(null);
  const reduced = useReducedMotion();
  return (
    <LayoutGroup id={id}>
      <RailContext.Provider value={{ hovered, setHovered, reduced }}>
        <div className="rail-group" onPointerLeave={() => setHovered(null)}>
          {children}
        </div>
      </RailContext.Provider>
    </LayoutGroup>
  );
}

/** Key of the item under the pointer or focus in this rail (null when none). */
export const useRailHovered = () => useContext(RailContext)?.hovered ?? null;

/** Hover handlers plus the pills to render inside an item. */
export function useRailHighlight(
  key: string,
  {
    active = false,
    disabled = false,
    tint,
  }: {
    active?: boolean;
    disabled?: boolean;
    tint?: string;
  } = {},
) {
  const rail = useContext(RailContext);
  const hovered = !!rail && rail.hovered === key && !disabled && !active;
  const animate = !!rail && !rail.reduced;
  const style = tint ? ({ "--rail-tint": tint } as CSSProperties) : undefined;
  const pills = (
    <>
      <AnimatePresence>
        {hovered && (
          <motion.span
            key="hover"
            aria-hidden="true"
            className="rail-pill rail-pill-hover"
            layoutId={animate ? "rail-hover" : undefined}
            initial={animate ? { opacity: 0 } : false}
            animate={{ opacity: 1 }}
            exit={animate ? { opacity: 0 } : undefined}
            transition={animate ? spring : { duration: 0 }}
          />
        )}
      </AnimatePresence>
      {active && (
        <motion.span
          aria-hidden="true"
          className="rail-pill rail-pill-active"
          style={style}
          layoutId={animate ? "rail-active" : undefined}
          transition={animate ? spring : { duration: 0 }}
        />
      )}
    </>
  );
  return {
    pills,
    handlers: {
      onPointerEnter: () => rail?.setHovered(key),
      onFocus: () => rail?.setHovered(key),
      onBlur: () => rail?.setHovered(null),
    },
  };
}

/** A rail button: ghost Button with sliding hover/active pills behind its content. */
export function RailItem({
  itemKey,
  active = false,
  tint,
  className = "",
  children,
  ...props
}: ComponentProps<typeof Button> & {
  itemKey: string;
  active?: boolean;
  tint?: string;
}) {
  const { pills, handlers } = useRailHighlight(itemKey, {
    active,
    disabled: !!props.disabled,
    tint,
  });
  return (
    <Button
      variant="ghost"
      {...props}
      {...handlers}
      className={`rail-item ${active ? "is-active" : ""} ${className}`}
    >
      {pills}
      {children}
    </Button>
  );
}
