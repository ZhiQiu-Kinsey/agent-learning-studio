/**
 * Backdrop presets: one React Bits shader per mood. `props`/`fallback` are tuned
 * for dark hero bands; `light` adapts the same mood to the light theme (most
 * shaders take `lightMode`; the rest get light-friendly colours or swap to a
 * sibling preset). `fallback` is the CSS gradient painted under (and instead
 * of) the shader, so static motion and missing WebGL keep the same palette.
 */
const brand = {
  violet: "#6d5dfc",
  teal: "#49dec6",
  lilac: "#b98aff",
  coral: "#ff9473",
  mint: "#6fd39a",
  ink: "#0d0b18",
};

interface Preset {
  /** Accent that carries the mood onto light surfaces (nav dots, card bars). */
  tint: string;
  load: () => Promise<{ default: unknown }>;
  props: Record<string, unknown>;
  fallback: string;
  light?: {
    /** Merged over `props` in the light theme. */
    props?: Record<string, unknown>;
    /** Use another preset's shader in the light theme (e.g. additive light rays vanish on white). */
    use?: string;
  };
}

const glow = (a: string, b: string) =>
  `radial-gradient(120% 140% at 85% 0%, ${a}55 0%, transparent 55%), radial-gradient(90% 120% at 10% 100%, ${b}44 0%, transparent 60%), ${brand.ink}`;

