// Adapted from https://reactbits.dev/r/ScrubField-TS-TW.json (MIT + Commons Clause, see LICENSE.md).
import React, { useEffect, useId, useRef, useState } from "react";
import {
  animate,
  useMotionTemplate,
  useMotionValue,
  useMotionValueEvent,
  useTransform,
} from "motion/react";
import { useReducedMotion } from "../../../motion";
import { createEntryHandlers } from "./entry";
import {
  type DragState,
  type Modifiers,
  SPRING_UI,
  LEAN,
  SIZES,
  clamp,
  decimalsOf,
} from "./utils";
import type { ScrubFieldSize, ScrubFieldProps } from "../ScrubField";

interface ScrubFieldOptions {
  valueProp: number | undefined;
  defaultValue: number;
  min: number;
  max: number;
  step: number;
  size: ScrubFieldSize;
  sensitivity: number;
  rubberReach: number;
  returnDuration: number;
  coarseMultiplier: number;
  fineMultiplier: number;
  showDirty: boolean;
  disabled: boolean;
  onChange: ScrubFieldProps["onChange"];
  onCommit: ScrubFieldProps["onCommit"];
}

/** Value state, the rubber-banded drag gesture, keyboard stepping and typed entry; the component only renders. */
export function useScrubField({
  valueProp,
  defaultValue,
  min,
  max,
  step,
  size,
  sensitivity,
  rubberReach,
  returnDuration,
  coarseMultiplier,
  fineMultiplier,
  showDirty,
  disabled,
  onChange,
  onCommit,
}: ScrubFieldOptions) {
  const id = useId();
  const reduce = useReducedMotion();
  const controlled = valueProp !== undefined;
  const [value, setValue] = useState<number>(
    controlled ? (valueProp as number) : defaultValue,
  );
  const [dragging, setDragging] = useState(false);
  const [draft, setDraft] = useState<string | null>(null);
  const display = useMotionValue(value);
  const chipRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const ghostRef = useRef<HTMLSpanElement>(null);
  const drag = useRef<DragState | null>(null);
  const valueRef = useRef(value);
  const typingRef = useRef(false);
  const movedRef = useRef(false);
  const endRef = useRef<(cancel?: boolean) => void>(() => {});
  const escRef = useRef<((e: KeyboardEvent) => void) | null>(null);
  const mounted = useRef(false);

  const baseDecimals = decimalsOf(step);
  const fineDecimals = Math.min(6, baseDecimals + decimalsOf(fineMultiplier));
  const preset = SIZES[size] || SIZES.md;

  const fmt = (v: number) => {
    const scaled = v * 10 ** baseDecimals;
    return v.toFixed(
      Math.abs(scaled - Math.round(scaled)) < 1e-6
        ? baseDecimals
        : fineDecimals,
    );
  };
  const signed = (d: number) => (d < 0 ? "−" : "+") + fmt(Math.abs(d));

  const reach = (rubberReach / 100) * Math.max(max - min, Number.EPSILON);
  const bend = (raw: number) =>
    reach ? Math.sign(raw) * reach * Math.log1p(Math.abs(raw) / reach) : 0;
  const unbend = (over: number) =>
    reach ? Math.sign(over) * reach * Math.expm1(Math.abs(over) / reach) : 0;
  const toShown = (raw: number) => {
    const c = clamp(raw, min, max);
    return c + bend(raw - c);
  };
  const toRaw = (shown: number) => {
    const c = clamp(shown, min, max);
    return c + unbend(shown - c);
  };
  const multiplierOf = (e: Modifiers) =>
    e.shiftKey ? coarseMultiplier : e.altKey ? fineMultiplier : 1;

  const commit = (next: number) => {
    const rounded = clamp(Number(next.toFixed(fineDecimals)), min, max);
    if (rounded === valueRef.current) return;
    valueRef.current = rounded;
    setValue(rounded);
    onChange?.(rounded);
  };

  useMotionValueEvent(display, "change", (d) => {
    if (!typingRef.current && inputRef.current) inputRef.current.value = fmt(d);
    if (chipRef.current)
      chipRef.current.dataset.over = d < min || d > max ? "true" : "false";
  });
  const lean = useTransform(display, (d) =>
    reduce || !reach
      ? 0
      : clamp((d - clamp(d, min, max)) / reach, -1, 1) * LEAN,
  );
  const chipTransform = useMotionTemplate`translateX(${lean}px)`;
  const fill = useTransform(
    display,
    (d) => (clamp(d, min, max) - min) / Math.max(max - min, Number.EPSILON),
  );
  const fillTransform = useMotionTemplate`scaleX(${fill})`;

  const adopt = (next: number) => {
    valueRef.current = next;
    setValue(next);
    display.jump(next);
    if (!typingRef.current && inputRef.current)
      inputRef.current.value = fmt(next);
  };

  useEffect(() => {
    if (controlled && !drag.current && valueProp !== valueRef.current)
      adopt(clamp(valueProp as number, min, max));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [valueProp]);
  useEffect(() => {
    if (!mounted.current) {
      mounted.current = true;
      return;
    }
    if (!controlled && !drag.current) adopt(clamp(defaultValue, min, max));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [defaultValue]);
  useEffect(() => {
    if (!typingRef.current && inputRef.current)
      inputRef.current.value = fmt(valueRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [baseDecimals, fineDecimals]);

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (disabled || drag.current || e.button !== 0 || typingRef.current) return;
    if (e.pointerType !== "touch") e.preventDefault();
    display.stop();
    movedRef.current = false;
    drag.current = {
      id: e.pointerId,
      x: e.clientX,
      raw: toRaw(display.get()),
      mult: multiplierOf(e),
      moved: false,
      before: valueRef.current,
      slack: e.pointerType === "touch" ? 8 : 3,
      left: chipRef.current ? chipRef.current.getBoundingClientRect().left : 0,
    };
    try {
      e.currentTarget.setPointerCapture(e.pointerId);
    } catch {}
    escRef.current = (ev: KeyboardEvent) => {
      if (ev.key === "Escape") endRef.current(true);
    };
    window.addEventListener("keydown", escRef.current);
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const g = drag.current;
    if (!g || e.pointerId !== g.id) return;
    if (!g.moved) {
      if (Math.abs(e.clientX - g.x) < g.slack) return;
      g.moved = true;
      movedRef.current = true;
      g.x = e.clientX;
      setDragging(true);
      document.documentElement.style.cursor = "ew-resize";
    }
    const m = multiplierOf(e);
    if (m !== g.mult) {
      g.mult = m;
      g.raw = toRaw(display.get());
      g.x = e.clientX;
    }
    const raw = g.raw + Math.round((e.clientX - g.x) / sensitivity) * step * m;
    const shown = toShown(raw);
    display.set(shown);
    commit(clamp(raw, min, max));
    if (ghostRef.current) {
      ghostRef.current.style.translate = `calc(${e.clientX - g.left}px - 50%) -100%`;
      ghostRef.current.textContent = signed(shown - g.before);
    }
  };

  const end = (cancel = false) => {
    const g = drag.current;
    if (!g) return;
    drag.current = null;
    setDragging(false);
    document.documentElement.style.cursor = "";
    if (escRef.current) {
      window.removeEventListener("keydown", escRef.current);
      escRef.current = null;
    }
    if (cancel) {
      commit(g.before);
      display.jump(g.before);
      return;
    }
    if (!g.moved) {
      inputRef.current?.focus();
      return;
    }
    const bound = clamp(display.get(), min, max);
    if (display.get() !== bound) {
      if (reduce) display.jump(bound);
      else
        animate(display, bound, {
          ...SPRING_UI,
          duration: returnDuration / 1000,
        });
    }
    if (g.moved && valueRef.current !== g.before) onCommit?.(valueRef.current);
  };
  endRef.current = end;

  const { handleKeyDown, handleFocus, handleBlur } = createEntryHandlers({
    draft,
    setDraft,
    typingRef,
    inputRef,
    valueRef,
    display,
    fmt,
    commit,
    multiplierOf,
    step,
    coarseMultiplier,
    min,
    max,
    onCommit,
  });

  useEffect(
    () => () => {
      document.documentElement.style.cursor = "";
      if (escRef.current) window.removeEventListener("keydown", escRef.current);
    },
    [],
  );

  const dirty = showDirty && value !== defaultValue;
  return {
    id,
    value,
    dragging,
    draft,
    setDraft,
    chipRef,
    inputRef,
    ghostRef,
    movedRef,
    preset,
    fmt,
    chipTransform,
    fillTransform,
    handlePointerDown,
    handlePointerMove,
    end,
    handleKeyDown,
    handleFocus,
    handleBlur,
    dirty,
  };
}
