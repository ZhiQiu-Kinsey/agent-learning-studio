// Adapted from https://reactbits.dev/r/BorderGlow-TS-TW.json (MIT + Commons Clause).

export function easeOutCubic(x: number) {
  return 1 - Math.pow(1 - x, 3);
}
export function easeInCubic(x: number) {
  return x * x * x;
}

interface AnimateOpts {
  start?: number;
  end?: number;
  duration?: number;
  delay?: number;
  ease?: (t: number) => number;
  onUpdate: (v: number) => void;
  onEnd?: () => void;
}

export function animateValue({
  start = 0,
  end = 100,
  duration = 1000,
  delay = 0,
  ease = easeOutCubic,
  onUpdate,
  onEnd,
}: AnimateOpts) {
  const t0 = performance.now() + delay;
  let raf = 0;
  let cancelled = false;
  function tick() {
    if (cancelled) return;
    const elapsed = performance.now() - t0;
    const t = Math.min(elapsed / duration, 1);
    onUpdate(start + (end - start) * ease(t));
    if (t < 1) raf = requestAnimationFrame(tick);
    else if (onEnd) onEnd();
  }
  const timer = setTimeout(() => {
    raf = requestAnimationFrame(tick);
  }, delay);
  return () => {
    cancelled = true;
    clearTimeout(timer);
    cancelAnimationFrame(raf);
  };
}
