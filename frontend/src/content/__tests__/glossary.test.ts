import { describe, expect, it } from "vitest";
import {
  assignFirstOccurrences,
  buildMatcher,
  buildNamePattern,
  isCodeShaped,
  keywordKind,
  splitCode,
  splitNames,
  splitProse,
  splitText,
  termsIn,
  type GlossaryEntry,
} from "../glossary/match";
import { termTier } from "../glossary/vocabulary";

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

describe("English prose", () => {
  const english = (
    id: string,
    zh: string,
    en: string,
    term: string,
    local: string[] = [],
  ) => ({ ...entry(id, zh, en), term, local_aliases: local });
  const en = buildMatcher(
    [
      english("tool-calling", "工具调用", "Tool Calling", "tool calling", ["function calling"]),
      english("tool", "工具", "Tool", "tool"),
      english("token", "Token", "Token", "token"),
      english("finish-reason", "结束原因", "Finish Reason", "finish reason"),
      english("cache", "缓存", "Cache", "cache"),
    ],
    "en",
  )!;

  it("matches English names and aliases case-insensitively as whole words, longest first", () => {
    expect(termsIn("Tool calling lets the model ask for a tool.", en)).toEqual([
      "tool-calling",
      "tool",
    ]);
    expect(termsIn("This is function calling.", en)).toEqual(["tool-calling"]);
    expect(termsIn("tool-calling and Finish Reason", en)).toEqual([
      "tool-calling",
      "finish-reason",
    ]);
    // Whole words only: no match inside a longer word or identifier.
    expect(termsIn("toolbox, tokenizer, finish_reason", en)).toEqual([]);
  });

  it("ignores Latin-only Chinese aliases in English prose but keeps Chinese forms", () => {
    const schema = {
      ...english("json-schema", "JSON Schema", "JSON Schema", "JSON Schema"),
      aliases: ["Schema", "结构定义"],
    };
    const matcher = buildMatcher([schema], "en")!;
    expect(termsIn("The tool schema lists its parameters.", matcher)).toEqual([]);
    expect(termsIn("A JSON Schema describes it.", matcher)).toEqual(["json-schema"]);
    expect(termsIn("回落段落里的结构定义", matcher)).toEqual(["json-schema"]);
  });

  it("accepts a plural ending and keeps the matched text unchanged", () => {
    expect(termsIn("Count the tokens and the caches.", en)).toEqual([
      "token",
      "cache",
    ]);
    const text = "Tokens cost money.";
    const segments = splitText(text, en, new Set(["token"]));
    expect(segments[0]).toEqual({ entry: expect.objectContaining({ id: "token" }), text: "Tokens" });
    expect(
      segments
        .map((segment) => (typeof segment === "string" ? segment : segment.text))
        .join(""),
    ).toBe(text);
  });

  it("does not take English abbreviations or plain words for code", () => {
    const codes = (text: string) =>
      splitCode(text)
        .filter((piece) => typeof piece !== "string")
        .map((piece) => (piece as { code: string }).code);
    expect(codes("Fields, e.g. usage.total_tokens, i.e. the sum.")).toEqual([
      "usage.total_tokens",
    ]);
    expect(
      ["messages", "is", "model", "Bearer", "tool_calls", "RunContext", "Final Answer", "lesson.report", "s-1042"].filter(
        isCodeShaped,
      ),
    ).toEqual(["tool_calls", "RunContext", "Final Answer", "lesson.report", "s-1042"]);
  });

  it("still finds Chinese forms in a paragraph that fell back to Chinese", () => {
    expect(termsIn("模型发起工具调用", en)).toEqual(["tool-calling"]);
  });

  it("leaves Chinese matching unchanged without an English language", () => {
    const zh = buildMatcher([english("token", "Token", "Token", "token")])!;
    expect(termsIn("tokens 不算，Token 才算", zh)).toEqual(["token"]);
    expect(zh.english).toBe(false);
  });
});

describe("Chinese phrases with another meaning", () => {
  const zh = buildMatcher([
    { ...entry("validator", "验证器", "Validator", ["验收器"]) },
    { ...entry("acceptance", "验收标准", "Acceptance Criteria") },
    { ...entry("evaluation", "评估", "Evaluation"), not_in: ["评估者"] },
  ])!;

  it("skips a not_in phrase as a whole and still finds the term elsewhere", () => {
    expect(termsIn("评估者给出评估", zh)).toEqual(["evaluation"]);
    expect(termsIn("评估者通过", zh)).toEqual([]);
    expect(termsIn("验收器对照验收标准", zh)).toEqual([
      "validator",
      "acceptance",
    ]);
  });
});

describe("lesson code names", () => {
  const names = buildNamePattern([
    "evidence",
    "stop",
    "Final Answer",
    "s-1042",
  ]);

  it("matches whole names only, never inside identifiers or dotted paths", () => {
    const pieces = (text: string) =>
      splitNames(text, names)
        .filter((piece) => typeof piece !== "string")
        .map((piece) => (piece as { code: string }).code);
    expect(pieces("evidence 指向结果，stop 规定何时停")).toEqual([
      "evidence",
      "stop",
    ]);
    expect(pieces("写出 Final Answer 后，学号 s-1042")).toEqual([
      "Final Answer",
      "s-1042",
    ]);
    expect(pieces("stopped、evidence_ref、lesson.stop、stop.x")).toEqual([]);
  });

  it("keeps precedence: code tokens, then owned terms, then code names", () => {
    const pieces = splitProse(
      "Token 数写在 usage.total 里，evidence 另记；Token 再出现",
      matcher,
      new Set(["token"]),
      buildNamePattern(["evidence", "Token"]),
    );
    const kinds = pieces.map((piece) =>
      typeof piece === "string"
        ? "text"
        : "code" in piece
          ? `code:${piece.code}`
          : `term:${piece.text}`,
    );
    expect(kinds.filter((kind) => kind !== "text")).toEqual([
      "term:Token",
      "code:usage.total",
      "code:evidence",
      "code:Token",
    ]);
    expect(
      pieces
        .map((piece) =>
          typeof piece === "string"
            ? piece
            : "code" in piece
              ? piece.code
              : piece.text,
        )
        .join(""),
    ).toBe("Token 数写在 usage.total 里，evidence 另记；Token 再出现");
  });
});

describe("term tiers", () => {
  const concept = {
    ...entry("task-card", "任务卡", "Task Card"),
    first_lesson: "task-contract",
  };
  const background = {
    ...entry("tokenizer", "分词器", "Tokenizer"),
    kind: "background" as const,
  };

  it("separates new, review and background terms", () => {
    expect(termTier(concept, "task-contract")).toBe("new");
    expect(termTier(concept, "context-budget")).toBe("review");
    expect(termTier(background, "context-budget")).toBe("background");
    expect(termTier(concept, undefined)).toBeUndefined();
  });
});
