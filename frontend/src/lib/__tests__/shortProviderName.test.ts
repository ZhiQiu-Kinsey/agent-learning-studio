import { describe, expect, it } from "vitest";
import { shortProviderName } from "../shortProviderName";

describe("shortProviderName", () => {
  it("drops a trailing qualifier in ASCII or full-width parentheses", () => {
    expect(shortProviderName("Bailian (raw HTTP)")).toBe("Bailian");
    expect(shortProviderName("Ollama (local)")).toBe("Ollama");
    expect(shortProviderName("百炼（原生 HTTP）")).toBe("百炼");
    expect(shortProviderName("Ollama（本地）")).toBe("Ollama");
  });

  it("keeps names without a qualifier", () => {
    expect(shortProviderName("OpenAI compatible")).toBe("OpenAI compatible");
    expect(shortProviderName("DeepSeek")).toBe("DeepSeek");
  });

  it("never returns an empty name", () => {
    expect(shortProviderName("(custom)")).toBe("(custom)");
  });
});
