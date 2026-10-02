import { describe, expect, it } from "vitest";
import type { Trace } from "../../types";
import vectors from "../__fixtures__/selector-vectors.json";
import { resolvePath, selectEvents } from "../selector";
import type { Selector } from "../types.gen";

// 与 tests/test_selectors.py 共用同一份向量，保证前后端选择器语义一致。
const none: Selector = {
  event: null,
  round: null,
  path: null,
  span_kind: null,
  name: null,
};

describe("shared selector vectors", () => {
  it.each(vectors.paths)("resolvePath($path)", (vector) => {
    const value = resolvePath(vector.value, vector.path);
    if (vector.found) {
      expect(value).not.toBeUndefined();
      expect(value).toEqual(vector.result);
    } else expect(value).toBeUndefined();
  });

  it.each(vectors.selectors)("selector %#", (vector) => {
    expect(
      selectEvents(
        { ...none, ...(vector.selector as Partial<Selector>) },
        vectors.events as Trace[],
      ),
    ).toEqual(vector.matches);
  });
});
