import { test, expect } from "@playwright/test";
import { fileURLToPath } from "node:url";
import type { CurriculumData, Detail, Lesson } from "../src/types";
import { isRunCreation, runOffline } from "./runs";
import { t } from "./i18n";
import { openLessonById } from "./navigation";
import { chapterView, lessonView } from "../src/content/view";
import { routePlannedLesson, withPlannedLesson } from "./catalog";

const capture = (name: string) =>
  fileURLToPath(new URL(`../../.runtime/${name}`, import.meta.url));

test("first visit teaches prerequisites, cites sources and exposes the real course tree", async ({
  page,
  request,
}) => {
  // 验的是导学内容与课程树，不是动效；无头浏览器没有 GPU，首页与导学的 WebGL 背景靠软件渲染，
  // 这条点遍所有章节的用例会因此逼近 30 秒上限。
  await page.emulateMedia({ reducedMotion: "reduce" });
  let runs = 0;
  page.on("request", (req) => {
    if (isRunCreation(req)) runs++;
  });
  const firstLesson: Detail = await (
    await request.get("/api/lessons/chat-request")
  ).json();
  await page.goto("/");
  // First visit lands on the home page; chapter 0 (onboarding) is one click away.
  await expect(page.getByTestId("home-page")).toBeVisible();
  await expect(page.getByTestId("home-journey-category")).toHaveCount(
    (await (await request.get("/api/curriculum")).json()).categories.length,
  );
  await page.getByTestId("home-start-onboarding").click();
  await expect(
    page.getByTestId("onboarding-hero").getByRole("heading", { level: 1 }),
  ).toBeVisible();
  await expect(page.getByTestId("lesson-masthead")).toHaveCount(0);
  const curriculum: CurriculumData = await (
    await request.get("/api/curriculum")
  ).json();
  const catalog: { lessons: Lesson[] } = await (
    await request.get("/api/lessons")
  ).json();
  const available = curriculum.lessons.filter(
    (lesson) =>
      lesson.status === "available" &&
      catalog.lessons.some((item) => item.id === lesson.id && item.available),
  );
  const navLessons = page.getByTestId("course-nav-lesson");
  await expect(navLessons).toHaveCount(curriculum.lessons.length);
  await expect(navLessons.and(page.locator(":disabled"))).toHaveCount(
    curriculum.lessons.length - available.length,
  );
  await expect(page.getByTestId("course-nav-category-toggle")).toHaveCount(
    curriculum.categories.length,
  );
  await expect(page.getByTestId("course-nav-module")).toHaveCount(
    curriculum.categories.reduce(
      (count, category) => count + category.modules.length,
      0,
    ),
  );
  const content = await (await request.get("/api/onboarding")).json();
  const sources = page.getByTestId("onboarding-sources");
  await sources.getByRole("button").click();
  await expect(sources.getByRole("link")).toHaveCount(
    chapterView(content.chapters[0]).references.length,
  );
  const chapterNav = page.getByTestId("onboarding-chapter-tabs");
  const chapterHeading = page
    .getByTestId("onboarding-chapter")
    .getByRole("heading", { level: 2 });
  for (const chapter of content.chapters) {
    await chapterNav.getByRole("button", { name: chapter.title }).click();
    await expect(chapterHeading).toHaveText(chapter.title);
    await expect(page.getByTestId("onboarding-section")).toHaveCount(
      chapterView(chapter).sections.length,
    );
    const checks = page.getByTestId("onboarding-checks").locator("input");
    for (let index = 0; index < (await checks.count()); index++)
      await checks.nth(index).check();
  }
  // 自检计数文案仍硬编码在 Onboarding.tsx。
  await expect(page.getByTestId("onboarding-meta")).toContainText(
    `${content.chapters.length} 节已自检`,
  );
  await page.getByTestId("onboarding-next").click();
  await expect(
    page.getByRole("heading", { name: firstLesson.title, exact: true }),
  ).toBeVisible();
  expect(runs).toBe(0);
});

test("unimplemented navigation stays disabled and an onboarding request failure can be retried", async ({
  page,
  request,
}) => {
  await routePlannedLesson(page);
  const curriculum: CurriculumData = withPlannedLesson(
    await (await request.get("/api/curriculum")).json(),
  );
  const plannedLesson = curriculum.lessons.find(
    (lesson) => lesson.status === "planned",
  )!;
  const categoryIndex = curriculum.categories.findIndex((category) =>
    category.modules.some((module) =>
      module.lesson_ids.includes(plannedLesson.id),
    ),
  );
  const failure = "前置章节暂时不可用";
  let fail = true;
  await page.route("**/api/onboarding", async (route) => {
    if (fail)
      await route.fulfill({
        status: 503,
        json: { detail: failure },
      });
    else await route.continue();
  });
  await page.goto("/");
  await page.getByTestId("home-start-onboarding").click();
  await expect(page.getByRole("alert")).toContainText(failure);
  fail = false;
  await page.getByTestId("onboarding-retry").click();
  await expect(page.getByTestId("onboarding-hero")).toBeVisible();
  const categories = page.getByTestId("course-nav-category-toggle");
  if (
    (await categories.nth(categoryIndex).getAttribute("aria-expanded")) !==
    "true"
  )
    await categories.nth(categoryIndex).click();
  const planned = page
    .getByTestId("course-nav-category")
    .nth(categoryIndex)
    .getByTestId("course-nav-lesson")
    .and(page.locator(":disabled"))
    .first();
  await expect(planned).toBeVisible();
  await expect(planned).toBeDisabled();
  // “计划中”标记仍硬编码在 CourseNavigation.tsx。
  await expect(planned).toContainText("计划中");
  expect(await page.getByTestId("onboarding-page").isVisible()).toBe(true);
});

