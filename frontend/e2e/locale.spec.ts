import { test, expect, type Page } from "@playwright/test";
import type { CurriculumData, Detail } from "../src/types";
import { t, tIn } from "./i18n";
import { runOffline } from "./runs";

const lessonId = "chat-request";

async function switchToEnglish(page: Page) {
  await page.getByRole("combobox", { name: t("language.label") }).click();
  await page.getByRole("option", { name: "English", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
}

test("switching to English translates the UI, refetches content in place and persists", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.addInitScript(() =>
    localStorage.setItem("agent-lab-entry", "lesson"),
  );
  const zh: Detail = await (
    await request.get(`/api/lessons/${lessonId}`)
  ).json();
  const en: Detail = await (
    await request.get(`/api/lessons/${lessonId}?lang=en`)
  ).json();
  test.skip(
    en.learning_i18n?.locale !== "en",
    "这门课还没有英文内容译文层",
  );
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: zh.title, exact: true, level: 1 }),
  ).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", "zh-CN");

  // Stay on the code scene: a language switch must not reset the lesson or scene.
  await page.getByTestId("scene-tab-code").click();
  await switchToEnglish(page);
  await expect(page.getByTestId("scene-tab-code")).toHaveAttribute(
    "data-state",
    "active",
  );
  await expect(
    page.getByRole("combobox", { name: tIn("en", "theme.label") }),
  ).toBeVisible();
  await expect(page.getByTestId("scene-tab-understand")).toContainText(
    tIn("en", "lesson:scenes.understand"),
  );
  await expect(
    page.getByRole("heading", { name: en.title, exact: true, level: 1 }),
  ).toBeVisible();

  // The lesson body comes from the English overlay, without a "not translated" note.
  await page.getByTestId("scene-tab-understand").click();
  const prose = (en.learning?.scenes.understand?.blocks ?? []).find(
    (block) => block.type === "prose" && block.title,
  ) as { title: string } | undefined;
  expect(prose).toBeDefined();
  await expect(
    page
      .getByTestId("learn-reading-section")
      .getByRole("heading", { name: prose!.title, exact: true }),
  ).toBeVisible();
  await expect(page.getByTestId("translation-notice")).toHaveCount(0);

  // The choice is saved and applied before the first paint after a reload.
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(
    page.getByRole("combobox", { name: tIn("en", "language.label") }),
  ).toHaveText("English");
  await expect(
    page.getByRole("heading", { name: en.title, exact: true, level: 1 }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("a lesson without an English overlay stays Chinese and is marked zh-CN", async ({
  page,
  request,
}) => {
  await page.addInitScript(() => {
    localStorage.setItem("agent-lab-entry", "lesson");
    localStorage.setItem("agent-lab-locale", "en");
  });
  // Serve this lesson as the server does for a language that has no overlay
  // (a real response, only the language code differs): every string falls back.
  await page.route(
    (url) =>
      url.pathname === `/api/lessons/${lessonId}` &&
      url.searchParams.get("lang") === "en",
    async (route) => {
      const response = await request.get(`/api/lessons/${lessonId}?lang=fr`);
      await route.fulfill({ response });
    },
  );
  const fallback: Detail = await (
    await request.get(`/api/lessons/${lessonId}?lang=fr`)
  ).json();
  expect(fallback.learning_i18n?.locale).toBe("zh-CN");
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  const notice = page.getByTestId("translation-notice");
  await expect(notice).toHaveText(tIn("en", "translation.pending"));
  await expect(notice).toHaveAttribute("data-state", "none");
  const scene = page.getByTestId("scene-understand");
  await expect(
    scene.locator('[data-testid="learn-reading-section"] [lang="zh-CN"]').first(),
  ).toBeVisible();
  // UI chrome around the Chinese text is still English.
  await expect(page.getByTestId("scene-tab-understand")).toContainText(
    tIn("en", "lesson:scenes.understand"),
  );
});

// Runtime language: what a run sends and records follows the UI language when
// the lesson supports it. Runs go to the backend's offline test mode at the
// network boundary (e2e/runs.ts); tools still really run.
test.describe("runtime language", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/status", async (route) => {
      const response = await route.fetch();
      const body = await response.json().catch(() => undefined);
      if (body === undefined) return;
      await route.fulfill({
        response,
        json: { ...body, config_ready: true, api_key_configured: true },
      });
    });
  });

  async function openLab(page: Page, locale: "zh-CN" | "en") {
    await page.addInitScript((value) => {
      localStorage.setItem("agent-lab-entry", "lesson");
      localStorage.setItem("agent-lab-locale", value);
    }, locale);
    await page.goto("/");
    await page.getByTestId("scene-tab-lab").click();
  }

  test("an English run sends the UI language and runs in English", async ({
    page,
    request,
  }) => {
    const en: Detail = await (
      await request.get(`/api/lessons/${lessonId}?lang=en`)
    ).json();
    test.skip(en.runtime_locale !== "en", "这门课还没有英文运行时");
    const payloads: Record<string, unknown>[] = [];
    await runOffline(page, (payload) => payloads.push(payload));
    await openLab(page, "en");
    await expect(page.getByTestId("lab-question-input")).toHaveValue(
      en.exercises[0].question,
    );
    await page.getByTestId("lab-run-button").click();
    await expect(page.getByTestId("lab-trace-status")).toHaveText(
      tIn("en", "lab:bench.status.completed"),
    );
    expect(payloads[0]).toMatchObject({ locale: "en", exercise_id: "basic" });
    await expect(page.getByTestId("lab-answer")).toHaveAttribute("lang", "en");
    await expect(page.getByTestId("lab-answer")).toContainText(
      "Offline script answer",
    );
    // Same language as the UI: nothing to point out.
    await expect(page.getByTestId("lab-run-locale")).toHaveCount(0);
    await expect(page.getByTestId("lab-runtime-locale")).toHaveCount(0);
  });

  test("a Chinese run stays Chinese and is labelled after switching to English", async ({
    page,
    request,
  }) => {
    const en: Detail = await (
      await request.get(`/api/lessons/${lessonId}?lang=en`)
    ).json();
    test.skip(en.runtime_locale !== "en", "这门课还没有英文运行时");
    await runOffline(page);
    await openLab(page, "zh-CN");
    await page.getByTestId("lab-run-button").click();
    await expect(page.getByTestId("lab-trace-status")).toHaveText(
      t("lab:bench.status.completed"),
    );
    const answer = await page.getByTestId("lab-answer").innerText();
    await switchToEnglish(page);
    // Replay is read-only: the recorded run is unchanged and says which language it is in.
    await expect(page.getByTestId("lab-answer")).toHaveText(answer);
    await expect(page.getByTestId("lab-answer")).toHaveAttribute(
      "lang",
      "zh-CN",
    );
    await expect(page.getByTestId("lab-run-locale")).toHaveText(
      tIn("en", "lab:bench.answer.runLocale", {
        language: tIn("en", "lab:language.zh-CN"),
      }),
    );
    // The untouched preset follows the new run language.
    await expect(page.getByTestId("lab-question-input")).toHaveValue(
      en.exercises[0].question,
    );
  });

  test("a lesson whose runner is still Chinese-only says so in the English UI", async ({
    page,
    request,
  }) => {
    const catalog: CurriculumData = await (
      await request.get("/api/curriculum?lang=en")
    ).json();
    const english: Detail[] = (
      await (await request.get("/api/lessons?lang=en")).json()
    ).lessons;
    const pending = english.find(
      (lesson) => lesson.available && lesson.runtime_locale !== "en",
    );
    test.skip(!pending, "每门课都已有英文运行时");
    await openLab(page, "en");
    // Open it through the course navigation, by its English titles.
    const lesson = catalog.lessons.find((item) => item.id === pending!.id)!;
    const category = catalog.categories.find(
      (item) => item.id === lesson.category_id,
    )!;
    const nav = page.getByTestId("course-nav");
    const toggle = nav
      .getByTestId("course-nav-category-toggle")
      .filter({ hasText: category.title });
    if ((await toggle.getAttribute("aria-expanded")) !== "true")
      await toggle.click();
    await nav
      .getByTestId("course-nav-lesson")
      .filter({ hasText: lesson.title })
      .click();
    await page.getByTestId("scene-tab-lab").click();
    await expect(page.getByTestId("lab-runtime-locale")).toHaveText(
      tIn("en", "lab:bench.composer.runtimeLocale", {
        language: tIn("en", "lab:language.zh-CN"),
      }),
    );
  });
});
