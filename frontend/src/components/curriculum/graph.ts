/**
 * Pure data for the course map: lesson graph (prerequisite edges), filters and
 * local progress marks. No React, no layout; layout.ts positions the nodes.
 *
 * Prerequisite rules (catalog.json is validated on the server, but the map
 * must stay honest if it ever drifts):
 * - ids resolve through the slug first, then legacy aliases;
 * - duplicates collapse to one edge;
 * - an unknown id or a lesson listing itself is dropped and reported in
 *   `issues`; with `strict: true` it throws CurriculumGraphError instead;
 * - a cycle always throws, because no learning route can satisfy it.
 * With `reduce` (default) edges implied by a longer chain are hidden from the
 * drawing; every node still keeps its full direct prerequisite list.
 */
import { resolveLessonId } from "../../lib/lessonIds";
import type { LessonProgress, ProgressRecord } from "../../progress/model";
import type { CurriculumData, CurriculumLesson } from "../../types";

export interface RoadmapNode {
  id: string;
  number: number;
  title: string;
  status: CurriculumLesson["status"];
  categoryId: string;
  moduleId: string;
  /** Resolved, de-duplicated direct prerequisites (lesson ids). */
  prerequisites: string[];
  /** Longest prerequisite chain before this lesson; roots are 0. */
  depth: number;
}

export interface RoadmapEdge {
  id: string;
  source: string;
  target: string;
}

export type GraphIssue =
  | { kind: "unknown_prerequisite"; lesson: string; prerequisite: string }
  | { kind: "self_prerequisite"; lesson: string };

export interface CurriculumGraph {
  nodes: RoadmapNode[];
  edges: RoadmapEdge[];
  issues: GraphIssue[];
}

export class CurriculumGraphError extends Error {
  constructor(
    message: string,
    readonly issues: GraphIssue[] = [],
    readonly cycle: string[] = [],
  ) {
    super(message);
    this.name = "CurriculumGraphError";
  }
}

type GraphLesson = Pick<
  CurriculumLesson,
  | "id"
  | "number"
  | "title"
  | "status"
  | "category_id"
  | "module_id"
  | "prerequisites"
> & { aliases?: readonly string[] };

export function buildCurriculumGraph(
  lessons: readonly GraphLesson[],
  { strict = false, reduce = true }: { strict?: boolean; reduce?: boolean } = {},
): CurriculumGraph {
  const issues: GraphIssue[] = [];
  const direct = new Map<string, string[]>();
  for (const lesson of lessons) {
    const resolved: string[] = [];
    for (const raw of lesson.prerequisites) {
      const id = resolveLessonId(raw, lessons);
      if (!id)
        issues.push({
          kind: "unknown_prerequisite",
          lesson: lesson.id,
          prerequisite: raw,
        });
      else if (id === lesson.id)
        issues.push({ kind: "self_prerequisite", lesson: lesson.id });
      else if (!resolved.includes(id)) resolved.push(id);
    }
    direct.set(lesson.id, resolved);
  }
  if (strict && issues.length)
    throw new CurriculumGraphError(
      `invalid prerequisites: ${issues
        .map((issue) =>
          issue.kind === "unknown_prerequisite"
            ? `${issue.lesson} -> ${issue.prerequisite}`
            : `${issue.lesson} -> itself`,
        )
        .join(", ")}`,
      issues,
    );

  // Ancestors (all transitive prerequisites) with cycle detection.
  const ancestors = new Map<string, Set<string>>();
  const depth = new Map<string, number>();
  const visiting: string[] = [];
  const visit = (id: string): Set<string> => {
    const known = ancestors.get(id);
    if (known) return known;
    const loop = visiting.indexOf(id);
    if (loop >= 0) {
      const cycle = [...visiting.slice(loop), id];
      throw new CurriculumGraphError(
        `prerequisite cycle: ${cycle.join(" -> ")}`,
        issues,
        cycle,
      );
    }
    visiting.push(id);
    const result = new Set<string>();
    let level = 0;
    for (const parent of direct.get(id) ?? []) {
      result.add(parent);
      visit(parent).forEach((item) => result.add(item));
      level = Math.max(level, depth.get(parent)! + 1);
    }
    visiting.pop();
    ancestors.set(id, result);
    depth.set(id, level);
    return result;
  };
  lessons.forEach((lesson) => visit(lesson.id));

  const nodes = lessons.map<RoadmapNode>((lesson) => ({
    id: lesson.id,
    number: lesson.number,
    title: lesson.title,
    status: lesson.status,
    categoryId: lesson.category_id,
    moduleId: lesson.module_id,
    prerequisites: direct.get(lesson.id)!,
    depth: depth.get(lesson.id)!,
  }));
  const edges: RoadmapEdge[] = [];
  for (const node of nodes) {
    for (const source of node.prerequisites) {
      // Hidden when another direct prerequisite already depends on `source`.
      const implied =
        reduce &&
        node.prerequisites.some(
          (other) => other !== source && ancestors.get(other)!.has(source),
        );
      if (!implied)
        edges.push({ id: `${source}->${node.id}`, source, target: node.id });
    }
  }
  return { nodes, edges, issues };
}

