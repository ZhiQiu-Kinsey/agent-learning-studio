import { test, expect } from "@playwright/test";
import { fileURLToPath } from "node:url";
import type { Detail } from "../src/types";
import { runOffline } from "./runs";
import { chooseExercise, openLessonById } from "./navigation";

const screenshot = (name: string) =>
  fileURLToPath(new URL(`../../.runtime/${name}`, import.meta.url));

const REASONING = [
  "text-actions",
  "todo-planning",
  "plan-and-replan",
  "reflection-revision",
  "workflow-patterns",
  "orchestrator-evaluator",
];

test("reasoning lessons run every preset through the shared lab and evidence board", async ({
  page,
  request,
}) => {
  test.setTimeout(180_000);
  await page.addInitScript(() =>
    localStorage.setItem("agent-lab-entry", "lesson"),
  );
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/api/status", async (route) => {
    const response = await route.fetch();
    await route.fulfill({
      response,
      json: {
        ...(await response.json()),
        api_key_configured: true,
        config_ready: true,
      },
    });
  });
  let runs = 0;
  await runOffline(page, () => runs++);
  await page.goto("/");
  let presets = 0;
  for (const id of REASONING) {
    const detail: Detail = await (
      await request.get(`/api/lessons/${id}`)
    ).json();
    await openLessonById(page, request, id);
    await page.getByTestId("scene-tab-lab").click();
    for (const exercise of detail.exercises) {
      await chooseExercise(page, exercise.id);
      await page.getByTestId("lab-run-button").click();
      await expect(
        page.locator("[data-testid='agent-stage'][data-status='completed']"),
      ).toBeVisible();
      await expect(page.getByTestId("evidence-report").first()).toBeVisible();
      await expect(page.getByTestId("lab-answer")).not.toBeEmpty();
      presets++;
    }
    await page.screenshot({
      path: screenshot(`reasoning-${id}-lab.png`),
      animations: "disabled",
    });
    await page.getByTestId("scene-tab-understand").click();
  }
  expect(runs).toBe(presets);
  expect(errors).toEqual([]);
});
