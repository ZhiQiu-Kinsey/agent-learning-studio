import { describe, expect, it } from "vitest";
import { createRunCache, runKey, runCacheStorageKey } from "../runCache";

function memoryStorage(initial: Record<string, string> = {}) {
  const data = new Map(Object.entries(initial));
  return {
    data,
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => void data.set(key, value),
  };
}

const detail = {
  id: "dependent-calls",
  runtime_locale: "zh-CN",
  system_prompt: "先查时间，再相加。",
  tools: [{ type: "function", function: { name: "add_numbers" } }],
  sources: [
    {
      path: "lessons/x/main.py",
      language: "python",
      role: "lesson" as const,
      content: "A",
    },
    {
      path: "course/agent.py",
      language: "python",
      role: "platform" as const,
      content: "B",
    },
    {
      path: "lessons/x/fixtures.py",
      language: "python",
      role: "fixture" as const,
      content: "C",
    },
  ],
};
const key = (
  patch: Partial<typeof detail> = {},
  question = "把现在的小时和分钟相加。",
  inputs = {},
) => runKey({ ...detail, ...patch }, "chain", question, inputs);

describe("run cache key", () => {
  it("stays the same while nothing that shapes the run changes", () => {
    expect(key()).toBe(key());
    expect(key({}, "q", { a: 1, b: { c: 2, d: 3 } })).toBe(
      key({}, "q", { b: { d: 3, c: 2 }, a: 1 }),
    );
    // Test fixtures never run in the page.
    expect(
      key({
        sources: detail.sources.map((source) =>
          source.role === "fixture"
            ? { ...source, content: "changed" }
            : source,
        ),
      }),
    ).toBe(key());
  });

  it("changes with the question, inputs, system prompt, tools or code", () => {
    const base = key();
    expect(key({}, "把现在的小时和分钟相乘。")).not.toBe(base);
    expect(key({}, undefined, { limit: 3 })).not.toBe(base);
    expect(key({ system_prompt: "别的提示词" })).not.toBe(base);
    expect(key({ tools: [] })).not.toBe(base);
    // The same question in another run language is another run.
    expect(key({ runtime_locale: "en" })).not.toBe(base);
    expect(
      key({
        sources: detail.sources.map((source) =>
          source.role === "platform" ? { ...source, content: "B2" } : source,
        ),
      }),
    ).not.toBe(base);
    expect(runKey(detail, "both", "q", {})).not.toBe(
      runKey(detail, "chain", "q", {}),
    );
  });
});

describe("run cache store", () => {
  it("remembers the latest run per key and forgets on request", () => {
    const storage = memoryStorage();
    const cache = createRunCache(storage);
    cache.remember("k", "run-1");
    cache.remember("k", "run-2");
    expect(cache.get("k")).toBe("run-2");
    expect(createRunCache(storage).get("k")).toBe("run-2");
    cache.forget("k");
    expect(createRunCache(storage).get("k")).toBeNull();
  });

  it("keeps only run ids and hashes, never the question text", () => {
    const storage = memoryStorage();
    createRunCache(storage).remember(key(), "run-1");
    expect(storage.data.get(runCacheStorageKey)).not.toContain("小时");
  });

  it("does not overwrite data it cannot read", () => {
    const newer = JSON.stringify({ version: 2, entries: [] });
    const storage = memoryStorage({ [runCacheStorageKey]: newer });
    const cache = createRunCache(storage);
    cache.remember("k", "run-1");
    expect(cache.get("k")).toBe("run-1");
    expect(storage.data.get(runCacheStorageKey)).toBe(newer);
  });
});
