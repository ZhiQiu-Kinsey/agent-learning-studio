import { useEffect, useRef } from "react";
import { useMotion } from "../../motion";

/**
 * Page atmosphere behind every view: two slow brand-colour light pools, a soft
 * spotlight that eases toward the mouse, and a static grain texture. Purely
 * decorative. The spotlight's rAF loop runs only while it is catching up with
 * the pointer, never in static motion or a hidden tab; the pools drift with a
 * CSS animation that the motion gate freezes.
 */
export function ShellAmbient() {
  const ref = useRef<HTMLDivElement>(null);
  const { reduced, pageVisible } = useMotion();

  useEffect(() => {
    const el = ref.current;
    if (!el || reduced || !pageVisible) return;
    let x = window.innerWidth * 0.72;
    let y = window.innerHeight * 0.18;
    let tx = x;
    let ty = y;
    let frame = 0;
    const paint = () => {
      el.style.setProperty("--glow-x", `${x.toFixed(1)}px`);
      el.style.setProperty("--glow-y", `${y.toFixed(1)}px`);
    };
    const tick = () => {
      x += (tx - x) * 0.07;
      y += (ty - y) * 0.07;
      paint();
      frame =
        Math.abs(tx - x) + Math.abs(ty - y) > 0.6
          ? requestAnimationFrame(tick)
          : 0;
    };
    const onMove = (event: PointerEvent) => {
      if (event.pointerType !== "mouse") return;
      tx = event.clientX;
      ty = event.clientY;
      if (!frame) frame = requestAnimationFrame(tick);
    };
    paint();
    window.addEventListener("pointermove", onMove, { passive: true });
    return () => {
      window.removeEventListener("pointermove", onMove);
      cancelAnimationFrame(frame);
    };
  }, [reduced, pageVisible]);

  return (
    <div ref={ref} className="shell-ambient" aria-hidden="true">
      <i className="shell-ambient-pool is-violet" />
      <i className="shell-ambient-pool is-teal" />
      <i className="shell-ambient-glow" />
      <i className="shell-ambient-grain" />
    </div>
  );
}
