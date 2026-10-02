import { describe, expect, it } from "vitest";
import type { Trace } from "../../../types";
import {
  annotatedLines,
  latestToolResult,
  notesForFile,
  splitLines,
  stackNotes,
  tokenLines,
  toolNames,
  whatsNewItems,
  type Annotation,
  type LessonCode,
} from "../model";

describe("line splitting matches the backend", () => {
  it("treats \\r\\n, \\r and \\n as breaks and ignores a final newline", () => {
    expect(splitLines("a\nb\n")).toEqual(["a", "b"]);
    expect(splitLines("a\r\nb\rc")).toEqual(["a", "b", "c"]);
    expect(splitLines("a\n\n")).toEqual(["a", ""]);
  });

  it("keeps token classes on every line a multi-line token spans", () => {
    const lines = tokenLines([
      { type: "keyword", content: "def" },
      " f():\n    ",
      { type: "string", alias: "doc", content: '"""a\nb"""' },
      "\n",
    ]);
    expect(lines).toHaveLength(3);
    expect(lines[0]).toEqual([
      { text: "def", types: ["keyword"] },
      { text: " f():", types: [] },
    ]);
    expect(lines[1][1]).toEqual({ text: '"""a', types: ["string", "doc"] });
    expect(lines[2]).toEqual([{ text: 'b"""', types: ["string", "doc"] }]);
    expect(lines.map((line) => line.map((s) => s.text).join(""))).toEqual(
      splitLines('def f():\n    """a\nb"""\n'),
    );
  });
});

describe("annotation placement", () => {
  const annotations: Annotation[] = [
    {
      id: "b",
      path: "x.py",
      start: null,
      end: null,
      notes: [{ id: "n9", line: 9, text: "later" }],
    },
    {
      id: "a",
      path: "x.py",
      start: 1,
      end: 5,
      notes: [{ id: "n2", line: 2, text: "first" }],
    },
    {
      id: "c",
      path: "y.py",
      start: null,
      end: null,
      notes: [{ id: "n1", line: 1, text: "other file" }],
    },
  ];

  it("collects one file's notes in line order with stable keys", () => {
    const notes = notesForFile(annotations, "x.py");
    expect(notes.map((note) => [note.key, note.line])).toEqual([
      ["a:n2", 2],
      ["b:n9", 9],
    ]);
    expect([...annotatedLines(notes)]).toEqual([2, 9]);
    expect(notesForFile(annotations, "missing.py")).toEqual([]);
  });

  it("aligns cards with their lines and pushes overlapping cards down", () => {
    // Lines at 0, 20 and 200 px; the first card is 60 px tall.
    expect(stackNotes([0, 20, 200], [60, 40, 30], 8)).toEqual([0, 68, 200]);
    expect(stackNotes([], [])).toEqual([]);
  });
});

describe("tool evidence links", () => {
  const event = (type: string, data: Record<string, unknown>): Trace => ({
    type,
    round: 1,
    timestamp: "2026-10-02T00:00:00Z",
    data,
  });

  it("reads tool names from the TOOLS schema only", () => {
    expect(
      toolNames([
        { type: "function", function: { name: "add_numbers" } },
        { type: "function", function: {} },
        null,
      ]),
    ).toEqual(["add_numbers"]);
    expect(toolNames(undefined)).toEqual([]);
  });

  it("finds the latest real tool_result of that tool and nothing else", () => {
    const events = [
      event("tool_call", { name: "add_numbers" }),
      event("tool_result", { name: "add_numbers", result: { ok: true } }),
      event("tool_result", { name: "get_current_time" }),
      event("tool_result", { name: "add_numbers", result: { ok: false } }),
      event("answer", { content: "42" }),
    ];
    expect(latestToolResult(events, "add_numbers")).toBe(3);
    expect(latestToolResult(events, "get_current_time")).toBe(2);
    expect(latestToolResult(events, "divide_numbers")).toBe(-1);
    expect(latestToolResult([], "add_numbers")).toBe(-1);
  });
});

it("lists added and changed symbols (not unchanged ones) in file and line order", () => {
  const ref = (name: string, path: string, start: number) => ({
    name,
    kind: "function" as const,
    path,
    start,
    end: start + 1,
  });
  const code: LessonCode = {
    lesson_id: "x",
    files: [
      { path: "a.py", language: "python", lines: 50, symbols: [] },
      { path: "b.py", language: "python", lines: 50, symbols: [] },
    ],
    whats_new: {
      compare_with: null,
      added: [ref("late", "b.py", 3), ref("early", "a.py", 9)],
      changed: [ref("top", "a.py", 1)],
      unchanged: [ref("same", "a.py", 20)],
    },
    annotations: [],
  };
  expect(whatsNewItems(code).map((item) => [item.name, item.status])).toEqual([
    ["top", "changed"],
    ["early", "added"],
    ["late", "added"],
  ]);
});
