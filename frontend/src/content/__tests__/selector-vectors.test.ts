import fs from "node:fs";
import { describe, expect, it } from "vitest";
import type { Trace } from "../../types";
import { evaluatePredict } from "../predict";
import { findEvidence, resolvePath, selectEvents } from "../selector";
import type { CountEvents, Selector } from "../types.gen";

/**
 * Shared vectors keep this implementation and server/selectors.py in lockstep:
 * tests/test_selectors.py reads the same file and must reach the same results.
 */
type Vectors = {
  resolve_path: {
    value: unknown;
    path: string;
    found: boolean;
    result?: unknown;
  }[];
  events: Trace[];
  select: { selector: Partial<Selector>; indices: number[] }[];
  evidence: {
    selector: Partial<Selector>;
    from: number;
    found: boolean;
    index?: number;
    value?: unknown;
    value_is_event?: boolean;
  }[];
  count_events: {
    rule: Omit<CountEvents, "name"> & { name?: string | null };
    count: number;
  }[];
};

const vectors = JSON.parse(
  fs.readFileSync(
    new URL(
      "../../../../tests/fixtures/selector_vectors.json",
      import.meta.url,
    ),
    "utf8",
  ),
) as Vectors;

const none: Selector = {
  event: null,
  round: null,
  path: null,
  span_kind: null,
  name: null,
  nth: null,
};
const full = (selector: Partial<Selector>): Selector => ({
  ...none,
  ...selector,
});

describe("shared selector vectors", () => {
  it("resolves paths like the Python implementation", () => {
    for (const item of vectors.resolve_path) {
      const value = resolvePath(item.value, item.path);
      if (item.found) {
        expect(value, item.path).not.toBeUndefined();
        expect(value, item.path).toEqual(item.result);
      } else {
        expect(value, item.path).toBeUndefined();
      }
    }
  });

  it("selects the same events", () => {
    for (const item of vectors.select) {
      expect(
        selectEvents(full(item.selector), vectors.events),
        JSON.stringify(item.selector),
      ).toEqual(item.indices);
    }
  });

  it("finds the same evidence", () => {
    for (const item of vectors.evidence) {
      const result = findEvidence(
        full(item.selector),
        vectors.events,
        item.from,
      );
      if (!item.found) {
        expect(result).toEqual({ found: false });
        continue;
      }
      expect(result).toEqual({
        found: true,
        index: item.index,
        value: item.value_is_event ? vectors.events[item.index!] : item.value,
      });
    }
  });

  it("counts predict rules over real events only", () => {
    for (const item of vectors.count_events) {
      const outcome = evaluatePredict(
        { ...item.rule, name: item.rule.name ?? null },
        vectors.events,
      );
      expect(outcome, JSON.stringify(item.rule)).toEqual({
        status: "computed",
        actual: item.count,
        matches: null,
      });
    }
  });
});
