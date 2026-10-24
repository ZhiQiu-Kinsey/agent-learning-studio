// Builds the site's curriculum map from curriculum/catalog.json (zh-CN source) and the
// catalog.<lang>.json overlays, with the backend's rules (server/data_overlay.py,
// server/content_overlay.py): an overlay entry whose `source` digest no longer matches the
// Chinese text is stale and falls back to the source text.
import { createHash } from "node:crypto";

/** Same as `digest` in server/content_overlay.py: the first 12 hex digits of sha256. */
export const digest = (text) =>
  createHash("sha256").update(text, "utf8").digest("hex").slice(0, 12);

const LESSON_REF = /\{\{lesson:([^{}]*)\}\}/g;
// Same templates as server/lesson_refs.py.
const REF_TEMPLATES = { "zh-CN": "第 {number} 课", en: "Lesson {number}" };

// The catalog writes level and difficulty in Chinese; the page translates the keys.
const LEVELS = { "必修": "core", "进阶": "advanced", "选修": "elective" };
const DIFFICULTIES = { "入门": "beginner", "进阶": "intermediate", "挑战": "challenge" };

function resolveRefs(text, numbers, locale) {
  return text.replace(LESSON_REF, (whole, slug) => {
    const number = numbers.get(slug);
    if (!number) throw new Error(`lesson reference ${whole} names no lesson in the catalog`);
    return REF_TEMPLATES[locale].replace("{number}", String(number));
  });
}

/**
 * One translatable text: `{ "zh-CN": source, en: translation | null }`. null means missing
 * or stale; the page then shows the source text marked lang="zh-CN".
 */
function localized(path, source, overlays, numbers) {
  const text = { "zh-CN": resolveRefs(source, numbers, "zh-CN") };
  for (const [locale, overlay] of Object.entries(overlays)) {
    const entry = overlay?.texts?.[path];
    text[locale] =
      entry && typeof entry.text === "string" && entry.source === digest(source)
        ? resolveRefs(entry.text, numbers, locale)
        : null;
  }
  return text;
}

/**
 * Curriculum map data in catalog order (category, module, lesson). Lesson numbers follow the
 * order of catalog.lessons, as in server/curriculum.py; nothing is written by hand.
 */
export function buildCurriculum(catalog, overlays = {}) {
  const numbers = new Map(catalog.lessons.map((lesson, index) => [lesson.id, index + 1]));
  const byId = new Map(catalog.lessons.map((lesson) => [lesson.id, lesson]));
  const text = (path, source) => localized(path, source, overlays, numbers);
  const placed = new Set();
  const categories = catalog.categories.map((category) => ({
    id: category.id,
    title: text(`category.${category.id}.title`, category.title),
    description: text(`category.${category.id}.description`, category.description),
    modules: category.modules.map((module) => ({
      id: module.id,
      title: text(`module.${module.id}.title`, module.title),
      description: text(`module.${module.id}.description`, module.description),
      lessons: module.lesson_ids.map((id) => {
        const lesson = byId.get(id);
        if (!lesson) throw new Error(`module ${module.id} lists unknown lesson ${id}`);
        if (lesson.category_id !== category.id || lesson.module_id !== module.id)
          throw new Error(`lesson ${id} names a different category or module than the one listing it`);
        placed.add(id);
        return {
          id,
          number: numbers.get(id),
          title: text(`lesson.${id}.title`, lesson.title),
          summary: text(`lesson.${id}.summary`, lesson.summary),
          status: lesson.status,
          level: LEVELS[lesson.level] ?? null,
          difficulty: DIFFICULTIES[lesson.difficulty] ?? null,
          minutes: Number.isFinite(lesson.estimated_minutes) ? lesson.estimated_minutes : null,
          prerequisites: lesson.prerequisites ?? [],
        };
      }),
    })),
  }));
  const missing = catalog.lessons.filter((lesson) => !placed.has(lesson.id));
  if (missing.length)
    throw new Error(`lessons not listed in any module: ${missing.map((lesson) => lesson.id).join(", ")}`);
  const lessons = catalog.lessons.length;
  return {
    version: catalog.version,
    lessonCount: lessons,
    availableCount: catalog.lessons.filter((lesson) => lesson.status === "available").length,
    categories,
  };
}
