import { describe, expect, it } from "vitest";
import { parseMotionSetting, resolveMotionLevel } from "../level";

describe("motion level", () => {
  it("follows the OS preference only when the setting is system", () => {
    expect(resolveMotionLevel("system", false)).toBe("full");
    expect(resolveMotionLevel("system", true)).toBe("static");
  });

  it("lets an explicit learner choice win", () => {
    expect(resolveMotionLevel("reduced", false)).toBe("reduced");
    expect(resolveMotionLevel("static", false)).toBe("static");
    expect(resolveMotionLevel("full", true)).toBe("full");
  });

  it("treats unknown stored values as system", () => {
    expect(parseMotionSetting("loud")).toBe("system");
    expect(parseMotionSetting(null)).toBe("system");
    expect(parseMotionSetting("reduced")).toBe("reduced");
  });
});
