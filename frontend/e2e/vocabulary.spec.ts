import { test, expect } from "@playwright/test";
import { openLessonById } from "./navigation";

test("lesson prose separates new, review and background terms and explains code names", async ({
  page,
  request,
}) => {
  await page.addInitScript(() =>
    localStorage.setItem("agent-lab-entry", "lesson"),
  );
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");

  // Lesson 4 introduces the task card; tool results come from lesson 1.
  await openLessonById(page, request, "task-contract");
  const reading = page.getByTestId("learn-reading-document");
  await expect(
    reading.locator("[data-testid='glossary-term'][data-term='task-card']"),
  ).toHaveAttribute("data-tier", "new");
  // The main text claims a term before a folded deep-dive does, so the mark
  // is visible without opening anything.
  await expect(
    reading
      .locator("[data-testid='glossary-term'][data-term='tool-result']")
      .first(),
  ).toHaveAttribute("data-tier", "review");

  // A field of the task card: shown as code, with the lesson's note on hover.
  const evidence = reading
    .getByTestId("code-note-trigger")
    .filter({ hasText: /^evidence$/ })
    .first();
  await evidence.scrollIntoViewIfNeeded();
  await evidence.hover();
  const card = page.getByTestId("code-note-card");
  await expect(card).toBeVisible();
  await expect(card).toContainText("evidence");

  // Context budget: sampling temperature was introduced by sampling-variance, so it is a review here.
  await openLessonById(page, request, "context-budget");
  await expect(
    page
      .getByTestId("learn-reading-document")
      .locator("[data-testid='glossary-term'][data-term='temperature']"),
  ).toHaveAttribute("data-tier", "review");

  // Replay is platform background knowledge, not a course concept.
  await openLessonById(page, request, "tool-selection");
  await expect(
    page
      .getByTestId("learn-reading-document")
      .locator("[data-testid='glossary-term'][data-term='replay']")
      .first(),
  ).toHaveAttribute("data-tier", "background");
  expect(errors).toEqual([]);
});
