import { test, expect, type Page } from "@playwright/test";
import { fileURLToPath } from "node:url";
import type { CurriculumData, CurriculumLesson, Detail } from "../src/types";
import { runOffline } from "./runs";

const screenshot = (name: string) =>
  fileURLToPath(new URL(`../../.runtime/${name}`, import.meta.url));

async function openLesson(
  page: Page,
  catalog: CurriculumData,
  lesson: CurriculumLesson,
) {
  const nav = page.getByRole("navigation", { name: "课程列表" });
  const category = catalog.categories.find(
    (item) => item.id === lesson.category_id,
  )!;
  const toggle = nav
    .locator(".nav-category-toggle")
    .filter({ hasText: category.title });
  if ((await toggle.getAttribute("aria-expanded")) !== "true")
    await toggle.click();
  await nav.locator(".nav-lesson").filter({ hasText: lesson.title }).click();
  await expect(
    page.getByRole("heading", { name: lesson.title, exact: true, level: 1 }),
  ).toBeVisible();
}

test("chapters two and three expose complete guides and run every real preset through the shared extension contract", async ({
  page,
  request,
}) => {
  test.setTimeout(120_000);
  await page.addInitScript(() =>
    localStorage.setItem("agent-lab-entry", "lesson"),
  );
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const catalog: CurriculumData = await (
    await request.get("/api/curriculum")
  ).json();
  const lessons = catalog.lessons.filter((lesson) =>
    ["4", "5", "6", "7", "8", "9", "10"].includes(lesson.id),
  );
  expect(lessons).toHaveLength(7);
  expect(lessons.every((lesson) => lesson.status === "available")).toBe(true);
  let runs = 0;
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
  await runOffline(page, () => runs++);
  await page.goto("/");
  let presets = 0;
  for (const lesson of lessons) {
    const detail: Detail = await (
      await request.get(`/api/lessons/${lesson.id}`)
    ).json();
    await openLesson(page, catalog, lesson);
    await expect(page.locator(".reading-section")).toHaveCount(
      detail.learning!.sections.length,
    );
    await expect(page.locator(".agent-flow-step")).toHaveCount(
      detail.learning!.presentation!.flow.steps.length,
    );
    await page.getByRole("tab", { name: "课后自测", exact: true }).click();
    await expect(page.locator(".quiz-question")).toHaveCount(
      detail.learning!.quiz.length,
    );
    await page.getByRole("tab", { name: "实验工作台", exact: true }).click();
    const inputs = page.getByLabel("实验参数 JSON", { exact: true });
    for (const exercise of detail.exercises.filter(
      (item) => !item.offline_only,
    )) {
      await page.getByRole("combobox", { name: "练习场景" }).click();
      await page
        .getByRole("option", { name: exercise.title, exact: true })
        .click();
      await expect(inputs).toHaveValue(
        JSON.stringify(
          { ...detail.input_defaults, ...exercise.inputs },
          null,
          2,
        ),
      );
      await page.getByRole("button", { name: "运行练习", exact: true }).click();
      await expect(page.locator(".trace-status")).toHaveText("已完成");
      await expect(page.locator(".evidence-report h3")).toBeVisible();
      await expect(page.locator(".answer-content")).not.toBeEmpty();
      await page
        .getByRole("button", { name: "查看报告原始事件", exact: true })
        .click();
      await expect(page.locator(".event-detail pre")).toContainText('"checks"');
      presets++;
    }
    await page.screenshot({
      path: screenshot(`chapter-course-${lesson.id}-lab.png`),
      animations: "disabled",
    });
    const before = runs;
    await page.getByRole("button", { name: "回到起点", exact: true }).click();
    await expect(page.locator(".evidence-report")).toHaveCount(0);
    expect(runs).toBe(before);
    await page.getByRole("tab", { name: "学习课程", exact: true }).click();
    await page.getByRole("tab", { name: "课程导读", exact: true }).click();
  }
  expect(runs).toBe(presets);
  expect(errors).toEqual([]);
});

test("new lesson inputs and evidence reports fit a mobile viewport without requiring a model for local courses", async ({
  page,
  request,
}) => {
  await page.addInitScript(() =>
    localStorage.setItem("agent-lab-entry", "lesson"),
  );
  await page.emulateMedia({ reducedMotion: "reduce", colorScheme: "dark" });
  const catalog: CurriculumData = await (
    await request.get("/api/curriculum")
  ).json();
  await page.route("**/api/status", (route) =>
    route.fulfill({
      json: { model: "", config_ready: false, api_key_configured: false },
    }),
  );
  await runOffline(page);
  await page.goto("/");
  await openLesson(
    page,
    catalog,
    catalog.lessons.find((lesson) => lesson.id === "10")!,
  );
  await page.getByRole("tab", { name: "实验工作台", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "配置模型连接", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "运行练习", exact: true }).click();
  await expect(page.locator(".trace-status")).toHaveText("已完成");
  for (const width of [390, 1440, 2560]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1100 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    ).toBe(true);
    await page.locator(".evidence-board").scrollIntoViewIfNeeded();
    await expect(page.locator(".evidence-report h3")).toBeVisible();
    await page.screenshot({
      path: screenshot(`chapter-memory-${width}-dark.png`),
      animations: "disabled",
    });
  }
});
