import { describe, expect, it } from "vitest";
import { createLanguageCache } from "../languageCache";

describe("language cache", () => {
  it("shares one request per language and refetches for a new language", async () => {
    const calls: string[] = [];
    const cache = createLanguageCache(async (language) => {
      calls.push(language);
      return { language };
    });
    const [a, b] = await Promise.all([cache.load("zh-CN"), cache.load("zh-CN")]);
    expect(a).toBe(b);
    expect(calls).toEqual(["zh-CN"]);
    // Switching language must not serve the cached zh-CN value.
    expect((await cache.load("en")).language).toBe("en");
    expect(calls).toEqual(["zh-CN", "en"]);
    // Switching back is served from the cache, without another request.
    expect(cache.peek("zh-CN")).toBe(a);
    await cache.load("zh-CN");
    expect(calls).toEqual(["zh-CN", "en"]);
  });

  it("forgets a failed request so the next caller retries", async () => {
    let attempt = 0;
    const cache = createLanguageCache(async () => {
      attempt += 1;
      if (attempt === 1) throw new Error("offline");
      return attempt;
    });
    await expect(cache.load("en")).rejects.toThrow("offline");
    expect(cache.peek("en")).toBeUndefined();
    expect(await cache.load("en")).toBe(2);
  });
});
