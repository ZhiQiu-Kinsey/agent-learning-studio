import { describe, expect, it } from "vitest";
import { controlFor } from "../SchemaInputs";

describe("controlFor", () => {
  it("maps INPUT_MODEL schema types to controls", () => {
    expect(controlFor({ type: "string", enum: ["omit", "full_only"] })).toBe(
      "segment",
    );
    expect(
      controlFor({ type: "string", enum: ["a", "b", "c", "d", "e"] }),
    ).toBe("select");
    // 选项文字太长时，分段按钮在窄屏会横向溢出，改用下拉。
    expect(
      controlFor({ type: "string", enum: ["a", "b", "c"] }, [
        "两个写入方与过时写入",
        "过期、删除与重开核对",
        "按范围召回，召回内容只当数据",
      ]),
    ).toBe("select");
    expect(
      controlFor({ type: "string", enum: ["a", "b"] }, ["完整", "移除"]),
    ).toBe("segment");
    expect(controlFor({ type: "boolean" })).toBe("switch");
    expect(controlFor({ type: "integer", minimum: 400, maximum: 4000 })).toBe(
      "scrub",
    );
    // Short integer ranges fit an elastic slider; fractions stay precise.
    expect(controlFor({ type: "integer", minimum: 1, maximum: 5 })).toBe(
      "elastic",
    );
    expect(controlFor({ type: "integer", minimum: 2, maximum: 25 })).toBe(
      "elastic",
    );
    expect(controlFor({ type: "number", minimum: 0, maximum: 1 })).toBe(
      "scrub",
    );
    expect(controlFor({ type: "integer" })).toBe("unsupported"); // unbounded numbers stay in JSON mode
    expect(controlFor({ type: "string", maxLength: 40 })).toBe("text");
    expect(controlFor({ type: "string", maxLength: 200 })).toBe("textarea");
    expect(controlFor({})).toBe("unsupported");
  });
});
