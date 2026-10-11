import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { Trace } from "../../../../types";
import { Code } from "../../../Code";
import both from "../../../../stage/__fixtures__/lesson-1-both.json";
import { printJson, shownPath, shownValue } from "../jsonLines";

const run = both as Trace[];

const body = {
  model: "m",
  messages: [
    { role: "system", content: "s" },
    { role: "user", content: "q" },
  ],
  empty: [],
  usage: { prompt_tokens: 51 },
};

const text = (html: string) =>
  html
    .replace(/<[^>]+>/g, "")
    .replace(/&quot;/g, '"')
    .replace(/&#x27;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&");

describe("printJson", () => {
  it("prints exactly what JSON.stringify prints for every event of a real run", () => {
    for (const event of run)
      expect(printJson(shownValue(event)).text).toBe(
        JSON.stringify(shownValue(event), null, 2),
      );
    expect(printJson(undefined).text).toBe("null");
  });

  it("records the lines each field occupies, with selector path syntax", () => {
    const { text: printed, ranges } = printJson(body);
    const lines = printed.split("\n");
    const messages = ranges.get("messages")!;
    expect(lines[messages.from]).toBe('  "messages": [');
    expect(lines[messages.to]).toBe("  ],");
    const content = ranges.get("messages[1].content")!;
    expect(content.from).toBe(content.to);
    expect(lines[content.from]).toBe('      "content": "q"');
    expect(lines[ranges.get("empty")!.from]).toBe('  "empty": [],');
    expect(lines[ranges.get("usage.prompt_tokens")!.from]).toBe(
      '    "prompt_tokens": 51',
    );
    expect(ranges.get("")).toEqual({ from: 0, to: lines.length - 1 });
  });
});

describe("shownPath", () => {
  const request = run.find((event) => event.type === "request")!;
  const toolResult = run.find((event) => event.type === "tool_result")!;

  it("maps selector paths into the JSON the inspector shows", () => {
    expect(shownPath(request, "data.body.messages")).toBe("messages");
    expect(shownPath(request, "data.body")).toBe("");
    expect(shownPath(toolResult, "data.result.result")).toBe("result.result");
  });

  it("returns null for fields outside the shown JSON", () => {
    expect(shownPath(request, "data.representation")).toBeNull();
    expect(shownPath(request, "seq")).toBeNull();
  });

  it("frames a report metric named by id, wherever it sits", () => {
    const report = {
      type: "lesson.report",
      data: {
        metrics: [
          { label: "Verdict", value: "passed" },
          { id: "last_claim", label: "Last claim", value: "done" },
        ],
      },
    } as unknown as Trace;
    const path = shownPath(report, "data.metrics[id=last_claim]");
    expect(path).toBe("metrics[1]");
    const { text, ranges } = printJson(report.data);
    const range = ranges.get(path!)!;
    expect(text.split("\n").slice(range.from, range.to + 1).join("\n")).toContain(
      '"id": "last_claim"',
    );
    expect(shownPath(report, "data.metrics[id=missing].value")).toBeNull();
  });
});

describe("Code mark", () => {
  const content = printJson(body).text;
  const messages = printJson(body).ranges.get("messages")!;

  it("frames the marked lines without changing the text", () => {
    const html = renderToStaticMarkup(
      createElement(Code, { content, mark: messages }),
    );
    expect(text(html)).toBe(content);
    const marked = html.match(/<mark[^>]*>([\s\S]*)<\/mark>/)![1];
    expect(text(marked).trimEnd()).toBe(
      content
        .split("\n")
        .slice(messages.from, messages.to + 1)
        .join("\n"),
    );
  });

  it("handles a mark on the first and on the last line", () => {
    for (const mark of [
      { from: 0, to: 0 },
      {
        from: content.split("\n").length - 1,
        to: content.split("\n").length - 1,
      },
    ])
      expect(
        text(renderToStaticMarkup(createElement(Code, { content, mark }))),
      ).toBe(content);
  });
});
