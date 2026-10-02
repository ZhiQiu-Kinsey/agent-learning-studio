import {
  backdropPresets,
  categoryBackdrop,
  type BackdropName,
} from "../backdrops/presets";

export function categoryTint(categoryId?: string) {
  const name: BackdropName =
    (categoryId && categoryBackdrop[categoryId]) || "threads";
  return {
    name,
    color: backdropPresets[name].tint,
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