export const backdropPresets = {
  threads: {
    tint: "#a99bff",
    load: () => import("../react-bits/Threads"),
    props: { color: [0.7, 0.65, 1], amplitude: 1.4, distance: 0.45, enableMouseInteraction: true },
    fallback: glow(brand.violet, brand.teal),
    light: { props: { color: [0.55, 0.48, 0.92] } },
  },
  blinds: {
    tint: "#49dec6",
    load: () => import("../react-bits/GradientBlinds"),
    props: {
      gradientColors: [brand.violet, brand.teal],
      angle: 20,
      noise: 0.12,
      blindCount: 8,
      blindMinWidth: 90,
      spotlightRadius: 0.5,
      spotlightOpacity: 0.5,
      distortAmount: 0.1,
      mixBlendMode: "lighten",
      lightMode: false,
    },
    fallback: glow(brand.teal, brand.violet),
    light: { props: { lightMode: true } },
  },
  grainient: {
    tint: "#b98aff",
    load: () => import("../react-bits/Grainient"),
    props: {
      color1: "#7c5cff",
      color2: "#2b1d6e",
      color3: "#0d0b18",
      timeSpeed: 0.12,
      grainAmount: 0.05,
      lightMode: false,
    },
    fallback: glow(brand.lilac, brand.violet),
    light: {
      props: {
        lightMode: true,
        grainAmount: 0.02,
        color1: "#b9a8ff",
        color2: "#d9d0ff",
        color3: "#f4f2ff",
      },
    },
  },
  rays: {
    tint: "#d6ceff",
    load: () => import("../react-bits/LightRays"),
    props: {
      raysOrigin: "top-center",
      raysColor: "#d6ceff",
      raysSpeed: 0.7,
      lightSpread: 1.2,
      rayLength: 2.2,
      followMouse: true,
      mouseInfluence: 0.12,
      noiseAmount: 0.08,
      distortion: 0.05,
      lightMode: false,
    },
    fallback: `radial-gradient(80% 120% at 50% -10%, #c9c0ff44 0%, transparent 60%), ${brand.ink}`,
    light: { props: { lightMode: true } },
  },
  galaxy: {
    tint: "#7aa2ff",
    load: () => import("../react-bits/Galaxy"),
    props: {
      density: 0.8,
      glowIntensity: 0.2,
      saturation: 0.45,
      hueShift: 200,
      twinkleIntensity: 0.25,
      rotationSpeed: 0.02,
      mouseRepulsion: true,
      repulsionStrength: 1.5,
      transparent: true,
      lightMode: false,
    },
    fallback: glow(brand.violet, "#2a6df4"),
    light: { props: { lightMode: true, density: 0.35, glowIntensity: 0.12, twinkleIntensity: 0.15 } },
  },
  ripple: {
    tint: "#c9a6ff",
    load: () => import("../react-bits/RippleGrid"),
    props: {
      gridColor: brand.lilac,
      rippleIntensity: 0.03,
      gridSize: 7,
      gridThickness: 10,
      glowIntensity: 0.08,
      opacity: 0.6,
      mouseInteraction: true,
      lightMode: false,
    },
    fallback: glow(brand.lilac, brand.teal),
    light: { props: { lightMode: true } },
  },
  terminal: {
    tint: "#6fd39a",
    load: () => import("../react-bits/FaultyTerminal"),
    props: {
      scale: 1.6,
      digitSize: 2.4,
      timeScale: 0.25,
      scanlineIntensity: 0.25,
      glitchAmount: 0.3,
      flickerAmount: 0.3,
      curvature: 0.12,
      tint: brand.mint,
      mouseReact: true,
      mouseStrength: 0.25,
      pageLoadAnimation: true,
      brightness: 0.45,
      lightMode: false,
    },
    fallback: glow(brand.mint, brand.teal),
    light: { props: { lightMode: true } },
  },
  radar: {
    tint: "#49dec6",
    load: () => import("../react-bits/Radar"),
    props: {
      color: brand.teal,
      backgroundColor: brand.ink,
      ringCount: 5,
      spokeCount: 6,
      sweepSpeed: 0.4,
      brightness: 0.6,
      enableMouseInteraction: true,
      lightMode: false,
    },
    fallback: glow(brand.teal, brand.mint),
    light: { props: { lightMode: true, backgroundColor: "#f4f2ff" } },
  },
  web: {
    tint: "#ff9473",
    load: () => import("../react-bits/WebThreads"),
    props: {
      color1: brand.violet,
      color2: brand.teal,
      color3: brand.coral,
      speed: 0.4,
      brightness: 0.4,
      opacity: 0.7,
      mouseInteraction: true,
      backgroundColor: brand.ink,
      lightMode: false,
    },
    fallback: glow(brand.coral, brand.violet),
    light: { props: { lightMode: true, backgroundColor: "#f4f2ff", brightness: 0.8, opacity: 0.85 } },
  },
  aurora: {
    tint: "#7ce8d6",
    load: () => import("../react-bits/SoftAurora"),
    props: {
      color1: brand.teal,
      color2: brand.lilac,
      speed: 0.35,
      brightness: 0.7,
      enableMouseInteraction: true,
      lightMode: false,
    },
    fallback: glow(brand.teal, brand.lilac),
    light: { props: { lightMode: true } },
  },
  veil: {
    tint: "#b98aff",
    load: () => import("../react-bits/DarkVeil"),
    props: {
      hueShift: 18,
      noiseIntensity: 0.02,
      scanlineIntensity: 0.06,
      scanlineFrequency: 2.2,
      speed: 0.3,
      warpAmount: 0.2,
      resolutionScale: 1,
      lightMode: false,
    },
    fallback: glow(brand.violet, brand.lilac),
    light: { props: { lightMode: true } },
  },
  topography: {
    tint: "#6d5dfc",
    load: () => import("../react-bits/Topography"),
    props: {
      lowColor: "#241b5c",
      midColor: brand.violet,
      highColor: brand.teal,
      speed: 0.2,
      bands: 1.2,
      scale: 1.4,
      glow: 0.35,
      opacity: 0.55,
      mouseInteraction: true,
      lightMode: false,
    },
    fallback: glow(brand.violet, brand.teal),
    light: { props: { lightMode: true, opacity: 0.4 } },
  },
  orb: {
    tint: "#a99bff",
    load: () => import("../react-bits/Orb"),
    props: { hue: 0, hoverIntensity: 0.35, rotateOnHover: true, backgroundColor: brand.ink },
    fallback: `radial-gradient(40% 60% at 50% 50%, ${brand.violet}55 0%, transparent 70%), ${brand.ink}`,
    light: { props: { backgroundColor: "#f4f2ff" } },
  },
  lightfall: {
    tint: "#b98aff",
    load: () => import("../react-bits/Lightfall"),
    props: {
      colors: [brand.lilac, brand.violet, brand.teal, "#d6ceff"],
      backgroundColor: brand.violet,
      speed: 0.3,
      streakCount: 2,
      streakWidth: 1,
      streakLength: 1.1,
      glow: 0.5,
      density: 0.4,
      twinkle: 0.4,
      zoom: 3,
      backgroundGlow: 0.4,
      opacity: 0.8,
      dpr: 1,
      mouseInteraction: false,
      lightMode: false,
    },
    fallback: glow(brand.lilac, brand.violet),
    light: { props: { lightMode: true } },
  },
  molten: {
    tint: "#ff9473",
    load: () => import("../react-bits/MoltenMetal"),
    props: {
      color1: brand.violet,
      color2: brand.coral,
      color3: "#ffe0c8",
      speed: 0.25,
      glow: 0.6,
      brightness: 0.7,
      grain: true,
      grainIntensity: 0.03,
      mouseInteraction: true,
      backgroundColor: brand.ink,
      lightMode: false,
    },
    fallback: glow(brand.coral, brand.violet),
    light: { props: { lightMode: true, backgroundColor: "#f4f2ff" } },
  },
  sideRays: {
    tint: "#b98aff",
    load: () => import("../react-bits/SideRays"),
    props: {
      rayColor1: brand.lilac,
      rayColor2: brand.teal,
      speed: 0.5,
      intensity: 0.8,
      spread: 0.9,
      opacity: 0.75,
    },
    fallback: glow(brand.lilac, brand.teal),
    light: { use: "rays" },
  },
} satisfies Record<string, Preset>;