export interface LessonFilter {
  query: string;
  onlyAvailable: boolean;
  categoryId: string | null;
}

/** Same matching the list always had: title, summary, level, domain, module, topics, goals, experiments. */
export function lessonMatches(
  lesson: CurriculumLesson,
  curriculum: Pick<CurriculumData, "categories">,
  { query, onlyAvailable, categoryId }: LessonFilter,
  /** Labels the UI shows for fixed values (level, difficulty) in its own language. */
  labels: (lesson: CurriculumLesson) => readonly (string | undefined)[] = () => [],
): boolean {
  if (categoryId && lesson.category_id !== categoryId) return false;
  if (onlyAvailable && lesson.status !== "available") return false;
  const needle = query.trim().toLocaleLowerCase();
  if (!needle) return true;
  const category = curriculum.categories.find(
    (item) => item.id === lesson.category_id,
  );
  const module = category?.modules.find((item) => item.id === lesson.module_id);
  return [
    lesson.title,
    lesson.summary,
    lesson.level,
    ...labels(lesson),
    category?.title,
    module?.title,
    ...lesson.topics,
    ...lesson.objectives,
    ...lesson.experiments.map((experiment) => experiment.title),
  ]
    .join(" ")
    .toLocaleLowerCase()
    .includes(needle);
}

/** What this browser really recorded for a lesson; never a judgement of mastery. */
export interface LessonMarks {
  opened: boolean;
  ran: boolean;
  quizzed: boolean;
}

/** Records may still sit under a legacy alias until the rename migration runs. */
function recordsOf(
  record: ProgressRecord,
  lesson: { id: string; aliases?: readonly string[] },
): LessonProgress[] {
  return [lesson.id, ...(lesson.aliases ?? [])]
    .map((key) => record.lessons[key])
    .filter((entry): entry is LessonProgress => !!entry);
}

export function lessonMarks(
  record: ProgressRecord,
  lesson: { id: string; aliases?: readonly string[] },
): LessonMarks {
  const entries = recordsOf(record, lesson);
  return {
    // Every progress entry starts from a real visit to the lesson.
    opened: entries.length > 0,
    ran: entries.some((entry) => entry.runs.count > 0),
    quizzed: entries.some((entry) => Object.keys(entry.quizzes).length > 0),
  };
}

export interface MarkCounts {
  opened: number;
  ran: number;
  quizzed: number;
}

export function countMarks(
  record: ProgressRecord,
  lessons: readonly { id: string; aliases?: readonly string[] }[],
): MarkCounts {
  return lessons.reduce<MarkCounts>(
    (sum, lesson) => {
      const marks = lessonMarks(record, lesson);
      return {
        opened: sum.opened + Number(marks.opened),
        ran: sum.ran + Number(marks.ran),
        quizzed: sum.quizzed + Number(marks.quizzed),
      };
    },
    { opened: 0, ran: 0, quizzed: 0 },
  );
}

export type Direction = "left" | "right" | "up" | "down";

/**
 * Spatial keyboard navigation over laid-out node centres: the nearest node in
 * the pressed direction, preferring nodes close to the current row/column.
 */
export function neighborInDirection(
  points: readonly { id: string; x: number; y: number }[],
  fromId: string,
  direction: Direction,
): string | undefined {
  const from = points.find((point) => point.id === fromId);
  if (!from) return undefined;
  let best: { id: string; score: number } | undefined;
  for (const point of points) {
    if (point.id === fromId) continue;
    const dx = point.x - from.x;
    const dy = point.y - from.y;
    const [along, across] =
      direction === "left"
        ? [-dx, dy]
        : direction === "right"
          ? [dx, dy]
          : direction === "up"
            ? [-dy, dx]
            : [dy, dx];
    if (along <= 1) continue;
    const score = along + Math.abs(across) * 2;
    if (!best || score < best.score) best = { id: point.id, score };
  }
  return best?.id;
}

/** Narrow-screen route: stages by prerequisite depth, catalog order inside each. */
export function stagesOf(graph: CurriculumGraph): RoadmapNode[][] {
  const stages: RoadmapNode[][] = [];
  for (const node of [...graph.nodes].sort((a, b) => a.number - b.number))
    (stages[node.depth] ??= []).push(node);
  return stages.filter(Boolean);
}
