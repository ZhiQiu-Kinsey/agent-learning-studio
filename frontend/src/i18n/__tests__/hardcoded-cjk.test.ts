import fs from "node:fs";
import { describe, expect, it } from "vitest";
import { baselinePath, countCjk, scanSource } from "../../../scripts/cjk-scan.mjs";

describe("hardcoded Chinese copy only goes down", () => {
  it("counts literals and JSX text but not comments or imports", () => {
    const sample = [
      'import x from "./中文模块";',
      "// 注释不算",
      'const a = "运行";',
      "const b = `第 ${n} 课`;",
      "const c = <p title=\"提示\">你好 {name}</p>;",
    ].join("\n");
    expect(countCjk(sample, "sample.tsx")).toBe(4);
  });

  it("matches the committed baseline (run `npm run i18n:baseline` after removing copy)", () => {
    const baseline = JSON.parse(fs.readFileSync(baselinePath, "utf8")) as Record<string, number>;
    const current = scanSource();
    const grew = Object.entries(current)
      .filter(([file, count]) => count > (baseline[file] ?? 0))
      .map(([file, count]) => `${file}: ${baseline[file] ?? 0} -> ${count}`);
    expect(grew, "new hardcoded Chinese; move it to src/i18n/locales").toEqual([]);
    const shrank = Object.entries(baseline)
      .filter(([file, count]) => (current[file] ?? 0) < count)
      .map(([file, count]) => `${file}: ${count} -> ${current[file] ?? 0}`);
    expect(shrank, "copy was extracted; tighten the baseline").toEqual([]);
  });
});
