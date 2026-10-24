import { test, expect, type Page } from "@playwright/test";
import type { Detail } from "../src/types";
import { isRunCreation, runOffline } from "./runs";
import { t } from "./i18n";
import { openLessonById } from "./navigation";

// 实验页的排布与跟随：左侧实验卡和证据核对、右侧运行观察台，运行时视角跟着走。
// 测试在网络边界改用后端测试适配器，不消耗模型调用；工具与事件仍由真实后端产生。
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

async function openDependentCalls(
  page: Page,
  request: import("@playwright/test").APIRequestContext,
) {
  const detail: Detail = await (
    await request.get("/api/lessons/dependent-calls")
  ).json();
  await page.goto("/");
  await openLessonById(page, request, detail.id);
  await page.getByTestId("scene-tab-lab").click();
  await scrollSettled(page);
  return detail;
}

/** Waits until the page has stopped scrolling (opening a scene scrolls to the top smoothly). */
async function scrollSettled(page: Page) {
  await page.evaluate(
    () =>
      new Promise<void>((resolve) => {
        let last = -1;
        let still = 0;
        const tick = () => {
          still = scrollY === last ? still + 1 : 0;
          last = scrollY;
          if (still > 5) resolve();
          else requestAnimationFrame(tick);
        };
        tick();
      }),
  );
}

const observe = (page: Page) => page.getByTestId("experiment-observe");
const experimentTab = (page: Page, number: number) =>
  page.getByRole("radio", {
    name: t("lesson:lab.experimentTab", { number }),
  });

test("switching experiments switches the arm and checks only that experiment's own run", async ({
  page,
  request,
}) => {
  const detail = await openDependentCalls(page, request);
  const [first, second] = detail.learning!.scenes.lab!.experiments;
  const exercise = (id: string) =>
    detail.exercises.find((item) => item.id === id)!;
  await page.getByTestId("lab-run-button").click();
  await expect(page.getByTestId("lab-trace-status")).toHaveText(
    t("lab:bench.status.completed"),
  );
  await expect(observe(page)).toHaveCount(first.observe.length);
  for (const point of await observe(page).all())
    await expect(point).toHaveAttribute("data-status", "found");

  await experimentTab(page, 2).click();
  await expect(
    page.getByTestId(`experiment-arm-${second.arms[0].id}`),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("lab-question-input")).toHaveValue(
    exercise(second.arms[0].exercise).question,
  );
  // The run on the stage belongs to experiment 1: experiment 2 has not run yet.
  await expect(observe(page)).toHaveCount(second.observe.length);
  for (const point of await observe(page).all())
    await expect(point).toHaveAttribute("data-status", "no-run");
  await expect(page.getByTestId("guide-start")).toBeDisabled();

  await experimentTab(page, 1).click();
  for (const point of await observe(page).all())
    await expect(point).toHaveAttribute("data-status", "found");
});

test("the view follows a run to the observatory and comes back when it ends", async ({
  page,
  request,
}) => {
  // Hold the event stream so the run lasts like a real model call.
  let release!: () => void;
  const held = new Promise<void>((resolve) => (release = resolve));
  await page.route(/\/api\/runs\/[^/]+\/events/, async (route) => {
    await held;
    await route.continue();
  });
  await openDependentCalls(page, request);
  // A late smooth scroll from opening the scene can still land; set until it holds.
  await expect
    .poll(() =>
      page.evaluate(() => {
        window.scrollTo(0, 120);
        return Math.round(scrollY);
      }),
    )
    .toBe(120);
  await page.getByTestId("lab-run-button").click();
  // Running: the observatory comes up under the toolbar, never back to the top.
  await expect
    .poll(() => page.evaluate(() => Math.round(scrollY)))
    .toBeGreaterThan(200);
  const observatory = page.locator("[data-run-focus]");
  await expect(observatory).toBeInViewport();
  release();
  await expect(page.getByTestId("lab-trace-status")).toHaveText(
    t("lab:bench.status.completed"),
  );
  // Finished: back where the run started.
  await expect
    .poll(() => page.evaluate(() => Math.round(scrollY)), { timeout: 8000 })
    .toBe(120);
});

test("scrolling by hand during a run keeps the page where the learner put it", async ({
  page,
  request,
}) => {
  let release!: () => void;
  const held = new Promise<void>((resolve) => (release = resolve));
  await page.route(/\/api\/runs\/[^/]+\/events/, async (route) => {
    await held;
    await route.continue();
  });
  await openDependentCalls(page, request);
  await page.getByTestId("lab-run-button").click();
  await expect
    .poll(() => page.evaluate(() => Math.round(scrollY)))
    .toBeGreaterThan(100);
  await page.mouse.move(900, 500);
  await page.mouse.wheel(0, 300);
  await page.waitForTimeout(300);
  const steered = await page.evaluate(() => Math.round(scrollY));
  release();
  await expect(page.getByTestId("lab-trace-status")).toHaveText(
    t("lab:bench.status.completed"),
  );
  await page.waitForTimeout(2500);
  expect(
    Math.abs((await page.evaluate(() => Math.round(scrollY))) - steered),
  ).toBeLessThan(40);
});

