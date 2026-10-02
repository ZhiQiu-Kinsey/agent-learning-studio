// React Bits MagicBento: `npx shadcn@4.21.0 view @react-bits/MagicBento-TS-TW`
// (https://reactbits.dev/r/MagicBento-TS-TW.json).
// Copyright (c) 2026 David Haz. License: MIT + Commons Clause, see ./LICENSE.md.
//
// Changes for Agent Lab:
// - The grid and cards take children instead of the demo card data, so any
//   accessible content (buttons, counts) can live inside a tile.
// - Motion follows src/motion: particles, spotlight, ripple and tilt only run
//   at the "full" level, while the grid is on screen in a visible tab
//   (useMotionBudget), and never on touch / narrow screens. Otherwise the tiles
//   are static with a plain border; focus shows a static glow instead.
// - Only the hovered tile owns particles, so a single looping effect is ever on
//   screen; their infinite tweens are killed on leave (upstream leaked them).
// - Styles moved to MagicBento.css and read theme tokens; class names are
//   prefixed (`magic-bento-*`) to avoid collisions with app styles.
"use client";

import React from "react";
import { useMotionBudget } from "../../motion";
import "./MagicBento.css";
import { DEFAULT_SPOTLIGHT_RADIUS, DEFAULT_GLOW_COLOR } from "./MagicBento/particles";
import { BentoMotion } from "./MagicBento/context";
import { GlobalSpotlight } from "./MagicBento/GlobalSpotlight";
import { useMobileDetection } from "./MagicBento/useMobileDetection";

export { MagicBentoCard } from "./MagicBento/MagicBentoCard";
export type { MagicBentoCardProps } from "./MagicBento/MagicBentoCard";

export interface MagicBentoProps {
  children: React.ReactNode;
  className?: string;
  enableSpotlight?: boolean;
  spotlightRadius?: number;
  /** "r, g, b" for the shared spotlight. */
  glowColor?: string;
  "aria-label"?: string;
  "aria-labelledby"?: string;
  "data-testid"?: string;
}

const MagicBento: React.FC<MagicBentoProps> = ({
  children,
  className = "",
  enableSpotlight = true,
  spotlightRadius = DEFAULT_SPOTLIGHT_RADIUS,
  glowColor = DEFAULT_GLOW_COLOR,
  ...rest
}) => {
  const { ref: gridRef, active } = useMotionBudget<HTMLDivElement>("css");
  const isMobile = useMobileDetection();
  const animate = active && !isMobile;

  return (
    <BentoMotion.Provider value={animate}>
      {enableSpotlight && animate && (
        <GlobalSpotlight
          gridRef={gridRef}
          spotlightRadius={spotlightRadius}
          glowColor={glowColor}
        />
      )}
      <div
        ref={gridRef}
        {...rest}
        className={`magic-bento ${className}`}
        data-animate={animate}
      >
        {children}
      </div>
    </BentoMotion.Provider>
  );
};

export default MagicBento;
