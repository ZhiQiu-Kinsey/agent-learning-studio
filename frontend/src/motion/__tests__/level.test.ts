import { describe, expect, it } from "vitest";
import { resolveMotionLevel } from "../level";

describe("resolveMotionLevel", () => {
  it("follows the OS reduce-motion preference", () => {
    expect(resolveMotionLevel(false)).toBe("full");
    expect(resolveMotionLevel(true)).toBe("static");
  });
});
