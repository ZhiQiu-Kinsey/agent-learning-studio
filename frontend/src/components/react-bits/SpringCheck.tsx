// Adapted from https://reactbits.dev/r/SpringCheck-TS-TW.json (MIT + Commons Clause).
// Copyright (c) 2026 David Haz. See LICENSE.md.
//
// Changes for Agent Lab:
// - A native <input type="checkbox"> inside a <label> carries the semantics
//   (forms, keyboard, assistive tech and tests see a real checkbox); the
//   springy box and tick are decoration (aria-hidden).
// - Reduced motion follows src/motion: the state jumps, nothing springs.
// - Styles live in SpringCheck.css and read theme tokens through CSS vars.
// - The strike-through rule is optional (off by default).
"use client";

import {
  useEffect,
  useLayoutEffect,
  useRef,
  type CSSProperties,
  type ReactNode,
} from "react";
import { animate, useMotionValue, useMotionValueEvent } from "motion/react";
import { Tick02Icon } from "@hugeicons/core-free-icons";
import { useReducedMotion } from "../../motion";
import "./SpringCheck.css";

const VISUAL_DURATION = 0.22;
const RULE_END = 0.84;
const SWELL = 0.35;
const TICK_PATH = String((Tick02Icon[0][1] as { d: string }).d);

const clamp01 = (value: number) => Math.min(1, Math.max(0, value));
const zetaOf = (bounce: number) =>
  bounce <= 0
    ? 1
    : -Math.log(bounce) / Math.sqrt(Math.PI ** 2 + Math.log(bounce) ** 2);

const readings = (t: number, doneOpacity: number, strikeLag: number) => {
  const held = clamp01(t);
  return {
    fill: `scale(${Math.max(t, 0)})`,
    box: `scale(${1 + SWELL * Math.max(0, t - 1)})`,
    tick: 1 - held,
    word: 1 - (1 - doneOpacity) * held,
    rule: `scaleX(${clamp01((held - strikeLag) / (RULE_END - strikeLag))})`,
  };
};

export interface SpringCheckProps {
  label: ReactNode;
  checked: boolean;
  onChange: (checked: boolean) => void;
  /** Spring bounciness, 0..1. */
  bounce?: number;
  /** Label opacity once checked. */
  doneOpacity?: number;
  strike?: boolean;
  strikeLag?: number;
  boxSize?: number;
  className?: string;
}

export default function SpringCheck({
  label,
  checked,
  onChange,
  bounce = 0.35,
  doneOpacity = 0.78,
  strike = false,
  strikeLag = 0.12,
  boxSize = 22,
  className = "",
}: SpringCheckProps) {
  const reduce = useReducedMotion();
  const t = useMotionValue(checked ? 1 : 0);
  const boxRef = useRef<HTMLSpanElement>(null);
  const fillRef = useRef<HTMLSpanElement>(null);
  const tickRef = useRef<SVGPathElement>(null);
  const wordRef = useRef<HTMLSpanElement>(null);
  const ruleRef = useRef<HTMLSpanElement>(null);
  const cfg = useRef({ doneOpacity, strikeLag });
  cfg.current = { doneOpacity, strikeLag };

  const write = (value: number) => {
    const r = readings(value, cfg.current.doneOpacity, cfg.current.strikeLag);
    if (fillRef.current) fillRef.current.style.transform = r.fill;
    if (boxRef.current) boxRef.current.style.transform = r.box;
    if (tickRef.current)
      tickRef.current.style.strokeDashoffset = String(r.tick);
    if (wordRef.current) wordRef.current.style.opacity = String(r.word);
    if (ruleRef.current) ruleRef.current.style.transform = r.rule;
  };
  useMotionValueEvent(t, "change", write);
  useLayoutEffect(() => {
    write(t.get());
  });

  useEffect(() => {
    const target = checked ? 1 : 0;
    if (reduce) {
      t.jump(target);
      return undefined;
    }
    if (t.get() === target && t.getVelocity() === 0) return undefined;
    const controls = animate(t, target, {
      type: "spring",
      visualDuration: VISUAL_DURATION,
      bounce: 1 - zetaOf(bounce),
    });
    return () => controls.stop();
  }, [checked, reduce, bounce, t]);

  const r = readings(t.get(), doneOpacity, strikeLag);
  return (
    <label
      className={`rb-spring-check ${className}`}
      data-checked={checked}
      style={{ "--sc-box": `${boxSize}px` } as CSSProperties}
    >
      <input
        type="checkbox"
        className="rb-spring-check-input"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span className="rb-spring-check-box" aria-hidden="true">
        <span
          ref={boxRef}
          className="rb-spring-check-inner"
          style={{ transform: r.box }}
        >
          <span className="rb-spring-check-ring" />
          <span
            ref={fillRef}
            className="rb-spring-check-fill"
            style={{ transform: r.fill }}
          />
          <svg viewBox="0 0 24 24" className="rb-spring-check-tick">
            <path
              ref={tickRef}
              d={TICK_PATH}
              pathLength={1}
              strokeDasharray={1}
              style={{ strokeDashoffset: r.tick }}
            />
          </svg>
        </span>
      </span>
      <span className="rb-spring-check-label">
        <span ref={wordRef} style={{ opacity: r.word }}>
          {label}
        </span>
        {strike && (
          <span
            ref={ruleRef}
            className="rb-spring-check-rule"
            aria-hidden="true"
            style={{ transform: r.rule }}
          />
        )}
      </span>
    </label>
  );
}
