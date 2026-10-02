// Adapted from https://reactbits.dev/r/RubberSegment-TS-TW.json (MIT + Commons Clause, see LICENSE.md).
import { useEffect, useLayoutEffect, useRef } from "react";
import {
  animate,
  useMotionValue,
  useTransform,
  type MotionValue,
} from "motion/react";
import type { RubberSegmentSize } from "../RubberSegment";
import {
  type Slot,
  type Drag,
  EASE_OUT,
  SPRING_UI,
  SPRING_MOMENTUM,
  SPRING_RELAX,
  DILATE,
  HANDOFF,
  MAX_VELOCITY,
  clamp,
} from "./physics";

interface ThumbOptions {
  list: { value: string }[];
  index: number;
  size: RubberSegmentSize;
  radius: number;
  inset: number;
  equalSlots: boolean;
  stretch: number;
  squash: number;
  speed: number;
  reduce: boolean;
}

/** Slot measurement and the two thumb edges: instant jumps, the stretch-and-land travel and the momentum landing. */
export function useRubberThumb({
  list,
  index,
  size,
  radius,
  inset,
  equalSlots,
  stretch,
  squash,
  speed,
  reduce,
}: ThumbOptions) {
  const trackRef = useRef<HTMLDivElement>(null);
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const slots = useRef<Slot[]>([]);
  const box = useRef<DOMRect | null>(null);
  const committed = useRef(index);
  const handoff = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const drag = useRef<Drag | null>(null);
  const gen = useRef(0);

  const edgeL = useMotionValue(0);
  const edgeR = useMotionValue(0);
  const innerW = useMotionValue(0);
  const thumbRadius = Math.max(0, radius - inset);
  const clipPath = useTransform(
    () =>
      `inset(0 ${Math.max(0, innerW.get() - edgeR.get())}px 0 ${Math.max(0, edgeL.get())}px round ${thumbRadius}px)`,
  );

  const t = (seconds: number) => seconds / speed;

  const jumpTo = (i: number) => {
    const s = slots.current[i];
    if (!s) return;
    clearTimeout(handoff.current);
    gen.current += 1;
    edgeL.jump(s.l);
    edgeR.jump(s.r);
  };

  const measure = () => {
    const track = trackRef.current;
    if (!track) return;
    const rect = track.getBoundingClientRect();
    box.current = rect;
    slots.current = list.map((_, i) => {
      const el = itemRefs.current[i];
      if (!el) return { l: 0, r: 0 };
      const r = el.getBoundingClientRect();
      return { l: r.left - rect.left - inset, r: r.right - rect.left - inset };
    });
    innerW.set(rect.width - inset * 2);
    jumpTo(committed.current);
  };

  const listKey = list.map((item) => item.value).join("|");
  useLayoutEffect(() => {
    measure();
    const observer = new ResizeObserver(measure);
    if (trackRef.current) observer.observe(trackRef.current);
    if (typeof document !== "undefined" && document.fonts)
      document.fonts.ready.then(measure);
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [listKey, size, inset, equalSlots]);

  useEffect(() => {
    if (!drag.current && committed.current !== index) {
      committed.current = index;
      jumpTo(index);
    }
  });

  useEffect(
    () => () => {
      clearTimeout(handoff.current);
      edgeL.stop();
      edgeR.stop();
    },
    [edgeL, edgeR],
  );

  const land = (
    to: number,
    v: number | null,
    flick: boolean,
    withSquash: boolean,
  ) => {
    const b = slots.current[to];
    if (!b) return;
    const g = ++gen.current;
    const dir =
      Math.sign((b.l + b.r) / 2 - (edgeL.get() + edgeR.get()) / 2) || 1;
    const [lead, leadTo, trail, trailTo] =
      dir > 0 ? [edgeR, b.r, edgeL, b.l] : [edgeL, b.l, edgeR, b.r];
    const velocityFor = (mv: MotionValue<number>) =>
      clamp(v === null ? mv.getVelocity() : v, -MAX_VELOCITY, MAX_VELOCITY);
    animate(lead, leadTo, {
      ...(flick ? SPRING_MOMENTUM : SPRING_UI),
      duration: t(flick ? 0.4 : 0.3),
      velocity: velocityFor(lead),
    });
    const trailVelocity = velocityFor(trail);
    if (!withSquash || squash <= 0) {
      animate(trail, trailTo, {
        ...SPRING_UI,
        duration: t(0.3),
        velocity: trailVelocity,
      });
      return;
    }
    animate(trail, trailTo + dir * squash, {
      ...SPRING_UI,
      duration: t(0.3),
      velocity: trailVelocity,
    }).then(() => {
      if (gen.current === g)
        animate(trail, trailTo, { ...SPRING_RELAX, duration: t(0.16) });
    });
  };

  const travel = (from: number, to: number) => {
    const a = slots.current[from];
    const b = slots.current[to];
    if (!a || !b) return;
    clearTimeout(handoff.current);
    gen.current += 1;
    if (reduce) {
      edgeL.jump(b.l);
      edgeR.jump(b.r);
      return;
    }
    const u = stretch / 100;
    const tween = { duration: t(DILATE), ease: EASE_OUT };
    animate(edgeL, b.l + (Math.min(a.l, b.l) - b.l) * u, tween);
    animate(edgeR, b.r + (Math.max(a.r, b.r) - b.r) * u, tween);
    handoff.current = setTimeout(
      () => land(to, null, false, true),
      t(HANDOFF) * 1000,
    );
  };

  return {
    trackRef,
    itemRefs,
    slots,
    box,
    committed,
    handoff,
    drag,
    gen,
    edgeL,
    edgeR,
    innerW,
    thumbRadius,
    clipPath,
    jumpTo,
    land,
    travel,
  };
}
