/**
 * "#rrggbb" -> CSS rgb() channels: "r g b" by default, "r, g, b" with
 * sep ", " (for legacy rgba() strings and `--*-rgb` custom properties).
 */
export function rgbChannels(hex: string, sep = " "): string {
  const value = hex.replace("#", "");
  return [0, 2, 4]
    .map((offset) => parseInt(value.slice(offset, offset + 2), 16))
    .join(sep);
}