export type BackdropName = keyof typeof backdropPresets;

const lightGlow = (tint: string) =>
  `radial-gradient(120% 140% at 85% 0%, ${tint}40 0%, transparent 55%), radial-gradient(90% 120% at 10% 100%, ${tint}2e 0%, transparent 60%), #f4f2ff`;

/** Shader, props and fallback for a preset in the applied theme. */
export function resolveBackdrop(name: BackdropName, theme: "light" | "dark") {
  const preset: Preset = backdropPresets[name];
  if (theme === "dark")
    return { shader: name, props: preset.props, fallback: preset.fallback };
  const shader = (preset.light?.use as BackdropName | undefined) ?? name;
  const base: Preset = backdropPresets[shader];
  return {
    shader,
    props: { ...base.props, ...base.light?.props },
    fallback: lightGlow(preset.tint),
  };
}

/** Each curriculum domain has its own atmosphere on lesson and map hero bands. */
export const categoryBackdrop: Record<string, BackdropName> = {
  A: "aurora", // 原生基础: one glowing loop running through
  B: "blinds", // 任务与接口: crisp contract slats
  C: "sideRays", // 上下文与状态: light entering the window from the side
  R: "rays", // 推理与控制: light rays of attention
  D: "galaxy", // 知识与检索: a field of documents
  E: "molten", // 框架与编排: parts fused into one runtime
  K: "terminal", // 编码 Agent: a terminal
  F: "radar", // 质量与可靠性: monitoring sweep
  G: "web", // 协议与工具: connections
  H: "threads", // 综合实践: every thread woven together
};
export const backdropFor = (categoryId?: string): BackdropName =>
  (categoryId && categoryBackdrop[categoryId]) || "threads";
/** Accent colour of a curriculum domain, shared by nav, cards and hero bands. */
export const tintFor = (categoryId?: string) =>
  backdropPresets[backdropFor(categoryId)].tint;
