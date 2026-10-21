import { lazy, Suspense } from "react";
import { EffectBoundary, useMotionBudget } from "@studio/motion";
import { useResolvedTheme } from "@studio/hooks/useTheme";
import "@studio/styles/backdrops.css";

const Threads = lazy(() => import("@studio/components/react-bits/Threads"));

// Same mood as the platform's "threads" backdrop preset (components/backdrops/presets.ts).
const COLOR = { dark: [0.78, 0.72, 1], light: [0.55, 0.48, 0.92] } as const;
const FALLBACK =
  "radial-gradient(120% 140% at 85% 0%, #6d5dfc55 0%, transparent 55%), radial-gradient(90% 120% at 10% 100%, #49dec644 0%, transparent 60%)";

/**
 * Decorative hero background. The gradient is always painted; the WebGL shader mounts
 * only at full motion with WebGL, while on screen, and unmounts (losing its context)
 * when scrolled away.
 */
export function HeroBackdrop() {
  const { ref, active } = useMotionBudget<HTMLDivElement>("webgl", {
    margin: "120px",
  });
  const theme = useResolvedTheme();
  return (
    <div ref={ref} className="backdrop" aria-hidden="true" style={{ background: FALLBACK }}>
      {active && (
        <EffectBoundary key={theme}>
          <Suspense fallback={null}>
            <div className="backdrop-canvas">
              <Threads
                color={[...COLOR[theme]] as [number, number, number]}
                amplitude={2.1}
                distance={0.45}
              />
            </div>
          </Suspense>
        </EffectBoundary>
      )}
    </div>
  );
}
