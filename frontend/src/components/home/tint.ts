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
