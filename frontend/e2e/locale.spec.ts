import { test, expect, type Page } from "@playwright/test";
import type { Detail } from "../src/types";
import { t, tIn } from "./i18n";

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
