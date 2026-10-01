import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { checkLocales } from "../../../scripts/check-i18n-keys.mjs";
import { pickLocale } from "../locales";

const realDir = path.resolve(__dirname, "../locales");

function fixture(files: Record<string, unknown>) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "i18n-"));
  for (const [name, value] of Object.entries(files)) {
    fs.mkdirSync(path.dirname(path.join(dir, name)), { recursive: true });
    fs.writeFileSync(path.join(dir, name), JSON.stringify(value));
  }
  return dir;
}

describe("locale files", () => {
  it("the shipped locales are aligned", () => {
    expect(checkLocales(realDir).errors).toEqual([]);
  });

  it("reports missing, extra, empty, placeholder and plural problems", () => {
    const dir = fixture({
      "zh-CN/common.json": {
        a: "运行",
        b: "第 {{n}} 课",
        runs_other: "{{count}} 次运行",
        list: { x: "一" },
      },
      "en-US/common.json": {
        b: "Lesson {{num}}",
        runs_other: "{{count}} runs",
        extra: "x",
        list: { x: "" },
      },
      "en-US/more.json": { y: "z" },
    });
    const { errors } = checkLocales(dir);
    expect(errors).toEqual(
      expect.arrayContaining([
        'en-US/common.json: missing "a"',
        'en-US/common.json: extra "extra"',
        'en-US/common.json: "b" placeholders differ from source',
        'en-US/common.json: "runs" lacks plural forms one',
        'en-US/common.json: "list.x" is empty',
        "en-US/more.json: namespace not in source",
      ]),
    );
  });

  it("warns when a translation equals the source text", () => {
    const dir = fixture({
      "zh-CN/common.json": { a: "Agent Lab" },
      "en-US/common.json": { a: "Agent Lab" },
    });
    const result = checkLocales(dir);
    expect(result.errors).toEqual([]);
    expect(result.warnings).toEqual(['en-US/common.json: "a" is identical to source']);
  });
});

describe("pickLocale", () => {
  it("prefers a saved registered locale, then the browser, then the source", () => {
    expect(pickLocale("zh-CN", ["en-US"])).toBe("zh-CN");
    expect(pickLocale("xx", ["zh-TW"])).toBe("zh-CN");
    expect(pickLocale(null, ["fr-FR"])).toBe("zh-CN");
  });
});
