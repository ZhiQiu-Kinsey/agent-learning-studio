import fs from "node:fs";
import { describe, expect, it } from "vitest";
import { buildCurriculum, digest } from "../../scripts/lib/curriculum.mjs";
import generated from "../generated/curriculum.json";

const root = new URL("../../../", import.meta.url);
const read = (path: string) => JSON.parse(fs.readFileSync(new URL(path, root), "utf8"));
const catalog = read("curriculum/catalog.json");
const overlay = read("curriculum/catalog.en.json");

type Lesson = { id: string; number: number; title: Record<string, string | null> };
const lessonsOf = (data: { categories: { modules: { lessons: Lesson[] }[] }[] }) =>
  data.categories.flatMap((category) => category.modules.flatMap((module) => module.lessons));

describe("curriculum map", () => {
  it("lists every catalog lesson exactly once, numbered in catalog order", () => {
    const built = buildCurriculum(catalog, { en: overlay });
    const lessons = lessonsOf(built);
    expect(built.lessonCount).toBe(catalog.lessons.length);
    expect(lessons).toHaveLength(catalog.lessons.length);
    expect(new Set(lessons.map((lesson) => lesson.id)).size).toBe(lessons.length);
    for (const lesson of lessons)
      expect(lesson.number).toBe(
        catalog.lessons.findIndex((entry: { id: string }) => entry.id === lesson.id) + 1,
      );
    expect(built.categories.map((category: { id: string }) => category.id)).toEqual(
      catalog.categories.map((category: { id: string }) => category.id),
    );
  });

  it("is what the build generated from the current catalog", () => {
    expect(generated).toEqual(buildCurriculum(catalog, { en: overlay }));
  });

  it("uses the English overlay and falls back when an entry is stale or missing", () => {
    const first = catalog.lessons[0];
    const stale = {
      texts: {
        [`lesson.${first.id}.title`]: { text: "Old title", source: "000000000000" },
        [`lesson.${first.id}.summary`]: { text: "Fresh summary", source: digest(first.summary) },
      },
    };
    const [lesson] = lessonsOf(buildCurriculum(catalog, { en: stale })).filter(
      (item) => item.id === first.id,
    );
    expect(lesson.title).toEqual({ "zh-CN": first.title, en: null });
    expect((lesson as unknown as { summary: unknown }).summary).toEqual({
      "zh-CN": first.summary,
      en: "Fresh summary",
    });
  });

  it("resolves lesson references to numbers in each language", () => {
    const copy = structuredClone(catalog);
    copy.lessons[1].summary = `接着 {{lesson:${copy.lessons[0].id}}}。`;
    const en = {
      texts: {
        [`lesson.${copy.lessons[1].id}.summary`]: {
          text: `After {{lesson:${copy.lessons[0].id}}}.`,
          source: digest(copy.lessons[1].summary),
        },
      },
    };
    const lesson = lessonsOf(buildCurriculum(copy, { en })).find(
      (item) => item.id === copy.lessons[1].id,
    ) as unknown as { summary: Record<string, string> };
    expect(lesson.summary["zh-CN"]).toBe("接着 第 1 课。");
    expect(lesson.summary.en).toBe("After Lesson 1.");
  });

  it("refuses a catalog whose modules do not place every lesson", () => {
    const copy = structuredClone(catalog);
    copy.categories[0].modules[0].lesson_ids.pop();
    expect(() => buildCurriculum(copy)).toThrow(/not listed in any module/);
  });
});
