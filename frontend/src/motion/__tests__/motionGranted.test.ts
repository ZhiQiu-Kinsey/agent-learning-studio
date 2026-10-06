import { describe, expect, it } from "vitest";
import { motionGranted } from "../useMotionBudget";

describe("motion budget grant", () => {
  it("grants every WebGL effect at full motion with WebGL, with no on-screen cap", () => {
    // 使用者 2026-10-06 决定：课程地图每张领域卡都挂自己的着色器，不再排队等名额。
    const grants = Array.from({ length: 12 }, () =>
      motionGranted("webgl", { level: "full", webgl: true }),
    );
    expect(grants.every(Boolean)).toBe(true);
  });

  it("falls back to static without WebGL or at static motion", () => {
    expect(motionGranted("webgl", { level: "full", webgl: false })).toBe(false);
    expect(motionGranted("webgl", { level: "static", webgl: true })).toBe(
      false,
    );
    expect(motionGranted("css", { level: "static", webgl: true })).toBe(false);
    expect(motionGranted("canvas", { level: "full", webgl: false })).toBe(true);
    expect(motionGranted("css", { level: "full", webgl: false })).toBe(true);
  });
});
