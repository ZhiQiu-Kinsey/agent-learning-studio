import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import zh from "../locales/zh-CN/site.json";
import en from "../locales/en/site.json";

const CJK = /[　-〿㐀-鿿＀-￯]/;
const src = new URL("../", import.meta.url).pathname;

function keys(value: unknown, prefix = ""): string[] {
  if (typeof value !== "object" || value === null) return [prefix.replace(/_(one|other)$/, "")];
  return Object.entries(value).flatMap(([key, child]) => keys(child, prefix ? `${prefix}.${key}` : key));
}
function strings(value: unknown): string[] {
  return typeof value === "string" ? [value] : Object.values(value as object).flatMap(strings);
}
function files(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((item) => {
    const full = path.join(dir, item.name);
    if (item.isDirectory()) return ["locales", "generated", "__tests__"].includes(item.name) ? [] : files(full);
    return /\.(ts|tsx)$/.test(item.name) ? [full] : [];
  });
}

describe("site text", () => {
  it("has the same keys in every language", () => {
    expect([...new Set(keys(en))].sort()).toEqual([...new Set(keys(zh))].sort());
  });

  it("has no Chinese in the English texts", () => {
    expect(strings(en).filter((text) => CJK.test(text))).toEqual([]);
  });

  it("has no hard-coded Chinese in components", () => {
    const found = files(src).filter((file) => CJK.test(fs.readFileSync(file, "utf8")));
    expect(found).toEqual([]);
  });
});
