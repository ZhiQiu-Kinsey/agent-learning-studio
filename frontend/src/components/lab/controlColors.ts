/** Theme colours for the lab's React Bits controls, from the design tokens. */

/** RubberSegment: muted track, surface thumb. */
export const segmentColors = {
  trackColor: "var(--surface-muted)",
  thumbColor: "var(--surface)",
  textColor: "var(--text-muted)",
  activeTextColor: "var(--text)",
} as const;

/** GlideSelect with the accent colour for the chosen option. */
export const pickerColors = {
  surfaceColor: "var(--surface)",
  textColor: "var(--text)",
  accentColor: "var(--accent)",
  highlightColor: "var(--surface-muted)",
} as const;
