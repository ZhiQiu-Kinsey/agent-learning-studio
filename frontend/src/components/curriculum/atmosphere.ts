import {
  backdropFor,
  backdropPresets,
  resolveBackdrop,
  type BackdropName,
} from "../backdrops/presets";
import { rgbChannels } from "../../lib/color";
import type { ResolvedTheme } from "../../hooks/useTheme";

/**
 * Light surfaces need the same hue with more ink: the preset tints are tuned
 * to glow on the dark band and wash out on white (e.g. #d6ceff). Keep the hue,
 * clamp saturation and pull lightness to the middle.
 */
function deepen(hex: string): string {
  const [r, g, b] = rgbChannels(hex)
    .split(" ")
    .map((value) => Number(value) / 255);
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const l = (max + min) / 2;
  const d = max - min;
  let h = 0;
  if (d) {
    if (max === r) h = ((g - b) / d) % 6;
    else if (max === g) h = (b - r) / d + 2;
    else h = (r - g) / d + 4;
  }
  h = (h * 60 + 360) % 360;
  const s0 = d ? d / (1 - Math.abs(2 * l - 1)) : 0;
  const s = Math.min(Math.max(s0, 0.55), 0.82);
  const light = 0.52;
  const c = (1 - Math.abs(2 * light - 1)) * s;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = light - c / 2;
  const [r1, g1, b1] =
    h < 60
      ? [c, x, 0]
      : h < 120
        ? [x, c, 0]
        : h < 180
          ? [0, c, x]
          : h < 240
            ? [0, x, c]
            : h < 300
              ? [x, 0, c]
              : [c, 0, x];
  return [r1, g1, b1].map((v) => Math.round((v + m) * 255)).join(", ");
}

/**
 * Each domain borrows the palette of its hero backdrop (presets.ts), so a
 * domain card's live window and its lesson masthead share one atmosphere.
 * Values are "r, g, b" so MagicBento can derive glow alphas. The light theme
 * gets a deeper shade of the same hue so glows and meters read on white.
 */
export const backdropAccent = (
  name: BackdropName,
  theme: ResolvedTheme = "dark",
): string =>
  theme === "dark"
    ? rgbChannels(backdropPresets[name].tint, ", ")
    : deepen(backdropPresets[name].tint);

export interface DomainAtmosphere {
  backdrop: BackdropName;
  /** "r, g, b" */
  accent: string;
  /** CSS gradient painted while the shader is not live (theme variant). */
  fallback: string;
}

export function domainAtmosphere(
  categoryId: string,
  theme: ResolvedTheme = "dark",
): DomainAtmosphere {
  const backdrop = backdropFor(categoryId);
  return {
    backdrop,
    accent: backdropAccent(backdrop, theme),
    fallback: resolveBackdrop(backdrop, theme).fallback,
  };
}
