import { test, expect } from "@playwright/test";
import { t } from "./i18n";

test("home shows a labelled illustration, the journey and a way back to the last lesson", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  const home = page.getByTestId("home-page");
  await expect(home).toBeVisible();

  // The illustration uses the real stage but is marked as not being a run record,
  // and it only moves when the learner steps it or presses play: never on load.
  const stage = home.getByTestId("agent-stage");
  await expect(stage).toHaveAttribute("data-provenance", "illustration");
  await expect(stage).toContainText(t("provenance.illustration"));
  const position = home.getByTestId("illustration-flow");
  const play = position.getByTestId("illustration-play");
  const before = await position.textContent();
  await page.waitForTimeout(1500);
  expect(await position.textContent()).toBe(before);
  await expect(play).toHaveAttribute("aria-pressed", "false");
  await position
    .getByRole("button", { name: t("blocks:flow.step"), exact: true })
    .click();
  expect(await position.textContent()).not.toBe(before);
  // Play advances on its own clock; a manual step pauses it again.
  const stepped = await position.textContent();
  await play.click();
  await expect(play).toHaveAttribute("aria-pressed", "true");
  await expect
    .poll(() => position.textContent(), { timeout: 4000 })
    .not.toBe(stepped);
  await position
    .getByRole("button", { name: t("blocks:flow.back"), exact: true })
    .click();
  await expect(play).toHaveAttribute("aria-pressed", "false");
  const paused = await position.textContent();
  await page.waitForTimeout(1600);
  expect(await position.textContent()).toBe(paused);

  // No local history yet: no "continue" button.
  await expect(page.getByTestId("home-continue")).toHaveCount(0);
  await page.getByTestId("home-first-lesson").click();
  const first = await (await request.get("/api/lessons/1")).json();
  await expect(page.getByTestId("lesson-badge")).toHaveText(
    String(first.number).padStart(2, "0"),
  );
  await page.getByTestId("app-home-button").click();
  await expect(page.getByTestId("home-continue")).toBeVisible();
  await page.getByTestId("home-continue").click();
  await expect(page.getByTestId("scene-understand")).toBeVisible();

  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByTestId("app-open-course-menu").click();
  await page.getByRole("dialog").getByTestId("app-home-button").click();
  await expect(page.getByTestId("home-page")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBe(true);
  expect(errors).toEqual([]);
});