test("a finished run opens on the first observe point's evidence and the conclusion folds", async ({
  page,
  request,
}) => {
  const detail = await openDependentCalls(page, request);
  const experiment = detail.learning!.scenes.lab!.experiments[0];
  const conclusion = page.getByTestId("experiment-conclusion-toggle");
  await expect(conclusion).toHaveAttribute("aria-expanded", "false");
  await expect(conclusion).toContainText(
    t("lesson:lab.conclusion.summary", {
      proves: experiment.conclusion!.proves.length,
      limits: experiment.conclusion!.does_not_prove.length,
    }),
  );
  await page.getByTestId("lab-run-button").click();
  await expect(page.getByTestId("lab-trace-status")).toHaveText(
    t("lab:bench.status.completed"),
  );
  await expect(observe(page).first()).toHaveAttribute("data-current", "true");
  await expect(
    page.getByTestId("lab-event-detail").locator("[data-evidence-mark]"),
  ).toBeVisible();
  // Selecting the evidence does not rewind the replay: the answer stays.
  await expect(page.getByTestId("lab-answer")).toBeVisible();

  await conclusion.click();
  await expect(conclusion).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByTestId("experiment-conclusion")).toContainText(
    experiment.conclusion!.proves[0].slice(0, 12),
  );
  // Locating another point moves the highlight with the evidence.
  await observe(page)
    .nth(3)
    .getByRole("button", { name: new RegExp(t("lesson:lab.locate")) })
    .click();
  await expect(observe(page).nth(3)).toHaveAttribute("data-current", "true");
  await expect(observe(page).first()).not.toHaveAttribute("data-current");
  // The event list scrolls itself to the located event, also the last one.
  const last = observe(page).last();
  await last
    .getByRole("button", { name: new RegExp(t("lesson:lab.locate")) })
    .click();
  await expect(last).toHaveAttribute("data-current", "true");
  const list = page.getByTestId("lab-timeline");
  await expect
    .poll(() =>
      list.evaluate((box) => {
        const row = box.querySelector("[aria-pressed='true']");
        if (!row) return false;
        const outer = box.getBoundingClientRect();
        const inner = row.getBoundingClientRect();
        return inner.top >= outer.top - 1 && inner.bottom <= outer.bottom + 1;
      }),
    )
    .toBe(true);
});

test("a burst of events plays on the stage one step at a time", async ({
  page,
  request,
}) => {
  await openDependentCalls(page, request);
  await page.getByTestId("lab-run-button").click();
  // The offline run arrives at once; the run itself is already finished...
  await expect(page.getByTestId("lab-trace-status")).toHaveText(
    t("lab:bench.status.completed"),
  );
  // ...while the stage is still stepping through its last events.
  const stage = page.locator("[data-run-focus]").getByTestId("agent-stage");
  await expect(stage).toHaveAttribute("data-status", "running");
  await expect(stage).toHaveAttribute("data-status", "completed");
});

test("wide screens keep the experiment beside the observatory while it scrolls", async ({
  page,
  request,
}) => {
  await openDependentCalls(page, request);
  await page.getByTestId("lab-run-button").click();
  await expect(page.getByTestId("lab-trace-status")).toHaveText(
    t("lab:bench.status.completed"),
  );
  const panel = page.getByTestId("experiment-panel");
  const workspace = page.getByTestId("lab-workspace");
  const [panelBox, workspaceBox] = [
    await panel.boundingBox(),
    await workspace.boundingBox(),
  ];
  expect(panelBox!.x + panelBox!.width).toBeLessThanOrEqual(workspaceBox!.x);
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await expect(panel).toBeInViewport();
  await page.setViewportSize({ width: 390, height: 844 });
  // 改窗口宽度后布局要过一帧才切换，轮询到稳定状态再判断有没有横向溢出。
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    )
    .toBe(true);
});

test("coming back with the same question shows the last run without calling the model", async ({
  page,
  request,
}) => {
  const created: string[] = [];
  page.on("request", (req) => {
    if (isRunCreation(req)) created.push(req.url());
  });
  const status = page.getByTestId("lab-trace-status");
  const restored = page.getByTestId("lab-restored");
  await openDependentCalls(page, request);
  await page.getByTestId("lab-run-button").click();
  await expect(status).toHaveText(t("lab:bench.status.completed"));
  await expect(restored).toHaveCount(0);

  // Another lesson and back: the finished run is read back from the run store.
  await openLessonById(page, request, "chat-request");
  await openLessonById(page, request, "dependent-calls");
  await page.getByTestId("scene-tab-lab").click();
  await expect(restored).toBeVisible();
  await expect(status).toHaveText(t("lab:bench.status.completed"));
  for (const point of await observe(page).all())
    await expect(point).toHaveAttribute("data-status", "found");

  // A reload too: the browser keeps only the run id.
  await page.reload();
  await openLessonById(page, request, "dependent-calls");
  await page.getByTestId("scene-tab-lab").click();
  await expect(restored).toBeVisible();
  expect(created).toHaveLength(1);

  // A changed question no longer matches the run on screen.
  await page.getByTestId("lab-question-input").fill("What is 2 + 3?");
  await expect(restored).toHaveCount(0);
  // Running again really creates a run (the offline fixture has no answer
  // for this question, so only the request itself is checked).
  await page.getByTestId("lab-run-button").click();
  await expect.poll(() => created.length).toBe(2);
  await expect(page.getByTestId("lab-run-button")).toBeVisible();
});
