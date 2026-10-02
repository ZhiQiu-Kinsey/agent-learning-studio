import {
  backdropPresets,
  categoryBackdrop,
  type BackdropName,
} from "../backdrops/presets";

/** Accent per backdrop mood, so a domain card carries its lesson band's colour. */
const tints: Partial<Record<BackdropName, string>> = {
  threads: "#a99bff",
  blinds: "#49dec6",
  grainient: "#b98aff",
  rays: "#d6ceff",
  galaxy: "#7aa2ff",
  ripple: "#c9a6ff",
  terminal: "#6fd39a",
  radar: "#49dec6",
  web: "#ff9473",
  aurora: "#7ce8d6",
  veil: "#b98aff",
  topography: "#6d5dfc",
  orb: "#a99bff",
  lightfall: "#b98aff",
};

export function categoryTint(categoryId?: string) {
  const name: BackdropName =
    (categoryId && categoryBackdrop[categoryId]) || "threads";
  return {
    name,
    color: tints[name] ?? "#a99bff",
    sky: backdropPresets[name].fallback,
  };
}

/** "#rrggbb" -> "r g b" (CSS rgb() channels) or "r, g, b" with sep ", ". */
export function rgbOf(hex: string, sep = " ") {
  const value = hex.replace("#", "");
  return [0, 2, 4]
    .map((offset) => parseInt(value.slice(offset, offset + 2), 16))
    .join(sep);
}
