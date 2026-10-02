import { describe, expect, it } from "vitest";
import { paletteFilter } from "../filter";

const lesson = (id: string, alias: string, title: string) =>
  [`lesson ${id}`, [title, id, alias, alias.padStart(2, "0")]] as const;

describe("paletteFilter", () => {
  it("shows everything for an empty query", () => {
    expect(paletteFilter("map", "  ", [])).toBe(1);
  });

  it("ranks an exact alias above lessons that merely contain it", () => {
    const [value2, keys2] = lesson("dependent-calls", "2", "依赖式多轮调用");
    const [value12, keys12] = lesson("hybrid-retrieval", "12", "混合检索");
    expect(paletteFilter(value2, "2", [...keys2])).toBe(1);
    expect(paletteFilter(value12, "2", [...keys12])).toBeLessThan(1);
  });

  it("matches slugs and titles by prefix or substring, case-insensitively", () => {
    const [value, keys] = lesson("agentic-rag", "14", "Agentic RAG 与有界迭代");
    expect(paletteFilter(value, "agentic", [...keys])).toBe(0.9);
    expect(paletteFilter(value, "RAG", [...keys])).toBe(0.8);
    expect(paletteFilter(value, "有界", [...keys])).toBe(0.8);
  });

  it("keeps fuzzy matches below any direct hit", () => {
    const score = paletteFilter("intro 1", "rag", ["认识 Agent"]);
    expect(score).toBeLessThan(0.8);
    expect(paletteFilter("map", "zzz", ["课程地图"])).toBe(0);
  });
});
