import { test, expect, type Page } from "@playwright/test";
import type { CurriculumData, Lesson } from "../src/types";
import { isRunCreation, runOffline } from "./runs";
import { t } from "./i18n";

// ⌘K 命令面板与实验快捷键。回放只读已有事件，全程只允许一次创建运行的请求。
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() =>
    localStorage.setItem("agent-lab-entry", "lesson"),
  );
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
  await runOffline(page, (body) => expect(body.mode).toBe("live"));
});

const palette = (page: Page) => page.getByTestId("command-palette");
const lessonItem = (page: Page, id: string) =>
  palette(page).locator(
    `[data-testid="command-lesson"][data-lesson-id="${id}"]`,
  );

async function catalog(page: Page) {
  const lessons: { lessons: Lesson[] } = await (
    await page.request.get("/api/lessons")
  ).json();
  const curriculum: CurriculumData = await (
    await page.request.get("/api/curriculum")
  ).json();
  return {
    available: lessons.lessons.filter((lesson) => lesson.available),
    planned: curriculum.lessons.filter((lesson) => lesson.status === "planned"),
  };
}

test("⌘K opens the palette, finds lessons by slug, number or title and enters them", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const { available } = await catalog(page);
  const [first, second, third] = available;
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: first.title, exact: true, level: 1 }),
  ).toBeVisible();

  // Keyboard: Ctrl+K opens with focus in the search field, Esc closes.
  await page.keyboard.press("Control+K");
  await expect(palette(page)).toBeVisible();
  await expect(palette(page)).toHaveAttribute("role", "dialog");
  const input = page.getByTestId("command-input");
  await expect(input).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(palette(page)).toHaveCount(0);
  await page.keyboard.press("Meta+K");
  await expect(palette(page)).toBeVisible();
  await page.keyboard.press("Escape");

  // Toolbar button: focus returns to it after closing.
  const button = page.getByTestId("app-command-button");
  await button.click();
  await expect(input).toBeFocused();
  await input.fill(second.id);
  await expect(lessonItem(page, second.id)).toBeVisible();
  // 显示课号也能搜到（课号随目录顺序计算，不是 ID）。
  await input.fill(String(second.number).padStart(2, "0"));
  await expect(lessonItem(page, second.id)).toBeVisible();
  await input.fill(second.title);
  await expect(lessonItem(page, second.id)).toBeVisible();
  await expect(lessonItem(page, third.id)).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect(palette(page)).toHaveCount(0);
  await expect(button).toBeFocused();

  // Enter runs the highlighted lesson.
  await button.click();
  await input.fill(second.id);
  await page.keyboard.press("Enter");
  await expect(palette(page)).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: second.title, exact: true, level: 1 }),
  ).toBeVisible();
  await expect(button).toBeFocused();

  // Scenes of the current lesson.
  await page.keyboard.press("Control+K");
  await input.fill(t("lesson:scenes.code"));
  await palette(page).getByTestId("command-scene-code").click();
  await expect(page.getByTestId("scene-tab-code")).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await page.keyboard.press("Control+K");
  await palette(page).getByTestId("command-scene-lab").click();
  await expect(page.getByTestId("scene-tab-lab")).toHaveAttribute(
    "aria-selected",
    "true",
  );

  // Course map and back into a lesson.
  await page.keyboard.press("Control+K");
  await palette(page).getByTestId("command-map").click();
  await expect(page.getByTestId("lesson-masthead")).toBeHidden();
  await page.keyboard.press("Control+K");
  await input.fill(first.id);
  await lessonItem(page, first.id).click();
  await expect(
    page.getByRole("heading", { name: first.title, exact: true, level: 1 }),
  ).toBeVisible();

  // Onboarding chapter from the palette.
  await page.keyboard.press("Control+K");
  await palette(page).getByTestId("command-intro-0").click();
  await expect(page.getByTestId("onboarding-chapter")).toBeVisible();
  expect(errors).toEqual([]);
});

