import {
  backdropPresets,
  categoryBackdrop,
  resolveBackdrop,
  type BackdropName,
} from "../backdrops/presets";
import type { ResolvedTheme } from "../../hooks/useTheme";

/** A domain's accent and its window gradient in the applied theme. */
export function categoryTint(
  categoryId: string | undefined,
  theme: ResolvedTheme,
) {
  const name: BackdropName =
    (categoryId && categoryBackdrop[categoryId]) || "threads";
  return {
    name,
    color: backdropPresets[name].tint,
    sky: resolveBackdrop(name, theme).fallback,
  };
}
