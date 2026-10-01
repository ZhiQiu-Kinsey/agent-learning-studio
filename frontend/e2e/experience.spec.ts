import { test, expect } from "@playwright/test";
import { fileURLToPath } from "node:url";
import type { CurriculumData, Lesson } from "../src/types";

const capture = (name: string) =>
  fileURLToPath(new URL(`../../.runtime/${name}`, import.meta.url));

test("first visit teaches prerequisites, cites sources and exposes the real course tree", async ({
  page,
  request,
}) => {
  let runs = 0;
  page.on("request", (req) => {
    if (req.url().endsWith("/api/run")) runs++;
  });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "先理解 Agent，再亲手构建。" }),
  ).toBeVisible();
  await expect(page.locator(".lesson-masthead")).toHaveCount(0);
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
  await expect(page.locator(".nav-lesson")).toHaveCount(
    curriculum.lessons.length,
  );
  await expect(page.locator(".nav-lesson:disabled")).toHaveCount(
    curriculum.lessons.length - available.length,
  );
  await expect(page.locator(".nav-category-toggle")).toHaveCount(
    curriculum.categories.length,
  );
  await expect(page.locator(".nav-module")).toHaveCount(
    curriculum.categories.reduce(
      (count, category) => count + category.modules.length,
      0,
    ),
  );
  const content = await (await request.get("/api/onboarding")).json();
  await page.locator(".onboarding-sources").getByRole("button").click();
  await expect(page.locator(".onboarding-sources a")).toHaveCount(
    content.chapters[0].references.length,
  );
  const chapterNav = page.getByRole("navigation", { name: "前置导学章节" });
  for (const chapter of content.chapters) {
    await chapterNav
      .getByRole("button", { name: new RegExp(chapter.title) })
      .click();
    await expect(page.locator(".onboarding-chapter h2")).toHaveText(
      chapter.title,
    );
    await expect(page.locator(".onboarding-section")).toHaveCount(
      chapter.sections.length,
    );
    const checks = page.locator(".onboarding-checks input");
    for (let index = 0; index < (await checks.count()); index++)
      await checks.nth(index).check();
  }
  await expect(page.locator(".onboarding-meta")).toContainText(
    `${content.chapters.length} 节已自检`,
  );
  await page
    .getByRole("button", { name: "开始第 1 课：工具选择", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "工具选择", exact: true }),
  ).toBeVisible();
  expect(runs).toBe(0);
});

test("unimplemented navigation stays disabled and an onboarding request failure can be retried", async ({
  page,
  request,
}) => {
  const curriculum: CurriculumData = await (
    await request.get("/api/curriculum")
  ).json();
  const plannedLesson = curriculum.lessons.find(
    (lesson) => lesson.status === "planned",
  )!;
  const categoryIndex = curriculum.categories.findIndex((category) =>
    category.modules.some((module) =>
      module.lesson_ids.includes(plannedLesson.id),
    ),
  );
  let fail = true;
  await page.route("**/api/onboarding", async (route) => {
    if (fail)
      await route.fulfill({
        status: 503,
        json: { detail: "前置章节暂时不可用" },
      });
    else await route.continue();
  });
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText("前置章节暂时不可用");
  fail = false;
  await page.getByRole("button", { name: "重新加载导学" }).click();
  await expect(page.locator(".onboarding-hero")).toBeVisible();
  const categories = page.locator(".nav-category-toggle");
  if (
    (await categories.nth(categoryIndex).getAttribute("aria-expanded")) !==
    "true"
  )
    await categories.nth(categoryIndex).click();
  const planned = page
    .locator(".nav-category")
    .nth(categoryIndex)
    .locator(".nav-lesson:disabled")
    .first();
  await expect(planned).toBeVisible();
  await expect(planned).toBeDisabled();
  await expect(planned).toContainText("计划中");
  expect(await page.locator(".onboarding-page").isVisible()).toBe(true);
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
    if (req.url().endsWith("/api/run")) runs++;
  });
  await page.goto("/");
  for (const id of ["1", "2", "3"]) {
    const detail = await (await request.get(`/api/lessons/${id}`)).json();
    await page
      .getByRole("navigation", { name: "课程列表" })
      .getByRole("button", { name: new RegExp(detail.title) })
      .click();
    await expect(page.locator(".lesson-hero h2")).toContainText(
      detail.learning.presentation.highlight,
    );
    const steps = page.locator(".agent-flow-step");
    await expect(steps).toHaveCount(
      detail.learning.presentation.flow.steps.length,
    );
    for (let i = 0; i < detail.learning.presentation.flow.steps.length; i++) {
      await steps.nth(i).click();
      await expect(page.locator(".agent-flow-explanation h3")).toHaveText(
        detail.learning.presentation.flow.steps[i].title,
      );
      await expect(page.locator(".agent-flow-code code")).toHaveText(
        detail.learning.presentation.flow.steps[i].code,
      );
    }
    await expect(page.locator(".agent-flow")).toContainText("教学示意");
    await expect(page.locator(".reading-section")).toHaveCount(
      detail.learning.sections.length,
    );
  }
  expect(runs).toBe(0);
});

test("live signal nodes and tool chips follow execution evidence and replay", async ({
  page,
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
  await page.route("**/api/run", async (route) => {
    runs++;
    const response = await route.fetch({
      postData: JSON.stringify({
        ...route.request().postDataJSON(),
        mode: "offline",
      }),
    });
    await route.fulfill({ response });
  });
  await page.goto("/");
  await page.getByRole("tab", { name: "实验工作台", exact: true }).click();
  await expect(page.locator(".execution-node:disabled")).toHaveCount(4);
  await page.getByRole("button", { name: "运行练习", exact: true }).click();
  await expect(page.locator(".trace-status")).toHaveText("已完成");
  await expect(page.locator(".execution-node:disabled")).toHaveCount(0);
  await page.getByRole("button", { name: "查看 add_numbers 完成结果" }).click();
  await expect(page.locator(".event-detail pre")).toContainText("42");
  await page.getByRole("button", { name: "回到起点" }).click();
  await expect(page.locator(".execution-node:disabled")).toHaveCount(4);
  await expect(page.locator(".execution-tools")).toHaveCount(0);
  expect(runs).toBe(1);
});

test("new entry and chapters remain readable in light, dark and reduced motion at three widths", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const theme of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme: theme });
    for (const width of [390, 1440, 2560]) {
      await page.setViewportSize({ width, height: width === 390 ? 844 : 1080 });
      await page.goto("/");
      await expect(page.locator(".onboarding-chapter h2")).toHaveText(
        "学习前言",
      );
      await expect(page.locator(".onboarding-hero h1")).toHaveText(
        "先理解 Agent，再亲手构建。",
      );
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
        .getByRole("navigation", { name: "前置导学章节" })
        .getByRole("button", { name: /认识 Agent/ })
        .click();
      await expect(page.locator(".onboarding-chapter h2")).toHaveText(
        "认识 Agent",
      );
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth + 1,
        ),
      ).toBe(true);
      await expect(
        page.locator(".onboarding-chapter table").first(),
      ).toBeVisible();
    }
  }
  expect(errors).toEqual([]);
});
