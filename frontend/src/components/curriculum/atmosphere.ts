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
const presetAccent: Record<BackdropName, string> = {
  threads: "150, 134, 255",
  blinds: "73, 222, 198",
  grainient: "185, 138, 255",
  rays: "214, 206, 255",
  galaxy: "96, 146, 255",
  ripple: "222, 142, 255",
  terminal: "111, 211, 154",
  radar: "64, 200, 230",
  web: "255, 148, 115",
  aurora: "120, 230, 200",
  veil: "139, 120, 230",
  topography: "109, 93, 252",
  orb: "109, 93, 252",
};

/** "r, g, b" accent that matches a backdrop preset's palette. */
export const backdropAccent = (name: BackdropName): string =>
  presetAccent[name];

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
    accent: presetAccent[backdrop],
    fallback: backdropPresets[backdrop].fallback,
  };
}
