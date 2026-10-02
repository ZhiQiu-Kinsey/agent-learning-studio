import {
  backdropFor,
  backdropPresets,
  type BackdropName,
} from "../backdrops/presets";

/**
 * Each domain borrows the palette of its hero backdrop (presets.ts), so a
 * domain card, its hover preview and its lesson masthead share one atmosphere.
 * Values are "r, g, b" so MagicBento can derive glow alphas.
 */
export const backdropAccent = (name: BackdropName): string =>
  rgbChannels(backdropPresets[name].tint);

const rgbChannels = (hex: string) =>
  [1, 3, 5].map((at) => parseInt(hex.slice(at, at + 2), 16)).join(", ");

export interface DomainAtmosphere {
  backdrop: BackdropName;
  /** "r, g, b" */
  accent: string;
  /** CSS gradient painted while the shader is not live. */
  fallback: string;
}

export function domainAtmosphere(categoryId: string): DomainAtmosphere {
  const backdrop = backdropFor(categoryId);
  return {
    backdrop,
    accent: backdropAccent(backdrop),
    fallback: backdropPresets[backdrop].fallback,
  };
}
