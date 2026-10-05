// Adapted from https://reactbits.dev/r/GlideSelect-TS-TW.json (MIT + Commons Clause).
import React, {
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import {
  type Phase,
  SIZES,
  PAD,
  GAP,
  menuPlacement,
  norm,
  typeaheadIndex,
} from "./utils";
import type { GlideSelectOption, GlideSelectProps } from "../GlideSelect";

/** The viewport, cut down by every ancestor that scrolls or clips its content. */
function visibleBounds(element: HTMLElement) {
  let top = 0;
  let bottom = window.innerHeight;
  for (
    let node = element.parentElement;
    node && node !== document.documentElement;
    node = node.parentElement
  ) {
    const style = getComputedStyle(node);
    if (style.overflowY === "visible" && style.overflowX === "visible")
      continue;
    const rect = node.getBoundingClientRect();
    // The padding box: content inside scrolls or is cut off there, not at the border.
    top = Math.max(top, rect.top + node.clientTop);
    bottom = Math.min(bottom, rect.top + node.clientTop + node.clientHeight);
  }
  return { top, bottom };
}

interface GlideSelectOptions {
  options: (string | GlideSelectOption)[];
  value: string | undefined;
  defaultValue: string | undefined;
  onChange: GlideSelectProps["onChange"];
  size: "sm" | "md" | "lg";
  placement: "top" | "bottom";
  popDuration: number;
  rememberPosition: boolean;
  disabled: boolean;
}

/** Selection state, menu open/close phases, the gliding highlight pill, keyboard and pointer scrubbing. */
export function useGlideSelect({
  options,
  value,
  defaultValue,
  onChange,
  size,
  placement,
  popDuration,
  rememberPosition,
  disabled,
}: GlideSelectOptions) {
  const items = options.map(norm);
  const [inner, setInner] = useState(defaultValue ?? "");
  const current = value ?? inner;
  const selected = items.findIndex((it) => it.value === current);
  const [phase, setPhase] = useState<Phase>("closed");
  const [active, setActive] = useState<number | null>(null);
  const [side, setSide] = useState<"top" | "bottom">(placement);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const pillRef = useRef<HTMLSpanElement>(null);
  const instant = useRef(false);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | undefined>(
    undefined,
  );
  const scrub = useRef<{ id: number; top: number } | null>(null);
  const id = useId();
  const S = SIZES[size] ?? SIZES.md;
  const step = S.row + GAP;
  const popOut = Math.round((popDuration * 2) / 3);

  useLayoutEffect(() => {
    if (phase !== "open") return;
    const el = menuRef.current;
    const root = rootRef.current;
    if (!el || !root) return;
    // Measure the full menu, then fit it inside what is actually visible: a
    // dialog that scrolls clips the menu long before the window edge does.
    el.style.maxHeight = "";
    el.style.overflowY = "";
    const r = root.getBoundingClientRect();
    const fit = menuPlacement(
      r,
      visibleBounds(root),
      el.offsetHeight,
      placement,
      S.row + PAD * 2,
    );
    setSide(fit.side);
    if (fit.maxHeight !== null) {
      el.style.maxHeight = `${fit.maxHeight}px`;
      el.style.overflowY = "auto";
      el.scrollTop = Math.max(0, selected) * step - fit.maxHeight / 2;
    }
    el.style.transitionDuration = instant.current ? "0ms" : "";
    el.dataset.state = "closed";
    void el.offsetHeight;
    el.dataset.state = "open";
    const p = pillRef.current;
    if (p) {
      p.style.transition = "none";
      p.style.transform = `translateY(${Math.max(0, selected) * step}px)`;
      p.style.opacity = "0";
      void p.offsetHeight;
      p.style.transition = "";
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase]);

  useLayoutEffect(() => {
    const p = pillRef.current;
    if (!p || phase !== "open") return;
    if (active === null) {
      p.style.opacity = "0";
      return;
    }
    const jump = instant.current || p.style.opacity !== "1";
    p.style.transitionDuration = jump ? "0ms, 150ms" : "";
    p.style.transform = `translateY(${active * step}px)`;
    p.style.opacity = "1";
    instant.current = false;
    // A height-capped menu scrolls; keep the active row (keyboard) in view.
    const menu = menuRef.current;
    if (menu && menu.scrollHeight > menu.clientHeight) {
      const top = PAD + active * step;
      if (top < menu.scrollTop) menu.scrollTop = top - PAD;
      else if (top + S.row > menu.scrollTop + menu.clientHeight)
        menu.scrollTop = top + S.row + PAD - menu.clientHeight;
    }
  }, [active, phase, step, S.row]);

  const open = (viaKey: boolean) => {
    if (disabled) return;
    clearTimeout(closeTimer.current);
    instant.current = true;
    setActive(selected >= 0 ? selected : viaKey ? 0 : null);
    setPhase("open");
  };
  const close = (mode: "instant" | "pop") => {
    setActive(null);
    clearTimeout(closeTimer.current);
    const el = menuRef.current;
    if (mode === "instant" || !el) {
      setPhase("closed");
      return;
    }
    el.style.transitionDuration = "";
    el.dataset.state = "closed";
    setPhase("closing");
    closeTimer.current = setTimeout(() => setPhase("closed"), popOut + 20);
  };
  const pick = (i: number, viaKey: boolean) => {
    const it = items[i];
    if (!it) {
      close("instant");
      return;
    }
    if (it.value !== current) {
      if (value === undefined) setInner(it.value);
      onChange?.(it.value, it);
      if (!viaKey && rootRef.current) rootRef.current.dataset.swap = "";
    }
    close("instant");
    triggerRef.current?.focus({ preventScroll: true });
  };

  const onTriggerKey = (e: React.KeyboardEvent<HTMLButtonElement>) => {
    const k = e.key;
    const n = items.length;
    const cur = active ?? Math.max(0, selected);
    if (phase !== "open") {
      if (k === "Enter" || k === " " || k === "ArrowDown" || k === "ArrowUp") {
        e.preventDefault();
        open(true);
      }
      return;
    }
    const go = (i: number) => {
      e.preventDefault();
      instant.current = true;
      setActive(Math.min(n - 1, Math.max(0, i)));
    };
    if (k === "ArrowDown" || k === "ArrowUp")
      go(active === null ? cur : cur + (k === "ArrowDown" ? 1 : -1));
    else if (k === "Home" || k === "End") go(k === "Home" ? 0 : n - 1);
    else if (k === "Enter" || k === " ") {
      e.preventDefault();
      pick(cur, true);
    } else if (k === "Escape" || k === "Tab") {
      if (k === "Escape") e.preventDefault();
      close("instant");
    } else if (k.length === 1 && !e.metaKey && !e.ctrlKey && !e.altKey)
      go(typeaheadIndex(items, cur, k));
  };

  useEffect(() => {
    if (phase === "closed") return undefined;
    const onDown = (e: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node))
        close("pop");
    };
    document.addEventListener("pointerdown", onDown, true);
    return () => document.removeEventListener("pointerdown", onDown, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase]);
  useEffect(() => {
    if (disabled && phase !== "closed") close("instant");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [disabled]);
  useEffect(() => () => clearTimeout(closeTimer.current), []);

  const rowAt = (y: number) => {
    const s = scrub.current;
    if (!s) return null;
    const i = Math.floor((y - s.top - PAD) / step);
    return i >= 0 && i < items.length ? i : null;
  };
  const onListDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (scrub.current) return;
    try {
      e.currentTarget.setPointerCapture(e.pointerId);
    } catch {}
    scrub.current = {
      id: e.pointerId,
      top: e.currentTarget.getBoundingClientRect().top,
    };
    instant.current = true;
    setActive(rowAt(e.clientY));
  };
  const onListMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!scrub.current || scrub.current.id !== e.pointerId) return;
    const i = rowAt(e.clientY);
    if (i !== active) setActive(i);
  };
  const onListUp = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!scrub.current || scrub.current.id !== e.pointerId) return;
    const i = e.type === "pointerup" ? rowAt(e.clientY) : null;
    scrub.current = null;
    if (i !== null) pick(i, false);
    else if (!rememberPosition) setActive(null);
  };
  const onListOver = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.pointerType === "touch" || scrub.current) return;
    const row = (e.target as HTMLElement).closest<HTMLElement>("[data-index]");
    if (!row) return;
    const i = Number(row.dataset.index);
    if (i !== active) setActive(i);
  };
  return {
    items,
    current,
    selected,
    phase,
    active,
    setActive,
    side,
    rootRef,
    triggerRef,
    menuRef,
    pillRef,
    scrub,
    id,
    S,
    popOut,
    open,
    close,
    onTriggerKey,
    onListDown,
    onListMove,
    onListUp,
    onListOver,
  };
}
