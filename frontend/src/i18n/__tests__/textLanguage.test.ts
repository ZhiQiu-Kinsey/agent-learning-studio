import { describe, expect, it } from "vitest";
import {
  fallbackLang,
  isChineseText,
  translationState,
  type ContentI18n,
} from "../textLanguage";

describe("fallback language marking", () => {
  it("marks Chinese strings only under a non-Chinese UI", () => {
    const zh = "一次请求就是一个 JSON 对象。";
    expect(fallbackLang(zh, "en")).toBe("zh-CN");
    expect(fallbackLang(zh, "zh-CN")).toBeUndefined();
    expect(fallbackLang("One request is one JSON object.", "en")).toBeUndefined();
    expect(fallbackLang("", "en")).toBeUndefined();
  });

  it("keeps an English sentence that quotes a Chinese phrase English", () => {
    expect(
      isChineseText(
        'The preset question is "用一句话解释什么是 Agent。" and it stays in Chinese because it is sent to the model as is.',
      ),
    ).toBe(false);
    expect(isChineseText("用一句话解释什么是 Agent。")).toBe(true);
    expect(isChineseText("Agent 循环")).toBe(true);
    expect(isChineseText("tool_calls")).toBe(false);
  });
});

describe("translation state", () => {
  const info = (patch: Partial<ContentI18n>): ContentI18n => ({
    requested: "en",
    locale: "en",
    source_language: "zh-CN",
    total: 10,
    translated: 10,
    missing: [],
    stale: [],
    ...patch,
  });

  it("tells source, complete, partial and untranslated content apart", () => {
    expect(translationState(undefined)).toBe("source");
    expect(translationState(info({ requested: "zh-CN", locale: "zh-CN" }))).toBe("source");
    expect(translationState(info({}))).toBe("complete");
    expect(translationState(info({ translated: 8, stale: ["a.title"] }))).toBe("partial");
    expect(translationState(info({ translated: 9, missing: ["b.text"] }))).toBe("partial");
    expect(
      translationState(info({ locale: "zh-CN", translated: 0, missing: ["a"] })),
    ).toBe("none");
  });
});
