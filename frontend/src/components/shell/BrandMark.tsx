import { lazy, Suspense, useState } from "react";
import { useTranslation } from "react-i18next";
import { Waypoints } from "lucide-react";
import {
  EffectBoundary,
  useMotionBudget,
  useReducedMotion,
} from "../../motion";
import ShinyText from "../react-bits/ShinyText";

const ElectricLogo = lazy(() => import("../react-bits/ElectricLogo"));

// The Waypoints glyph as a white mask for ElectricLogo to trace: filled nodes
// and thick links read better as an electric outline than hairline strokes.
const glyph = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96" viewBox="0 0 24 24" fill="#fff" stroke="#fff" stroke-width="2.4" stroke-linecap="round"><circle cx="12" cy="4.5" r="2.7"/><path d="m10.2 6.3-3.9 3.9" fill="none"/><circle cx="4.5" cy="12" r="2.7"/><path d="M7 12h10" fill="none"/><circle cx="19.5" cy="12" r="2.7"/><path d="m13.8 17.7 3.9-3.9" fill="none"/><circle cx="12" cy="19.5" r="2.7"/></svg>',
)}`;

/**
 * WebGL electric outline over the brand glyph. Mounted only while the brand is
 * hovered or focused, at full motion with WebGL support (useMotionBudget);
 * unmounting releases the GL context.
 */
function BrandSpark() {
  const { ref, granted } = useMotionBudget<HTMLSpanElement>("webgl");
  return (
    <span ref={ref} className="rail-brand-spark" aria-hidden="true">
      {granted && (
        <EffectBoundary>
          <Suspense fallback={null}>
            <ElectricLogo
              src={glyph}
              color="#efeaff"
              glowColor="#8f7dff"
              scale={0.36}
              glow={0.55}
              intensity={0.85}
              thickness={1.3}
              strands={3}
              crackle={1.2}
              arcs={1.4}
              speed={2}
              interactive={false}
              theme="dark"
            />
          </Suspense>
        </EffectBoundary>
      )}
    </span>
  );
}

/** Sidebar brand: the mark doubles as the way home (disabled while a run is live). */
export function BrandMark({
  running,
  onHome,
}: {
  running: boolean;
  onHome: () => void;
}) {
  const { t } = useTranslation("common");
  const reduced = useReducedMotion();
  const [engaged, setEngaged] = useState(false);
  const spark = engaged && !reduced;
  return (
    <div
      className="rail-brand"
      data-spark={spark || undefined}
      onPointerEnter={(event) => {
        if (event.pointerType === "mouse") setEngaged(true);
      }}
      onPointerLeave={() => setEngaged(false)}
      onFocus={(event) => {
        if (event.target.matches(":focus-visible")) setEngaged(true);
      }}
      onBlur={() => setEngaged(false)}
    >
      <button
        type="button"
        className="rail-brand-mark"
        aria-label={t("shell.brandHome")}
        title={t("shell.brandHome")}
        disabled={running}
        onClick={onHome}
      >
        <i className="rail-brand-halo" aria-hidden="true" />
        <i className="rail-brand-core" aria-hidden="true">
          <Waypoints size={21} />
        </i>
        {spark && <BrandSpark />}
      </button>
      <div>
        <ShinyText
          text="Agent Lab"
          color="var(--text)"
          shineColor="var(--rail-shine)"
          speed={3}
          delay={3}
          disabled={reduced}
        />
        <small>{t("shell.brandTagline")}</small>
      </div>
    </div>
  );
}
