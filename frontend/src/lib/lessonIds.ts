/**
 * 课程 ID 约定：slug（如 "tool-selection"）是主 ID；改名前的旧 slug 作为别名由服务端返回（不使用数字别名）。
 * 任何来自旧链接、旧下载记录或本机存储的课程 ID 都应先经过 resolveLessonId 迁移为 slug。
 */
export type LessonIdentity = { id: string; aliases?: readonly string[] };

export function resolveLessonId(
  raw: string | null | undefined,
  lessons: readonly LessonIdentity[],
): string | undefined {
  if (!raw) return undefined;
  return (
    lessons.find((lesson) => lesson.id === raw)?.id ??
    lessons.find((lesson) => lesson.aliases?.includes(raw))?.id
  );
}

/** 显示课号来自接口的 number 字段，不再从 ID 推算。 */
export function formatLessonNumber(number: number | undefined) {
  return number ? String(number).padStart(2, "0") : "—";
}
