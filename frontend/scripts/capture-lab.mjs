// Development helper: screenshots the lab after one deterministic run.
// Usage: node scripts/capture-lab.mjs <baseURL> <outDir>   (runs lesson 1 through the deterministic adapter)
import { chromium } from "@playwright/test";

const [base = "http://127.0.0.1:8770", out = "../.runtime"] =
  process.argv.slice(2);
const browser = await chromium.launch({ channel: "chrome" });
for (const theme of ["dark", "light"]) {
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1100 },
  });
  await page.addInitScript((value) => {
    localStorage.setItem("agent-lab-entry", "lesson");
    localStorage.setItem("agent-lab-theme", value);
  }, theme);
  await page.route("**/api/status", async (route) => {
    const response = await route.fetch();
    await route.fulfill({
      response,
      json: {
        ...(await response.json()),
        config_ready: true,
        api_key_configured: true,
      },
    });
  });
  await page.route(
    (url) => url.pathname === "/api/runs",
    async (route) => {
      if (route.request().method() !== "POST") return route.fallback();
      const response = await route.fetch({
        postData: JSON.stringify({
          ...route.request().postDataJSON(),
          mode: "offline",
        }),
      });
      await route.fulfill({ response });
    },
  );
  await page.goto(`${base}/`);
  await page.getByTestId("workspace-tab-lab").click();
  await page.getByTestId("lab-run-button").click();
  await page
    .locator("[data-testid='agent-stage'][data-status='completed']")
    .waitFor();
  await page.getByTestId("lab-replay-step").waitFor();
  await page.getByTestId("agent-stage").scrollIntoViewIfNeeded();
  await page.screenshot({
    path: `${out}/lab-stage-${theme}.png`,
    fullPage: true,
    animations: "disabled",
  });
  // Mid-replay: cursor on the first tool call.
  await page.getByTestId("lab-replay-rewind").click();
  for (let i = 0; i < 4; i++) await page.getByTestId("lab-replay-step").click();
  await page
    .getByTestId("agent-stage")
    .screenshot({
      path: `${out}/lab-stage-mid-${theme}.png`,
      animations: "disabled",
    });
  await page.close();
}
await browser.close();
console.log("captured");
