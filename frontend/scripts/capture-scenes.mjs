// Development helper: screenshots every lesson scene after one deterministic run.
// Usage: node scripts/capture-scenes.mjs <baseURL> <outDir> [lessonId]
import { chromium } from "@playwright/test";

const [base = "http://127.0.0.1:8770", out = "../.runtime", lesson = "tool-selection"] =
  process.argv.slice(2);
const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
await page.addInitScript(() => {
  localStorage.setItem("agent-lab-entry", "lesson");
  localStorage.setItem("agent-lab-theme", "dark");
});
await page.route("**/api/status", async (route) => {
  const response = await route.fetch();
  await route.fulfill({
    response,
    json: { ...(await response.json()), config_ready: true, api_key_configured: true },
  });
});
await page.route(
  (url) => url.pathname === "/api/runs",
  async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    const response = await route.fetch({
      postData: JSON.stringify({ ...route.request().postDataJSON(), mode: "offline" }),
    });
    await route.fulfill({ response });
  },
);
await page.goto(`${base}/`);
if (lesson !== "tool-selection") {
  const catalog = await (await page.request.get(`${base}/api/curriculum`)).json();
  const entry = catalog.lessons.find((item) => item.id === lesson);
  const category = catalog.categories.find((item) => item.id === entry.category_id);
  const toggle = page.getByTestId("course-nav-category-toggle").filter({ hasText: category.title });
  if ((await toggle.getAttribute("aria-expanded")) !== "true") await toggle.click();
  await page.getByTestId("course-nav-lesson").filter({ hasText: entry.title }).click();
}
await page.getByTestId("scene-tab-lab").click();
await page.getByTestId("lab-run-button").click();
await page.locator("[data-testid='agent-stage'][data-status='completed']").waitFor();
for (const scene of ["understand", "code", "lab", "check", "review"]) {
  await page.getByTestId(`scene-tab-${scene}`).click();
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${out}/scene-${lesson}-${scene}.png`, fullPage: true, animations: "disabled" });
}
await browser.close();
console.log("captured");
