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

test("memory lens shows scope filtering and flags recalled instructions without sending them", async ({
  page,
  request,
}) => {
  // 范围过滤与“召回内容只当数据”在拆分后属于“记忆的更新、过期与召回范围”一课。
  const detail = await (
    await request.get("/api/lessons/memory-lifecycle")
  ).json();
  const scope = detail.exercises.find(
    (item: { id: string }) => item.id === "scope_filter",
  );
  await page.goto("/");
  await openLessonById(page, request, "memory-lifecycle");
  await page.getByTestId("scene-tab-lab").click();
  await page.getByTestId("lab-exercise-field").getByRole("combobox").click();
  await page.getByRole("option", { name: scope.title, exact: true }).click();
  await page.getByTestId("lab-run-button").click();
  await expect(
    page.locator("[data-testid='agent-stage'][data-status='completed']"),
  ).toBeVisible();
  const lens = page.getByTestId("lens-memory");
  await expect(lens.locator("li[data-action='recalled']")).toHaveCount(2);
  await expect(lens.locator("[data-excluded]").first()).toBeVisible();
  await expect(lens.locator("[data-flagged]")).toHaveCount(1);
  await expect(lens.locator("li[data-action='packaged']")).toBeVisible();
});

test("plan lens follows todo snapshots and marks harness reminders", async ({
  page,
  request,
}) => {
  const detail = await (await request.get("/api/lessons/todo-planning")).json();
  const reminder = detail.exercises.find(
    (item: { id: string }) => item.id === "todo-reminder",
  );
  await page.goto("/");
  await openLessonById(page, request, "todo-planning");
  await page.getByTestId("scene-tab-lab").click();
  await expect(page.getByTestId("lens-plan")).toHaveCount(0);
  await page.getByTestId("lab-exercise-field").getByRole("combobox").click();
  await page.getByRole("option", { name: reminder.title, exact: true }).click();
  await page.getByTestId("lab-run-button").click();
  await expect(
    page.locator("[data-testid='agent-stage'][data-status='completed']"),
  ).toBeVisible();
  const lens = page.getByTestId("lens-plan");
  await expect(lens.locator("li[data-status='done']")).toHaveCount(4);
  await expect(lens.locator("[data-injected]")).toBeVisible();
  await page.getByTestId("lab-replay-rewind").click();
  await expect(page.getByTestId("lens-plan")).toHaveCount(0);
});
