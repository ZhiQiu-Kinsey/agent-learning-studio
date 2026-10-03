/**
 * Where to go when step `index` cannot be shown (its target is missing):
 * onward in the direction the learner is moving, so stepping back past it
 * never bounces forward again. Going back from the first step turns forward.
 * Returns null when there is nowhere left to go: the tour should end.
 */
export function skipTarget(
  index: number,
  direction: 1 | -1,
  total: number,
): number | null {
  const next = index + direction;
  if (next < 0) return index + 1 < total ? index + 1 : null;
  return next < total ? next : null;
}
