import type { CSSProperties } from "react";
import { motion } from "motion/react";
import type { LucideIcon } from "lucide-react";
import CountUp from "../react-bits/CountUp";
import { useReducedMotion } from "../../motion";
import { easeOut } from "./transitions";

/** One hero statistic; the number counts up, screen readers get it at once. */
export function MapMetric({
  value,
  label,
  index,
  Icon,
  ratio,
}: {
  value: number;
  label: string;
  index: number;
  Icon: LucideIcon;
  /** Optional real share (0..1) drawn as a thin meter. */
  ratio?: number;
}) {
  const reducedMotion = useReducedMotion();
  return (
    <motion.div
      className="curriculum-metric"
      initial={reducedMotion ? false : { opacity: 0, y: 22, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.65, delay: 0.3 + index * 0.08, ease: easeOut }}
      style={
        ratio === undefined
          ? undefined
          : ({ "--ratio": ratio } as CSSProperties)
      }
    >
      <Icon className="curriculum-metric-icon" size={16} aria-hidden="true" />
      <strong>
        <span className="sr-only">{value}</span>
        <span aria-hidden="true">
          {reducedMotion ? (
            value
          ) : (
            <CountUp to={value} duration={1.1} delay={0.35 + index * 0.09} />
          )}
        </span>
      </strong>
      <span>{label}</span>
      {ratio !== undefined && (
        <span className="curriculum-metric-meter" aria-hidden="true">
          <i />
        </span>
      )}
    </motion.div>
  );
}
