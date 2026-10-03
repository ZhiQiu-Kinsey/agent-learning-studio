import { test, expect } from "@playwright/test";
import type { Detail } from "../src/types";
import { runOffline } from "./runs";
import { t } from "./i18n";
import { openLessonById } from "./navigation";

// 导览在学习者自己的运行上逐步框出证据。测试在网络边界改用后端测试适配器，
// 不消耗模型调用；工具与事件仍由真实后端产生。
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
        config_ready: true,
        api_key_configured: true,
      },
    });
  });
  await runOffline(page);
});

async function runChatRequest(
  page: import("@playwright/test").Page,
  request: import("@playwright/test").APIRequestContext,
) {
  const detail: Detail = await (
    await request.get("/api/lessons/chat-request")
  ).json();
  const experiment = detail.learning!.scenes.lab!.experiments[0];
  await page.goto("/");
  await openLessonById(page, request, detail.id);
  await page.getByTestId("scene-tab-lab").click();
  await page.getByTestId("lab-run-button").click();
  await expect(page.getByTestId("guide-start")).toBeEnabled();
  return experiment;
}

test("the guide frames each step's evidence under a mask that ignores clicks", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const experiment = await runChatRequest(page, request);
  const total = experiment.guide.length;
  const card = page.getByTestId("tour-card");
  const position = card.getByTestId("tour-position");
  const sentence = (step: number) =>
    card
      .getByTestId("guide-narration")
      .getByLabel(experiment.guide[step].text, { exact: true });

  await page.getByTestId("guide-start").click();
  await expect(position).toHaveText(
    t("common:tour.position", { current: 1, total }),
  );
  await expect(sentence(0)).toBeAttached();

  // Step 2 points at request.messages: those lines are framed and on screen.
  await card.getByTestId("tour-next").click();
  await expect(position).toHaveText(
    t("common:tour.position", { current: 2, total }),
  );
  await expect(sentence(1)).toBeAttached();
  const field = page.locator("[data-evidence-mark]");
  await expect(field).toContainText('"messages"');
  await expect(field).toBeInViewport();
  await expect(card.getByTestId("guide-evidence")).toContainText(
    "data.body.messages",
  );
  await expect(card.getByTestId("tour-next")).toBeFocused();

  // The dimmed page does nothing on click; the guide stays where it was.
  await page.mouse.click(4, 300);
  await expect(position).toHaveText(
    t("common:tour.position", { current: 2, total }),
  );

  // A held key repeats; only the first press moves the guide.
  await page.keyboard.down("ArrowRight");
  await page.keyboard.down("ArrowRight");
  await page.keyboard.down("ArrowRight");
  await page.keyboard.up("ArrowRight");
  await expect(position).toHaveText(
    t("common:tour.position", { current: 3, total }),
  );
  await expect(field).toContainText('"content"');
  await page.keyboard.press("ArrowLeft");
  await expect(sentence(1)).toBeAttached();

  // Esc leaves; focus returns to the guide button and the evidence stays framed.
  await page.keyboard.press("Escape");
  await expect(card).toHaveCount(0);
  await expect(page.getByTestId("guide-start")).toBeFocused();
  await expect(field).toContainText('"messages"');
  expect(errors).toEqual([]);
});

test("finishing the guide is acknowledged and it can be taken again", async ({
  page,
  request,
}) => {
  const experiment = await runChatRequest(page, request);
  const total = experiment.guide.length;
  const card = page.getByTestId("tour-card");
  await page.getByTestId("guide-start").click();
  for (let step = 1; step < total; step++) {
    await card.getByTestId("tour-next").click();
    await expect(card.getByTestId("tour-position")).toHaveText(
      t("common:tour.position", { current: step + 1, total }),
    );
  }
  await expect(card.getByTestId("tour-next")).toHaveText(
    t("common:tour.finish"),
  );
  await card.getByTestId("tour-next").click();
  await expect(card).toHaveCount(0);
  await expect(page.getByTestId("guide-start")).toHaveText(
    t("lesson:lab.guide.again"),
  );
  await expect(page.getByTestId("guide-start")).toBeEnabled();
});

test("locating an observe point frames its field in the event inspector", async ({
  page,
  request,
}) => {
  const experiment = await runChatRequest(page, request);
  const answer = experiment.observe.findIndex((item) => item.id === "answer");
  await page
    .getByTestId("experiment-observe")
    .nth(answer)
    .getByRole("button")
    .click();
  const field = page.locator("[data-evidence-mark]");
  await expect(field).toContainText('"content"');
  await expect(field).toBeInViewport();

  // Locating scrolls once. Stepping the replay back onto the same event later
  // frames the field again but leaves the page where the learner scrolled it.
  // Let locate's smooth scroll finish before scrolling away.
  await expect
    .poll(async () => {
      const before = await page.evaluate(() => window.scrollY);
      await page.waitForTimeout(150);
      return before === (await page.evaluate(() => window.scrollY));
    })
    .toBe(true);
  await page.evaluate(() => window.scrollTo(0, 0));
  // Lab shortcuts listen on the page; take focus off the locate button first.
  await page.evaluate(() =>
    (document.activeElement as HTMLElement | null)?.blur(),
  );
  await page.keyboard.press("ArrowLeft");
  await page.keyboard.press("ArrowRight");
  await expect(field).toContainText('"content"');
  expect(await page.evaluate(() => window.scrollY)).toBe(0);
});
