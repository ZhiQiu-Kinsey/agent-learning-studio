import {
  lazy,
  Suspense,
  type ComponentType,
  type LazyExoticComponent,
} from "react";
import { EffectBoundary, useMotionBudget } from "../../motion";
import { backdropPresets, resolveBackdrop, type BackdropName } from "./presets";
import { useResolvedTheme } from "../../hooks/useTheme";
import "../../styles/backdrops.css";

// Each preset loads its React Bits shader on demand; props stay in presets.ts.
type AnyComponent = ComponentType<Record<string, unknown>>;
const loaded = new Map<BackdropName, LazyExoticComponent<AnyComponent>>();
function lazyBackdrop(name: BackdropName) {
  let component = loaded.get(name);
  if (!component) {
    component = lazy(
      backdropPresets[name].load as () => Promise<{ default: AnyComponent }>,
    );
    loaded.set(name, component);
  }
  return component;
}

/**
 * Living background for hero bands, in the applied theme's variant (the shader
 * remounts when the theme changes). A CSS gradient in the preset's palette is
 * always painted underneath; the WebGL shader mounts only at full motion, while
 * on screen in a visible tab and holding the shared WebGL slot, and fades in on
 * top. Leaving the viewport unmounts it, which releases the GPU context.
 */
export function Backdrop({
  name,
  className = "",
  props,
}: {
  name: BackdropName;
  className?: string;
  /** Overrides merged over the preset's tuned props. */
  props?: Record<string, unknown>;
}) {
  const { ref, active } = useMotionBudget<HTMLDivElement>("webgl", {
    margin: "120px",
  });
  const theme = useResolvedTheme();
  const { shader, props: themed, fallback } = resolveBackdrop(name, theme);
  const Effect = lazyBackdrop(shader);
  return (
    <div
      ref={ref}
      className={`backdrop ${className}`}
      data-backdrop={name}
      data-theme-variant={theme}
      aria-hidden="true"
      style={{ background: fallback }}
    >
      {active && (
        <EffectBoundary key={`${shader}-${theme}`}>
          <Suspense fallback={null}>
            <div className="backdrop-canvas">
              <Effect {...themed} {...props} />
            </div>
          </Suspense>
        </EffectBoundary>
      )}
    </div>
  );
}

export { categoryBackdrop, type BackdropName } from "./presets";
