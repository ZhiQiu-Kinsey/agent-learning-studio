import { test, expect, type Page } from "@playwright/test";
import quiz from "../src/i18n/locales/zh-CN/quiz.json" with { type: "json" };
import { lessonView } from "../src/content/view";
import { runOffline } from "./runs";

const progressOf = (page: Page) =>
  page.evaluate(() =>
    JSON.parse(localStorage.getItem("agent-lab-progress") ?? "null"),
  );

test.beforeEach(async ({ page }) => {
  await page.route("**/api/status", async (route) => {
    const response = await route.fetch();
    await route.fulfill({
      response,
      json: { ...(await response.json()), config_ready: true },
    });
  });
  await runOffline(page);
});

test("progress records only real local actions and survives a reload", async ({
  page,
  request,
}) => {
  await page.addInitScript(() =>
    localStorage.setItem("agent-lab-entry", "lesson"),
  );
  await page.goto("/");
  const detail = await (await request.get("/api/lessons/1")).json();
  await expect
    .poll(async () => (await progressOf(page))?.lastLessonId)
    .toBe(detail.id);
  let lesson = (await progressOf(page)).lessons[detail.id];
  expect(lesson.scenes.understand).toBeTruthy();
  expect(lesson.runs.count).toBe(0);
  expect(lesson.quiz).toBeUndefined();

  // A completed self-check stores the score that was actually shown.
  await page.getByRole("tab", { name: "课后自测" }).click();
  const questions = lessonView(detail.learning).quiz;
  for (const [index, question] of questions.entries()) {
    const option = question.options.find((item) =>
      index === 0 ? item.id !== question.correct : item.id === question.correct,
    )!;
    await page
      .getByRole("group", { name: question.prompt, exact: true })
      .getByRole("radio", { name: option.text, exact: true })
      .click();
  }
  await page.getByRole("button", { name: quiz.submit, exact: true }).click();
  lesson = (await progressOf(page)).lessons[detail.id];
  expect(lesson.scenes.check).toBeTruthy();
  expect(lesson.quiz).toMatchObject({
    correct: questions.length - 1,
    total: questions.length,
    attempts: 1,
  });

  // One finished run counts once; replaying it does not count again.
  await page.getByRole("tab", { name: "实验工作台", exact: true }).click();
  await page.getByRole("button", { name: "运行练习" }).click();
  await expect
    .poll(async () => (await progressOf(page)).lessons[detail.id].runs.count)
    .toBe(1);
  lesson = (await progressOf(page)).lessons[detail.id];
  expect(lesson.scenes.lab).toBeTruthy();
  expect(lesson.runs.lastRunId).toMatch(/\S/);
  await page.getByRole("button", { name: "回到起点" }).click();
  await page.reload();
  expect((await progressOf(page)).lessons[detail.id].runs.count).toBe(1);
});

test("onboarding checkpoints are self-reported and persist locally", async ({
  page,
  request,
}) => {
  await page.addInitScript(() => localStorage.removeItem("agent-lab-entry"));
  await page.goto("/");
  const content = await (await request.get("/api/onboarding")).json();
  const first = page.locator(".onboarding-checks input").first();
  await first.check();
  const stored = (await progressOf(page)).lessons.onboarding.checkpoints;
  const checkpoint = content.chapters[0].scenes.check.blocks[0].items[0].id;
  expect(Object.keys(stored)).toEqual([`${content.chapters[0].id}/${checkpoint}`]);
  await page.reload();
  await expect(page.locator(".onboarding-checks input").first()).toBeChecked();
  await page.locator(".onboarding-checks input").first().uncheck();
  expect((await progressOf(page)).lessons.onboarding.checkpoints).toEqual({});
});
