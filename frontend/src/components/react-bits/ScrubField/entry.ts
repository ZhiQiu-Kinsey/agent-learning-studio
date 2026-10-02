// Adapted from https://reactbits.dev/r/ScrubField-TS-TW.json (MIT + Commons Clause, see LICENSE.md).
import type { Dispatch, RefObject, SetStateAction } from "react";
import type { MotionValue } from "motion/react";
import type { Modifiers } from "./utils";

interface EntryOptions {
  draft: string | null;
  setDraft: Dispatch<SetStateAction<string | null>>;
  typingRef: RefObject<boolean>;
  inputRef: RefObject<HTMLInputElement | null>;
  valueRef: RefObject<number>;
  display: MotionValue<number>;
  fmt: (v: number) => string;
  commit: (next: number) => void;
  multiplierOf: (e: Modifiers) => number;
  step: number;
  coarseMultiplier: number;
  min: number;
  max: number;
  onCommit?: (value: number) => void;
}

/** Typed entry and keyboard stepping on the number input. */
export const createEntryHandlers = ({
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
}: EntryOptions) => {
  const leaveTyping = () => {
    typingRef.current = false;
    setDraft(null);
    if (inputRef.current) inputRef.current.value = fmt(valueRef.current);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    const typedNumber =
      draft !== null && draft.trim() !== "" ? Number(draft) : NaN;
    const from = Number.isNaN(typedNumber) ? valueRef.current : typedNumber;
    const deltas: Record<string, number> = {
      ArrowUp: step * multiplierOf(e),
      ArrowDown: -step * multiplierOf(e),
      PageUp: step * coarseMultiplier,
      PageDown: -step * coarseMultiplier,
    };
    const delta = deltas[e.key];
    if (delta !== undefined || e.key === "Home" || e.key === "End") {
      e.preventDefault();
      leaveTyping();
      commit(delta !== undefined ? from + delta : e.key === "Home" ? min : max);
      display.jump(valueRef.current);
      if (inputRef.current) inputRef.current.value = fmt(valueRef.current);
      onCommit?.(valueRef.current);
    } else if (e.key === "Enter") {
      e.preventDefault();
      e.currentTarget.blur();
    } else if (e.key === "Escape") {
      e.preventDefault();
      leaveTyping();
      e.currentTarget.blur();
    }
  };

  const handleFocus = (e: React.FocusEvent<HTMLInputElement>) => {
    typingRef.current = true;
    setDraft(e.target.value);
    e.target.select();
  };

  const handleBlur = () => {
    const n = draft === null ? NaN : parseFloat(draft.replace(/[^\d.-]/g, ""));
    if (!Number.isNaN(n)) {
      commit(n);
      onCommit?.(valueRef.current);
    }
    leaveTyping();
    display.jump(valueRef.current);
  };

  return { handleKeyDown, handleFocus, handleBlur };
};
