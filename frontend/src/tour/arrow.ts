/**
 * Triangle for the tour card's arrow. Joyride sizes the arrow's box per side
 * (base × size above or below the card, size × base beside it) but does not
 * rotate a custom arrow, so each side gets its own points — the same geometry
 * as Joyride's built-in arrow. The tip always points at the framed element.
 */
export function arrowShape(placement: string, base: number, size: number) {
  const side = placement.split("-")[0];
  const points: Record<string, string> = {
    top: `0,0 ${base / 2},${size} ${base},0`,
    bottom: `${base},${size} ${base / 2},0 0,${size}`,
    left: `0,0 ${size},${base / 2} 0,${base}`,
    right: `${size},${base} ${size},0 0,${base / 2}`,
  };
  if (!(side in points)) return null;
  const vertical = side === "left" || side === "right";
  const [width, height] = vertical ? [size, base] : [base, size];
  return { width, height, points: points[side] };
}
