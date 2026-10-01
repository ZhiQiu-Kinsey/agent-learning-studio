/** Motion tokens shared by JS animations; CSS mirrors them in styles/tokens.css. */
export const ease = [0.16, 1, 0.3, 1] as const;

export const duration = {
  fast: 0.12,
  base: 0.16,
  fold: 0.22,
  slow: 0.32,
} as const;

/** Default transition for motion/react elements. */
export const baseTransition = { duration: duration.base, ease } as const;
export const foldTransition = { duration: duration.fold, ease } as const;
