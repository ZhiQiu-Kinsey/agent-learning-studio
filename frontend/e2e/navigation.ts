import { expect, type APIRequestContext, type Page } from "@playwright/test";
import type { CurriculumData } from "../src/types";
import { t } from "./i18n";

/** Picks an exercise with the question bar's `/` menu (the experiment arms pick it too). */
export async function chooseExercise(page: Page, id: string) {
  await page
    .getByRole("button", { name: t("lab:bench.composer.openCommands") })
    .click();
  await page
    .getByRole("listbox", { name: t("lab:bench.composer.commands") })
    .locator(`[data-key="${id}"]`)
    .click();
}

/** Opens a lesson through the course navigation, expanding its category first. */
export async function openLessonById(
  page: Page,
  request: APIRequestContext,
  id: string,
) {
  const catalog: CurriculumData = await (
    await request.get("/api/curriculum")
  ).json();
  const lesson = catalog.lessons.find(
    (item) => item.id === id || item.aliases?.includes(id),
  )!;
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
  await expect(
    page.getByRole("heading", { name: lesson.title, exact: true, level: 1 }),
  ).toBeVisible();
  return lesson;
}
