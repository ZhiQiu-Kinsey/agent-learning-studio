import {
  lazy,
  Suspense,
  type ComponentType,
  type LazyExoticComponent,
} from "react";
import { EffectBoundary, useMotionBudget } from "../../motion";
import { backdropPresets, type BackdropName } from "./presets";
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
 * Living background for hero bands. A CSS gradient in the preset's palette is
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
  const preset = backdropPresets[name];
  const Effect = lazyBackdrop(name);
  return (
    <div
      ref={ref}
      className={`backdrop ${className}`}
      data-backdrop={name}
      aria-hidden="true"
      style={{ background: preset.fallback }}
    >
      {active && (
        <EffectBoundary key={name}>
          <Suspense fallback={null}>
            <div className="backdrop-canvas">
              <Effect {...preset.props} {...props} />
            </div>
          </Suspense>
        </EffectBoundary>
      )}
    </div>
  );
}

export { categoryBackdrop, type BackdropName } from "./presets";
