# Curriculum animation sources

These components were read and downloaded from the official React Bits TypeScript/CSS registry. Copyright (c) 2026 David Haz; the shared [license](../react-bits/LICENSE.md) applies.

- [RotatingText](https://reactbits.dev/r/RotatingText-TS-CSS.json): original spring and per-character transitions retained. Added reduced-motion handling and suspension when the component is outside the viewport or the browser document is hidden. The curriculum reserves text dimensions and uses a 3.4-second interval.
- [GlareHover](https://reactbits.dev/r/GlareHover-TS-CSS.json): original gradient sweep and variables retained. Added keyboard focus feedback, non-intercepting pseudo-elements, and a static reduced-motion variant.

The curriculum also uses existing React Bits `AnimatedContent`, `CountUp`, `ShinyText`, `SpotlightCard`, and `SquishSwitch`. Statistics and availability are computed from the catalogue response; the visual treatment does not imply that planned courses are runnable.

Reviewed but not added: `TiltedCard` is image-oriented and would distort the reading surface; `ScrollFloat` requires extra scroll ownership and cleanup for a mostly text-based course list. The selected effects support the specific navigation and reading interactions here.
