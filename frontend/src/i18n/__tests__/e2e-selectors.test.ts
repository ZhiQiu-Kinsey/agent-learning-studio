import fs from "node:fs";
import { describe, expect, it } from "vitest";
import {
  baselinePath,
  countSelectors,
  scanSpecs,
  type SelectorCounts,
} from "../../../scripts/check-e2e-selectors.mjs";

describe("brittle e2e selectors only go down", () => {
  it("counts Chinese selectors, Chinese expectations and class selectors only", () => {
    const sample = [
      "// 注释不算",
      'const fixture = { title: "测试课" };',
      'page.getByRole("button", { name: "运行练习" });',
      'page.getByRole("button", { name: /依赖式/ });',
      'page.getByTestId("lab-run-button");',
      'page.getByRole("button", { name: t("quiz:submit") });',
      'nav.locator(".nav-lesson").filter({ hasText: "计划中" });',
      "page.locator('[data-status=\"planned\"]');",
      "page.locator('b [aria-hidden=\"true\"]');",
      'heading.locator("..");',
      'lessons.filter((lesson) => lesson.title === "中文");',
      'expect(status).toHaveText("已完成");',
      "expect(meta).toContainText(`${n} 节已自检`);",
      "expect(board).toContainText(fixture.title);",
    ].join("\n");
    expect(countSelectors(sample)).toEqual({
      cjkSelectors: 3,
      cjkAssertions: 2,
      classSelectors: 1,
    });
  });

  it("matches the committed baseline (run `npm run e2e:selectors` after migrating selectors)", () => {
    const baseline = JSON.parse(
      fs.readFileSync(baselinePath, "utf8"),
    ) as Record<string, SelectorCounts>;
    const current = scanSpecs();
    const empty: SelectorCounts = {
      cjkSelectors: 0,
      cjkAssertions: 0,
      classSelectors: 0,
    };
    const grew: string[] = [];
    const shrank: string[] = [];
    for (const file of new Set([
      ...Object.keys(baseline),
      ...Object.keys(current),
    ])) {
      const before = baseline[file] ?? empty;
      const after = current[file] ?? empty;
      for (const key of Object.keys(empty) as (keyof SelectorCounts)[]) {
        if (after[key] > before[key])
          grew.push(`${file} ${key}: ${before[key]} -> ${after[key]}`);
        if (after[key] < before[key])
          shrank.push(`${file} ${key}: ${before[key]} -> ${after[key]}`);
      }
    }
    expect(
      grew,
      "locate by role + locale key or data-testid; assert copy from API data or src/i18n/locales",
    ).toEqual([]);
    expect(shrank, "selectors were migrated; tighten the baseline").toEqual([]);
  });
});
