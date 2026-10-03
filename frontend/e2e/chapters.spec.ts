import { test, expect, type Page } from "@playwright/test";
import { fileURLToPath } from "node:url";
import type { CurriculumData, CurriculumLesson, Detail } from "../src/types";
import { runOffline } from "./runs";
import { t } from "./i18n";
import { lessonView } from "../src/content/view";
import { chooseExercise } from "./navigation";

const screenshot = (name: string) =>
  fileURLToPath(new URL(`../../.runtime/${name}`, import.meta.url));

async function openLesson(
  page: Page,
  catalog: CurriculumData,
  lesson: CurriculumLesson,
) {
  const nav = page.getByTestId("course-nav");
  const category = catalog.categories.find(
    (item) => item.id === lesson.category_id,
  )!;
  const toggle = nav
    .getByTestId("course-nav-category-toggle")
    .filter({ hasText: category.title });
  if ((await toggle.getAttribute("aria-expanded")) !== "true")
    await toggle.click();
  await nav
    .getByTestId("course-nav-lesson")
    .filter({ hasText: lesson.title })
    .click();
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
    [
      "task-contract",
      "structured-output",
      "prompt-experiments",
      "messages-context",
      "application-state",
      "context-budget",
      "persistent-memory",
    ].includes(lesson.id),
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
    // The badge shows the server-computed display number, not the slug id.
    await expect(page.getByTestId("lesson-badge")).toHaveText(
      String(lesson.number).padStart(2, "0"),
    );
    await expect(page.getByTestId("learn-reading-section")).toHaveCount(
      lessonView(detail.learning).sections.length,
    );
    await expect(page.getByTestId("agent-flow-step")).toHaveCount(
      lessonView(detail.learning).walkthrough!.steps.length,
    );
    await page.getByTestId("scene-tab-check").click();
    await expect(page.getByTestId("quiz-question")).toHaveCount(
      lessonView(detail.learning).quiz.length,
    );
    await page.getByTestId("scene-tab-lab").click();
    // Controls are generated from the input schema; JSON stays available as the advanced mode.
    await expect(page.getByTestId("schema-inputs")).toBeVisible();
    await page.getByTestId("lab-inputs-mode").click();
    const inputs = page.getByTestId("lab-inputs-json");
    for (const exercise of detail.exercises.filter(
      (item) => !item.offline_only,
    )) {
      await chooseExercise(page, exercise.id);
      await expect(inputs).toHaveValue(
        JSON.stringify(
          { ...detail.input_defaults, ...exercise.inputs },
          null,
          2,
        ),
      );
      await page.getByTestId("lab-run-button").click();
      await expect(page.getByTestId("lab-trace-status")).toHaveText("已完成");
      await expect(
        page.getByTestId("evidence-report").getByRole("heading", { level: 3 }),
      ).toBeVisible();
      await expect(page.getByTestId("lab-answer")).not.toBeEmpty();
      await page
        .getByRole("button", { name: t("lab:evidence.rawLabel"), exact: true })
        .click();
      await expect(
        page.getByTestId("lab-event-detail").locator("pre"),
      ).toContainText('"checks"');
      presets++;
    }
    await page.screenshot({
      path: screenshot(`chapter-course-${lesson.id}-lab.png`),
      animations: "disabled",
    });
    const before = runs;
    await page.getByTestId("lab-replay-rewind").click();
    await expect(page.getByTestId("evidence-report")).toHaveCount(0);
    expect(runs).toBe(before);
    await page.getByTestId("scene-tab-understand").click();
    await page.getByTestId("scene-tab-understand").click();
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
    // 不调用模型的课：持久记忆拆分后，保存与召回范围的本地练习在这门课里。
    catalog.lessons.find((lesson) => lesson.id === "memory-lifecycle")!,
  );
  await page.getByTestId("scene-tab-lab").click();
  await expect(page.getByTestId("lab-configure-button")).toHaveCount(0);
  await page.getByTestId("lab-run-button").click();
  await expect(page.getByTestId("lab-trace-status")).toHaveText("已完成");
  for (const width of [390, 1440, 2560]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1100 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    ).toBe(true);
    await page
      .getByRole("region", { name: t("lab:evidence.region") })
      .scrollIntoViewIfNeeded();
    await expect(
      page.getByTestId("evidence-report").getByRole("heading", { level: 3 }),
    ).toBeVisible();
    await page.screenshot({
      path: screenshot(`chapter-memory-${width}-dark.png`),
      animations: "disabled",
    });
  }
});