test("planned lessons are listed with a badge but cannot be entered", async ({
  page,
}) => {
  let runs = 0;
  page.on("request", (request) => {
    if (isRunCreation(request)) runs++;
  });
  const { available, planned } = await catalog(page);
  test.skip(!planned.length, "curriculum has no planned lessons");
  const lesson = planned[0];
  await page.goto("/");
  await expect(
    page.getByRole("heading", {
      name: available[0].title,
      exact: true,
      level: 1,
    }),
  ).toBeVisible();
  await page.keyboard.press("Control+K");
  await page.getByTestId("command-input").fill(lesson.id);
  const item = lessonItem(page, lesson.id);
  await expect(item).toBeVisible();
  await expect(item).toHaveAttribute("aria-disabled", "true");
  await expect(item).toHaveAttribute("data-status", "planned");
  await expect(item).toContainText(t("command:lesson.planned"));
  await page.keyboard.press("Enter");
  await item.click({ force: true });
  await expect(palette(page)).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("heading", {
      name: available[0].title,
      exact: true,
      level: 1,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: lesson.title, exact: true, level: 1 }),
  ).toHaveCount(0);
  expect(runs).toBe(0);
});

test("theme commands apply immediately", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("lesson-masthead")).toBeVisible();
  await page.keyboard.press("Control+K");
  await palette(page).getByTestId("command-theme-dark").click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.keyboard.press("Control+K");
  await palette(page).getByTestId("command-theme-light").click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  expect(
    await page.evaluate(() => localStorage.getItem("agent-lab-theme")),
  ).toBe("light");
  await page.keyboard.press("Control+K");
  await palette(page).getByTestId("command-settings").click();
  await expect(palette(page)).toHaveCount(0);
  await expect(page.getByRole("dialog")).toBeVisible();
});

test("lab shortcuts replay recorded events and never fire while typing", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  let runs = 0;
  page.on("request", (request) => {
    if (isRunCreation(request)) runs++;
  });
  await page.goto("/");
  await page.getByTestId("scene-tab-lab").click();
  await page.getByTestId("lab-run-button").click();
  await expect(page.getByTestId("lab-answer")).toContainText("42");
  const toolbar = page.getByTestId("lab-replay-toolbar");
  // Attribute selector: the slider stays queryable while a modal hides the page.
  const scrubber = toolbar.locator("[role='slider']");
  await expect(scrubber).toBeEnabled();
  const total = Number(await scrubber.getAttribute("aria-valuemax"));
  expect(total).toBeGreaterThan(3);
  const position = async () =>
    Number(await scrubber.getAttribute("aria-valuenow"));
  const blur = () =>
    page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
  await blur();

  // ← / → step one event.
  await page.keyboard.press("ArrowLeft");
  await expect(scrubber).toHaveAttribute("aria-valuenow", String(total - 1));
  await page.keyboard.press("ArrowLeft");
  await expect(scrubber).toHaveAttribute("aria-valuenow", String(total - 2));
  await page.keyboard.press("ArrowRight");
  await expect(scrubber).toHaveAttribute("aria-valuenow", String(total - 1));

  // Shift+← / → move by real time, at least one event.
  await page.keyboard.press("Shift+ArrowLeft");
  await expect.poll(position).toBeLessThan(total - 1);
  const back = await position();
  await page.keyboard.press("Shift+ArrowRight");
  await expect.poll(position).toBeGreaterThan(back);

  // [ / ] cycle uniform → 1× → 2×.
  const pacing = (key: string) =>
    toolbar.getByRole("radio", { name: t(`stage:replay.${key}`) });
  await expect(pacing("uniform")).toHaveAttribute("aria-checked", "true");
  await page.keyboard.press("]");
  await expect(pacing("real1")).toHaveAttribute("aria-checked", "true");
  await page.keyboard.press("]");
  await expect(pacing("real2")).toHaveAttribute("aria-checked", "true");
  await page.keyboard.press("]");
  await expect(pacing("uniform")).toHaveAttribute("aria-checked", "true");
  await page.keyboard.press("[");
  await expect(pacing("real2")).toHaveAttribute("aria-checked", "true");
  await page.keyboard.press("[");
  await page.keyboard.press("[");
  await expect(pacing("uniform")).toHaveAttribute("aria-checked", "true");

  // Space plays from the start and pauses.
  await page.getByTestId("lab-replay-rewind").click();
  await blur();
  await expect(scrubber).toHaveAttribute("aria-valuenow", "0");
  await page.keyboard.press("Space");
  await expect.poll(position).toBeGreaterThan(1);
  await page.keyboard.press("Space");
  const paused = await position();
  await page.waitForTimeout(1500);
  expect(await position()).toBe(paused);

  // Typing in the question field never triggers shortcuts.
  const question = page.getByTestId("lab-question-input");
  await question.click();
  await question.press("End");
  await page.keyboard.type(" []?");
  await page.keyboard.press("ArrowLeft");
  await page.keyboard.press("Shift+ArrowLeft");
  expect(await position()).toBe(paused);
  await expect(page.getByTestId("shortcut-help")).toHaveCount(0);
  await expect(pacing("uniform")).toHaveAttribute("aria-checked", "true");
  await expect(question).toHaveValue(/ \[\]\?$/);

  // ? opens the help overlay; Esc closes it and returns focus.
  await blur();
  await page.keyboard.press("?");
  const help = page.getByTestId("shortcut-help");
  await expect(help).toBeVisible();
  await expect(help).toHaveAttribute("role", "dialog");
  await expect(help.getByRole("row")).toHaveCount(9);
  expect(await help.evaluate((el) => el.contains(document.activeElement))).toBe(
    true,
  );
  // Keys inside the overlay do not move the replay.
  await page.keyboard.press("ArrowLeft");
  expect(await position()).toBe(paused);
  await page.keyboard.press("Escape");
  await expect(help).toHaveCount(0);
  const rewind = page.getByTestId("lab-replay-rewind");
  await rewind.focus();
  await page.keyboard.press("?");
  await expect(help).toBeVisible();
  await help.getByTestId("shortcut-help-close").click();
  await expect(help).toHaveCount(0);
  await expect(rewind).toBeFocused();

  // Download appears in the palette once a run exists.
  await page.keyboard.press("Control+K");
  await expect(palette(page).getByTestId("command-download")).toBeVisible();
  const download = page.waitForEvent("download");
  await palette(page).getByTestId("command-download").click();
  expect((await download).suggestedFilename()).toMatch(/^agent-lab-.+\.json$/);

  expect(runs).toBe(1);
  expect(errors).toEqual([]);
});