test("interactive lesson explanations are different for all three lessons and never execute a model", async ({
  page,
  request,
}) => {
  await page.addInitScript(() =>
    localStorage.setItem("agent-lab-entry", "lesson"),
  );
  let runs = 0;
  page.on("request", (req) => {
    if (isRunCreation(req)) runs++;
  });
  await page.goto("/");
  for (const id of ["tool-selection", "dependent-calls", "fail-safely"]) {
    const detail = await (await request.get(`/api/lessons/${id}`)).json();
    await page
      .getByTestId("course-nav")
      .getByRole("button", { name: detail.title })
      .click();
    // 课程头部带本课副标题，换课后随之更新。
    await expect(page.getByTestId("lesson-masthead")).toContainText(
      detail.subtitle,
    );
    const steps = page.getByTestId("agent-flow-step");
    await expect(steps).toHaveCount(
      lessonView(detail.learning).walkthrough!.steps.length,
    );
    const flowSteps = lessonView(detail.learning).walkthrough!.steps;
    for (let i = 0; i < flowSteps.length; i++) {
      await steps.nth(i).click();
      await expect(
        page.getByTestId("agent-flow-explanation").getByRole("heading", {
          level: 3,
        }),
      ).toHaveText(flowSteps[i].title);
      await expect(
        page.getByTestId("agent-flow-code").locator("code"),
      ).toHaveText(flowSteps[i].code!);
    }
    // 示意内容必须标注为“教学示意 · 非运行记录”。
    await expect(page.getByTestId("agent-flow-provenance")).toHaveText(
      t("provenance.illustration"),
    );
    await expect(page.getByTestId("agent-flow")).toContainText(
      t("provenance.illustration"),
    );
    await expect(page.getByTestId("learn-reading-section")).toHaveCount(
      lessonView(detail.learning).sections.length,
    );
  }
  expect(runs).toBe(0);
});

test("stage nodes and tool cards follow execution evidence and replay", async ({
  page,
  request,
}) => {
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
  let runs = 0;
  await runOffline(page, () => runs++);
  const stage = page.getByTestId("agent-stage");
  const nodes = stage.locator("[data-testid^='stage-node-']");
  const lit = stage.locator(
    "[data-testid^='stage-node-']:not([data-state='dormant'])",
  );
  await page.goto("/");
  // 第一门课不带工具；工具卡片在“执行工具与回传结果”里。
  await openLessonById(page, request, "tool-selection");
  await page.getByTestId("scene-tab-lab").click();
  // Before any run the stage shows no topology at all, not a placeholder run.
  await expect(nodes).toHaveCount(0);
  await page.getByTestId("lab-run-button").click();
  await expect(page.getByTestId("lab-trace-status")).toHaveText("已完成");
  await expect(stage).toHaveAttribute("data-provenance", "real_run");
  await expect(stage).toHaveAttribute("data-status", "completed");
  await expect(
    stage.getByTestId("stage-node-tool:add_numbers"),
  ).toHaveAttribute("data-state", "idle");
  await expect(lit).toHaveCount(await nodes.count());
  const card = page.getByTestId("tool-card").filter({ hasText: "add_numbers" });
  await card.locator("summary").click();
  await card.getByTestId("tool-card-inspect").click();
  await expect(
    page.getByTestId("lab-event-detail").locator("pre"),
  ).toContainText("42");
  await page.getByTestId("lab-replay-rewind").click();
  // Rewinding keeps the run's topology but nothing is reached yet.
  await expect(nodes).not.toHaveCount(0);
  await expect(lit).toHaveCount(0);
  await expect(page.getByTestId("tool-card")).toHaveCount(0);
  expect(runs).toBe(1);
});

test("new entry and chapters remain readable in light, dark and reduced motion at three widths", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const content = await (await request.get("/api/onboarding")).json();
  const [preface, intro] = content.chapters;
  const chapterHeading = page
    .getByTestId("onboarding-chapter")
    .getByRole("heading", { level: 2 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const theme of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme: theme });
    for (const width of [390, 1440, 2560]) {
      await page.setViewportSize({ width, height: width === 390 ? 844 : 1080 });
      await page.goto("/");
      await page.getByTestId("home-start-onboarding").click();
      await expect(chapterHeading).toHaveText(preface.title);
      // 首页主标题仍硬编码在 Onboarding.tsx。
      await expect(
        page.getByTestId("onboarding-hero").getByRole("heading", { level: 1 }),
      ).toHaveText("先理解 Agent，再亲手构建。");
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth + 1,
        ),
      ).toBe(true);
      await page.screenshot({
        path: capture(`onboarding-${width}-${theme}.png`),
        animations: "disabled",
      });
      await page
        .getByTestId("onboarding-chapter-tabs")
        .getByRole("button", { name: intro.title })
        .click();
      await expect(chapterHeading).toHaveText(intro.title);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth + 1,
        ),
      ).toBe(true);
      await expect(
        page.getByTestId("onboarding-chapter").getByRole("table").first(),
      ).toBeVisible();
    }
  }
  expect(errors).toEqual([]);
});
