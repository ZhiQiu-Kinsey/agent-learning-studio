import { describe, expect, it } from "vitest";
import type { Trace } from "../../../../types";
import { runLocaleOf, sameLanguage } from "../RunLanguage";

const start = (data: Record<string, unknown>): Trace => ({
  type: "run_start",
  round: null,
  timestamp: "2026-10-11T00:00:00Z",
  data,
});

describe("run language", () => {
  it("compares languages, not regions", () => {
    expect(sameLanguage("en", "en-US")).toBe(true);
    expect(sameLanguage("zh-CN", "zh")).toBe(true);
    expect(sameLanguage("zh-CN", "en")).toBe(false);
  });

  it("reads the run language from run_start; older runs were Chinese", () => {
    expect(runLocaleOf([])).toBeNull();
    expect(runLocaleOf([start({ locale: "en" })])).toBe("en");
    expect(runLocaleOf([start({})])).toBe("zh-CN");
  });
});
