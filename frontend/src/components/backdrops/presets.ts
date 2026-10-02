/**
 * Backdrop presets: one React Bits shader per mood, tuned for the always-dark
 * hero bands. `fallback` is the CSS gradient painted under (and instead of)
 * the shader, so static motion and missing WebGL keep the same palette.
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
  load: () => Promise<{ default: unknown }>;
  props: Record<string, unknown>;
  fallback: string;
}

const glow = (a: string, b: string) =>
  `radial-gradient(120% 140% at 85% 0%, ${a}55 0%, transparent 55%), radial-gradient(90% 120% at 10% 100%, ${b}44 0%, transparent 60%), ${brand.ink}`;

export const backdropPresets = {
  threads: {
    load: () => import("../react-bits/Threads"),
    props: { color: [0.66, 0.6, 1], amplitude: 1.6, distance: 0.3, enableMouseInteraction: true },
    fallback: glow(brand.violet, brand.teal),
  },
  blinds: {
    load: () => import("../react-bits/GradientBlinds"),
    props: {
      gradientColors: [brand.violet, brand.teal],
      angle: 20,
      noise: 0.25,
      blindCount: 14,
      blindMinWidth: 50,
      spotlightRadius: 0.55,
      spotlightOpacity: 0.9,
      distortAmount: 0.2,
      mixBlendMode: "lighten",
      lightMode: false,
    },
    fallback: glow(brand.teal, brand.violet),
  },
  grainient: {
    load: () => import("../react-bits/Grainient"),
    props: {
      color1: "#7c5cff",
      color2: "#2b1d6e",
      color3: "#0d0b18",
      timeSpeed: 0.2,
      grainAmount: 0.08,
      lightMode: false,
    },
    fallback: glow(brand.lilac, brand.violet),
  },
  rays: {
    load: () => import("../react-bits/LightRays"),
    props: {
      raysOrigin: "top-center",
      raysColor: "#d6ceff",
      raysSpeed: 1.1,
      lightSpread: 1.2,
      rayLength: 2.2,
      followMouse: true,
      mouseInfluence: 0.12,
      noiseAmount: 0.08,
      distortion: 0.05,
      lightMode: false,
    },
    fallback: `radial-gradient(80% 120% at 50% -10%, #c9c0ff44 0%, transparent 60%), ${brand.ink}`,
  },
  galaxy: {
    load: () => import("../react-bits/Galaxy"),
    props: {
      density: 1.1,
      glowIntensity: 0.35,
      saturation: 0.55,
      hueShift: 200,
      twinkleIntensity: 0.4,
      rotationSpeed: 0.04,
      mouseRepulsion: true,
      repulsionStrength: 1.5,
      transparent: true,
      lightMode: false,
    },
    fallback: glow(brand.violet, "#2a6df4"),
  },
  ripple: {
    load: () => import("../react-bits/RippleGrid"),
    props: {
      gridColor: brand.lilac,
      rippleIntensity: 0.04,
      gridSize: 12,
      gridThickness: 14,
      glowIntensity: 0.12,
      opacity: 0.85,
      mouseInteraction: true,
      lightMode: false,
    },
    fallback: glow(brand.lilac, brand.teal),
  },
  terminal: {
    load: () => import("../react-bits/FaultyTerminal"),
    props: {
      scale: 1.6,
      digitSize: 1.3,
      timeScale: 0.5,
      scanlineIntensity: 0.4,
      glitchAmount: 0.6,
      flickerAmount: 0.6,
      curvature: 0.12,
      tint: brand.mint,
      mouseReact: true,
      mouseStrength: 0.25,
      pageLoadAnimation: true,
      brightness: 0.55,
      lightMode: false,
    },
    fallback: glow(brand.mint, brand.teal),
  },
  radar: {
    load: () => import("../react-bits/Radar"),
    props: {
      color: brand.teal,
      backgroundColor: brand.ink,
      ringCount: 7,
      spokeCount: 10,
      sweepSpeed: 0.6,
      brightness: 0.8,
      enableMouseInteraction: true,
      lightMode: false,
    },
    fallback: glow(brand.teal, brand.mint),
  },
  web: {
    load: () => import("../react-bits/WebThreads"),
    props: {
      color1: brand.violet,
      color2: brand.teal,
      color3: brand.coral,
      speed: 0.6,
      brightness: 0.5,
      opacity: 0.85,
      mouseInteraction: true,
      backgroundColor: brand.ink,
      lightMode: false,
    },
    fallback: glow(brand.coral, brand.violet),
  },
  aurora: {
    load: () => import("../react-bits/SoftAurora"),
    props: {
      color1: brand.teal,
      color2: brand.lilac,
      speed: 0.5,
      brightness: 1,
      enableMouseInteraction: true,
      lightMode: false,
    },
    fallback: glow(brand.teal, brand.lilac),
  },
  veil: {
    load: () => import("../react-bits/DarkVeil"),
    props: {
      hueShift: 18,
      noiseIntensity: 0.02,
      scanlineIntensity: 0.06,
      scanlineFrequency: 2.2,
      speed: 0.45,
      warpAmount: 0.25,
      resolutionScale: 1,
      lightMode: false,
    },
    fallback: glow(brand.violet, brand.lilac),
  },
  topography: {
    load: () => import("../react-bits/Topography"),
    props: {
      lowColor: "#241b5c",
      midColor: brand.violet,
      highColor: brand.teal,
      speed: 0.35,
      bands: 14,
      glow: 0.8,
      opacity: 0.85,
      mouseInteraction: true,
      lightMode: false,
    },
    fallback: glow(brand.violet, brand.teal),
  },
  orb: {
    load: () => import("../react-bits/Orb"),
    props: { hue: 0, hoverIntensity: 0.35, rotateOnHover: true, backgroundColor: brand.ink },
    fallback: `radial-gradient(40% 60% at 50% 50%, ${brand.violet}55 0%, transparent 70%), ${brand.ink}`,
  },
  lightfall: {
    load: () => import("../react-bits/Lightfall"),
    props: {
      colors: [brand.lilac, brand.violet, brand.teal, "#d6ceff"],
      backgroundColor: brand.violet,
      speed: 0.45,
      streakCount: 3,
      streakWidth: 1,
      streakLength: 1.1,
      glow: 0.9,
      density: 0.7,
      twinkle: 0.8,
      zoom: 3,
      backgroundGlow: 0.6,
      opacity: 1,
      dpr: 1,
      mouseInteraction: false,
      lightMode: false,
    },
    fallback: glow(brand.lilac, brand.violet),
  },
} satisfies Record<string, Preset>;

export type BackdropName = keyof typeof backdropPresets;

/** Each curriculum domain has its own atmosphere on lesson and map hero bands. */
export const categoryBackdrop: Record<string, BackdropName> = {
  A: "threads", // 原生基础: the loop's woven threads
  B: "blinds", // 任务与接口: crisp contract slats
  C: "grainient", // 上下文与状态: flowing memory
  R: "rays", // 推理与控制: light rays of attention
  D: "galaxy", // 知识与检索: a field of documents
  E: "ripple", // 框架与编排: an orchestrated grid
  K: "terminal", // 编码 Agent: a terminal
  F: "radar", // 质量与可靠性: monitoring sweep
  G: "web", // 协议与工具: connections
  H: "aurora", // 综合实践: everything together
};
export const backdropFor = (categoryId?: string): BackdropName =>
  (categoryId && categoryBackdrop[categoryId]) || "threads";
