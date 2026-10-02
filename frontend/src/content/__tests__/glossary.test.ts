import { describe, expect, it } from "vitest";
import {
  assignFirstOccurrences,
  buildMatcher,
  keywordKind,
  splitCode,
  splitText,
  termsIn,
  type GlossaryEntry,
} from "../glossary/match";

const entry = (id: string, zh: string, en: string, aliases: string[] = []) =>
  ({ id, zh, en, aliases, definition: `${id} definition` }) as GlossaryEntry;

const matcher = buildMatcher([
  entry("agent", "Agent", "Agent", ["智能体"]),
  entry("agent-loop", "Agent 循环", "Agent Loop"),
  entry("token", "Token", "Token"),
  entry("usage", "用量", "Usage", ["usage"]),
])!;

describe("glossary matching", () => {
  it("prefers the longest form and respects Latin word boundaries", () => {
    expect(termsIn("Agent 循环里的 Agent", matcher)).toEqual([
      "agent-loop",
      "agent",
    ]);
    expect(termsIn("tokens 不算，Token 才算", matcher)).toEqual(["token"]);
  });

  it("ignores code-like tokens and inline code when scanning", () => {
    expect(termsIn("response.usage 和 `Token`", matcher)).toEqual([]);
  });

  it("gives each term to the first text that uses it", () => {
    const owners = assignFirstOccurrences(
      ["先说 Agent", "再说 Agent 和 Token"],
      matcher,
    );
    expect([...(owners.get("先说 Agent") ?? [])]).toEqual(["agent"]);
    expect([...(owners.get("再说 Agent 和 Token") ?? [])]).toEqual(["token"]);
  });

  it("marks only the first occurrence and keeps the text unchanged", () => {
    const text = "Agent 调用 Agent";
    const segments = splitText(text, matcher, new Set(["agent"]));
    expect(
      segments.filter((segment) => typeof segment !== "string"),
    ).toHaveLength(1);
    expect(
      segments
        .map((segment) =>
          typeof segment === "string" ? segment : segment.text,
        )
        .join(""),
    ).toBe(text);
  });
});

describe("code keywords", () => {
  it("finds code-like tokens in plain prose without changing text", () => {
    const text = "模型返回 tool_calls 时用 role=tool 和 add_numbers(19, 23)。";
    const pieces = splitCode(text);
    expect(pieces.filter((piece) => typeof piece !== "string")).toEqual([
      { code: "tool_calls" },
      { code: "role=tool" },
      { code: "add_numbers(19, 23)" },
    ]);
    expect(
      pieces
        .map((piece) => (typeof piece === "string" ? piece : piece.code))
        .join(""),
    ).toBe(text);
  });

  it("classifies by what the token names", () => {
    expect(keywordKind("role=tool")).toEqual({ kind: "role", role: "tool" });
    expect(keywordKind("tool_call_id").kind).toBe("field");
    expect(keywordKind("add_numbers(19, 23)").kind).toBe("call");
    expect(keywordKind("42").kind).toBe("literal");
  });
});
