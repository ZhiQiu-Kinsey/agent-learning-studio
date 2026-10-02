// Adapted from https://reactbits.dev/r/ElasticSlider-TS-TW.json (MIT + Commons Clause).
// Changes: controlled value with min/max/step, a real `role="slider"` with
// keyboard support (arrows, Page keys, Home/End), disabled state, app colour
// tokens, and the stretch/scale effects switched off at static motion.
import React, { useRef, useState } from "react";
import {
  animate,
  motion,
  useMotionValue,
  useMotionValueEvent,
  useTransform,
} from "motion/react";
import { useReducedMotion } from "../../motion";

const MAX_OVERFLOW = 40;

export interface ElasticSliderProps {
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (value: number) => void;
  disabled?: boolean;
  ariaLabel?: string;
  ariaLabelledBy?: string;
  /** Formats the value for display and aria-valuetext. */
  format?: (value: number) => string;
  accent?: string;
  trackColor?: string;
  className?: string;
  "data-testid"?: string;
}

function decay(value: number, max: number) {
  if (max === 0) return 0;
  const entry = value / max;
  return 2 * (1 / (1 + Math.exp(-entry)) - 0.5) * max;
}

const ElasticSlider: React.FC<ElasticSliderProps> = ({
  value,
  min,
  max,
  step = 1,
  onChange,
  disabled = false,
  ariaLabel,
  ariaLabelledBy,
  format = (v) => String(v),
  accent = "var(--accent)",
  trackColor = "var(--surface-muted)",
  className = "",
  "data-testid": testId,
}) => {
  const reduced = useReducedMotion();
  const trackRef = useRef<HTMLDivElement>(null);
  const [region, setRegion] = useState<"left" | "middle" | "right">("middle");
  const clientX = useMotionValue(0);
  const overflow = useMotionValue(0);
  const scale = useMotionValue(1);

  const clamp = (v: number) => Math.min(max, Math.max(min, v));
  const snap = (v: number) => {
    const stepped = Math.round((v - min) / step) * step + min;
    const decimals = String(step).split(".")[1]?.length ?? 0;
    return clamp(Number(stepped.toFixed(decimals)));
  };
  const commit = (v: number) => {
    const next = snap(v);
    if (next !== value) onChange(next);
  };

  useMotionValueEvent(clientX, "change", (latest: number) => {
    const track = trackRef.current;
    if (!track || reduced) return;
    const { left, right } = track.getBoundingClientRect();
    let next = 0;
    if (latest < left) {
      setRegion("left");
      next = left - latest;
    } else if (latest > right) {
      setRegion("right");
      next = latest - right;
    } else setRegion("middle");
    overflow.jump(decay(next, MAX_OVERFLOW));
  });

  const fromPointer = (event: React.PointerEvent<HTMLDivElement>) => {
    const track = trackRef.current;
    if (!track) return;
    const { left, width } = track.getBoundingClientRect();
    commit(min + ((event.clientX - left) / width) * (max - min));
    clientX.jump(event.clientX);
  };
  const release = () => {
    if (reduced) overflow.jump(0);
    else animate(overflow, 0, { type: "spring", bounce: 0.5 });
  };
  const onKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const big = Math.max(step, (max - min) / 10);
    const moves: Record<string, number> = {
      ArrowRight: value + step,
      ArrowUp: value + step,
      ArrowLeft: value - step,
      ArrowDown: value - step,
      PageUp: value + big,
      PageDown: value - big,
      Home: min,
      End: max,
    };
    if (!(event.key in moves)) return;
    event.preventDefault();
    commit(moves[event.key]);
  };

  const percent = max === min ? 0 : ((value - min) / (max - min)) * 100;
  const scaleX = useTransform(() => {
    const width = trackRef.current?.getBoundingClientRect().width;
    return width ? 1 + overflow.get() / width : 1;
  });
  const scaleY = useTransform(overflow, [0, MAX_OVERFLOW], [1, 0.8]);
  const origin = useTransform(() => {
    const rect = trackRef.current?.getBoundingClientRect();
    return rect && clientX.get() < rect.left + rect.width / 2
      ? "right"
      : "left";
  });
  const height = useTransform(scale, [1, 1.15], [6, 10]);
  // Read the pointer position inside the transform so it never goes stale.
  const side = () => {
    const rect = trackRef.current?.getBoundingClientRect();
    const x = clientX.get();
    return !rect ? 0 : x < rect.left ? -1 : x > rect.right ? 1 : 0;
  };
  const leftX = useTransform(() =>
    side() < 0 ? -overflow.get() / scale.get() : 0,
  );
  const rightX = useTransform(() =>
    side() > 0 ? overflow.get() / scale.get() : 0,
  );
  const grow = (to: number) => {
    if (!reduced && !disabled) animate(scale, to);
  };

  return (
    <div
      className={`elastic-slider${className ? ` ${className}` : ""}`}
      data-disabled={disabled ? "" : undefined}
    >
      <motion.div
        className="elastic-slider__row"
        onHoverStart={() => grow(1.15)}
        onHoverEnd={() => grow(1)}
        onTouchStart={() => grow(1.15)}
        onTouchEnd={() => grow(1)}
      >
        <motion.span
          className="elastic-slider__end"
          aria-hidden="true"
          animate={{ scale: region === "left" && !reduced ? [1, 1.3, 1] : 1 }}
          transition={{ duration: 0.25 }}
          style={{ x: leftX }}
        >
          {format(min)}
        </motion.span>
        <div
          ref={trackRef}
          className="elastic-slider__hit"
          role="slider"
          tabIndex={disabled ? -1 : 0}
          aria-label={ariaLabel}
          aria-labelledby={ariaLabelledBy}
          aria-valuemin={min}
          aria-valuemax={max}
          aria-valuenow={value}
          aria-valuetext={format(value)}
          aria-disabled={disabled || undefined}
          data-testid={testId}
          onKeyDown={disabled ? undefined : onKeyDown}
          onPointerDown={(event) => {
            if (disabled || event.button !== 0) return;
            event.currentTarget.setPointerCapture(event.pointerId);
            event.currentTarget.focus({ preventScroll: true });
            fromPointer(event);
          }}
          onPointerMove={(event) => {
            if (!disabled && event.buttons > 0) fromPointer(event);
          }}
          onPointerUp={release}
          onPointerCancel={release}
          onLostPointerCapture={release}
        >
          <motion.div
            className="elastic-slider__track"
            style={{
              scaleX,
              scaleY,
              transformOrigin: origin,
              height,
              background: trackColor,
            }}
          >
            <div
              className="elastic-slider__fill"
              style={{ width: `${percent}%`, background: accent }}
            />
          </motion.div>
        </div>
        <motion.span
          className="elastic-slider__end"
          aria-hidden="true"
          animate={{ scale: region === "right" && !reduced ? [1, 1.3, 1] : 1 }}
          transition={{ duration: 0.25 }}
          style={{ x: rightX }}
        >
          {format(max)}
        </motion.span>
      </motion.div>
      <output className="elastic-slider__value" aria-hidden="true">
        {format(value)}
      </output>
    </div>
  );
};

export default ElasticSlider;
