import { Component, type ReactNode } from "react";

/**
 * Decorative effects (WebGL shaders, 3D, WASM) must never take the page down:
 * if one throws while loading or rendering, show its static fallback instead.
 */
export class EffectBoundary extends Component<
  { fallback?: ReactNode; children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: unknown) {
    console.warn("Decorative effect disabled after an error:", error);
  }

  render() {
    return this.state.failed
      ? (this.props.fallback ?? null)
      : this.props.children;
  }
}
