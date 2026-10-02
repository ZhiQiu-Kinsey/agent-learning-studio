import { describe, expect, it } from "vitest";
import { emptyProgress, reduceProgress } from "../../../progress/model";
import type { CurriculumLesson } from "../../../types";
import {
  buildCurriculumGraph,
  countMarks,
  CurriculumGraphError,
  lessonMarks,
  lessonMatches,
  neighborInDirection,
  stagesOf,
} from "../graph";
import { layoutRoadmap, NODE_WIDTH } from "../layout";

function lesson(
  id: string,
  number: number,
  prerequisites: string[] = [],
  extra: Partial<CurriculumLesson> = {},
): CurriculumLesson {
  return {
    id,
    number,
    aliases: [String(number)],
    title: `Lesson ${id}`,
    category_id: "A",
    module_id: "A1",
    level: "intro",
    status: "available",
    prerequisites,
    summary: "",
    objectives: [],
    topics: [],
    experiments: [],
    acceptance: [],
    references: [],
    ...extra,
  };
}

// a -> b -> c, and c also lists a directly (implied by b).
const chain = [
  lesson("a", 1),
  lesson("b", 2, ["a"]),
  lesson("c", 3, ["b", "a"], { status: "planned", category_id: "B" }),
];

describe("buildCurriculumGraph", () => {
  it("builds one node per lesson with depth and full prerequisite lists", () => {
    const graph = buildCurriculumGraph(chain);
    expect(graph.nodes.map((node) => [node.id, node.depth])).toEqual([
      ["a", 0],
      ["b", 1],
      ["c", 2],
    ]);
    expect(graph.nodes[2]).toMatchObject({
      prerequisites: ["b", "a"],
      status: "planned",
      categoryId: "B",
    });
    expect(graph.issues).toEqual([]);
  });

  it("hides edges implied by a longer chain unless reduce is off", () => {
    expect(buildCurriculumGraph(chain).edges.map((edge) => edge.id)).toEqual([
      "a->b",
      "b->c",
    ]);
    expect(
      buildCurriculumGraph(chain, { reduce: false }).edges.map(
        (edge) => edge.id,
      ),
    ).toEqual(["a->b", "b->c", "a->c"]);
  });

  it("resolves legacy aliases and collapses duplicates", () => {
    const graph = buildCurriculumGraph([
      lesson("a", 1),
      lesson("b", 2, ["1", "a", "a"]),
    ]);
    expect(graph.nodes[1].prerequisites).toEqual(["a"]);
    expect(graph.edges).toEqual([{ id: "a->b", source: "a", target: "b" }]);
  });

  it("drops and reports unknown or self prerequisites by default", () => {
    const graph = buildCurriculumGraph([
      lesson("a", 1, ["a"]),
      lesson("b", 2, ["a", "missing"]),
    ]);
    expect(graph.edges.map((edge) => edge.id)).toEqual(["a->b"]);
    expect(graph.nodes[0].prerequisites).toEqual([]);
    expect(graph.issues).toEqual([
      { kind: "self_prerequisite", lesson: "a" },
      { kind: "unknown_prerequisite", lesson: "b", prerequisite: "missing" },
    ]);
  });

  it("throws on unknown prerequisites in strict mode", () => {
    expect(() =>
      buildCurriculumGraph([lesson("a", 1, ["missing"])], { strict: true }),
    ).toThrow(CurriculumGraphError);
  });

  it("always throws on a cycle and names it", () => {
    try {
      buildCurriculumGraph([lesson("a", 1, ["b"]), lesson("b", 2, ["a"])]);
      expect.unreachable();
    } catch (error) {
      expect(error).toBeInstanceOf(CurriculumGraphError);
      expect((error as CurriculumGraphError).cycle).toEqual(["a", "b", "a"]);
    }
  });

  it("groups narrow-screen stages by depth in catalog order", () => {
    const stages = stagesOf(
      buildCurriculumGraph([...chain, lesson("d", 4)]),
    );
    expect(stages.map((stage) => stage.map((node) => node.id))).toEqual([
      ["a", "d"],
      ["b"],
      ["c"],
    ]);
  });
});

describe("layoutRoadmap", () => {
  it("places every lesson and keeps prerequisites to the left", async () => {
    const graph = buildCurriculumGraph(chain);
    const positions = await layoutRoadmap(graph);
    expect([...positions.keys()].sort()).toEqual(["a", "b", "c"]);
    for (const edge of graph.edges)
      expect(positions.get(edge.source)!.x + NODE_WIDTH).toBeLessThanOrEqual(
        positions.get(edge.target)!.x,
      );
  });
});

describe("lessonMatches", () => {
  const curriculum = {
    categories: [
      {
        id: "A",
        title: "Native",
        description: "",
        modules: [
          { id: "A1", title: "Loop", description: "", lesson_ids: ["a"] },
        ],
      },
    ],
  };
  const target = lesson("a", 1, [], { topics: ["tool call"] });
  const none = { query: "", onlyAvailable: false, categoryId: null };

  it("searches lesson, domain and module text", () => {
    expect(lessonMatches(target, curriculum, { ...none, query: "TOOL" })).toBe(
      true,
    );
    expect(lessonMatches(target, curriculum, { ...none, query: "loop" })).toBe(
      true,
    );
    expect(lessonMatches(target, curriculum, { ...none, query: "xyz" })).toBe(
      false,
    );
  });

  it("applies the domain and availability filters", () => {
    expect(lessonMatches(target, curriculum, { ...none, categoryId: "B" })).toBe(
      false,
    );
    expect(
      lessonMatches(
        { ...target, status: "planned" },
        curriculum,
        { ...none, onlyAvailable: true },
      ),
    ).toBe(false);
  });
});

describe("local progress marks", () => {
  const at = "2026-10-02T00:00:00.000Z";
  let record = emptyProgress();
  record = reduceProgress(record, { type: "lesson_opened", lessonId: "a", at });
  record = reduceProgress(record, {
    type: "run_completed",
    lessonId: "a",
    runId: "r1",
    at,
  });
  record = reduceProgress(record, { type: "lesson_opened", lessonId: "2", at });
  record = reduceProgress(record, {
    type: "quiz_scored",
    lessonId: "2",
    correct: 1,
    total: 2,
    at,
  });

  it("only reflects recorded actions, including legacy alias keys", () => {
    expect(lessonMarks(record, chain[0])).toEqual({
      opened: true,
      ran: true,
      quizzed: false,
    });
    expect(lessonMarks(record, chain[1])).toEqual({
      opened: true,
      ran: false,
      quizzed: true,
    });
    expect(lessonMarks(record, chain[2])).toEqual({
      opened: false,
      ran: false,
      quizzed: false,
    });
    expect(countMarks(record, chain)).toEqual({
      opened: 2,
      ran: 1,
      quizzed: 1,
    });
  });
});

describe("neighborInDirection", () => {
  const points = [
    { id: "a", x: 0, y: 0 },
    { id: "b", x: 300, y: 0 },
    { id: "c", x: 300, y: 100 },
    { id: "d", x: 0, y: 100 },
  ];

  it("moves to the nearest node in the pressed direction", () => {
    expect(neighborInDirection(points, "a", "right")).toBe("b");
    expect(neighborInDirection(points, "c", "left")).toBe("d");
    expect(neighborInDirection(points, "b", "down")).toBe("c");
    expect(neighborInDirection(points, "d", "up")).toBe("a");
  });

  it("stays put at the edge or for unknown nodes", () => {
    expect(neighborInDirection(points, "a", "left")).toBeUndefined();
    expect(neighborInDirection(points, "zzz", "right")).toBeUndefined();
  });
});
