import fs from "node:fs";
import { describe, expect, it } from "vitest";
import { outFile, render } from "../../../scripts/gen-content-types.mjs";

describe("content types", () => {
  it("match the exported JSON Schema (run `npm run content:types`)", async () => {
    expect(fs.readFileSync(outFile, "utf8")).toBe(await render());
  }, 20_000);
});