test("palette, toolbar button and shortcut help fit narrow screens", async ({
  page,
}) => {
  const fits = () =>
    page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1);
  const inside = async (testId: string, width: number) => {
    const box = await page.getByTestId(testId).boundingBox();
    return !!box && box.x >= 0 && box.x + box.width <= width;
  };

  // Narrow desktop: the icon-only button stays in the toolbar.
  await page.setViewportSize({ width: 1100, height: 900 });
  await page.goto("/");
  await expect(page.getByTestId("lesson-masthead")).toBeVisible();
  await expect.poll(fits).toBe(true);
  const button = page.getByTestId("app-command-button");
  await expect(button).toBeVisible();
  expect(await inside("app-command-button", 1100)).toBe(true);

  // Tablet and phone: the crowded toolbar drops the button; a keyboard still opens the palette.
  await page.setViewportSize({ width: 768, height: 1024 });
  await expect(button).toBeHidden();
  await expect.poll(fits).toBe(true);
  await page.setViewportSize({ width: 375, height: 812 });
  await expect(button).toBeHidden();
  await expect.poll(fits).toBe(true);
  await page.keyboard.press("Control+K");
  await expect(palette(page)).toBeVisible();
  await expect.poll(() => inside("command-palette", 375)).toBe(true);
  await expect.poll(fits).toBe(true);
  await page.keyboard.press("Escape");
  await expect(palette(page)).toHaveCount(0);
  // Without a keyboard, the course menu offers the palette instead.
  await page.getByTestId("app-open-course-menu").click();
  await page.getByRole("dialog").getByTestId("app-rail-command").click();
  await expect(palette(page)).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(palette(page)).toHaveCount(0);

  await page.getByTestId("scene-tab-lab").click();
  await expect(page.getByTestId("scene-lab")).toBeVisible();
  await page.evaluate(() =>
    (document.activeElement as HTMLElement | null)?.blur(),
  );
  await page.keyboard.press("?");
  await expect(page.getByTestId("shortcut-help")).toBeVisible();
  await expect.poll(() => inside("shortcut-help", 375)).toBe(true);
  await expect.poll(fits).toBe(true);
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("shortcut-help")).toHaveCount(0);
});
