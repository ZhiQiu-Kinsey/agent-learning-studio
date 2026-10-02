import { test, expect } from "@playwright/test";
import { runOffline } from "./runs";
import { openLessonById } from "./navigation";

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() =>
    localStorage.setItem("agent-lab-entry", "lesson"),
  );
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
  await runOffline(page);
});

for (const { lesson, lens } of [
  { lesson: "task-contract", lens: "lens-task-card" },
  { lesson: "context-budget", lens: "lens-budget" },
  { lesson: "persistent-memory", lens: "lens-memory" },
]) {
  test(`${lesson} shows its lens only from real events and rewinds with replay`, async ({
    page,
    request,
  }) => {
    const detail = await (await request.get(`/api/lessons/${lesson}`)).json();
    await page.goto("/");
    await openLessonById(page, request, lesson);
    await expect(page.getByTestId("lesson-badge")).toHaveText(
      String(detail.number).padStart(2, "0"),
    );
    await page.getByTestId("scene-tab-lab").click();
    await expect(page.getByTestId(lens)).toHaveCount(0);
    await page.getByTestId("lab-run-button").click();
    await expect(
      page.locator("[data-testid='agent-stage'][data-status='completed']"),
    ).toBeVisible();
    await expect(page.getByTestId(lens)).toBeVisible();
    if (lens === "lens-budget") {
      // The budget line comes from this run's char_budget input, not a constant.
      const budget = String(detail.exercises[0].inputs.char_budget);
      await expect(page.getByTestId(lens)).toContainText(budget);
    }
    await page.getByTestId("lab-replay-rewind").click();
    await expect(page.getByTestId(lens)).toHaveCount(0);
  });
}
