import { defineConfig } from "vitest/config";

// Unit tests for pure frontend logic; browser flows live in e2e/ (Playwright).
export default defineConfig({
  test: { include: ["src/**/*.test.ts"], environment: "node" },
});
