import { test, expect, type Page } from "@playwright/test";
import type { CurriculumData, Detail } from "../src/types";
import { isRunCreation, runOffline } from "./runs";
import { routePlannedLesson, withPlannedLesson } from "./catalog";

// 课程地图：领域卡片与先修路线图。进度标记只来自本机真实记录（打开、完成运行、自测）。
const progressOf = (page: Page) =>
  page.evaluate(() =>
    JSON.parse(localStorage.getItem("agent-lab-progress") ?? "null"),
  );

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
  await runOffline(page);
  await routePlannedLesson(page);
});

async function load(request: import("@playwright/test").APIRequestContext) {
  const catalog: CurriculumData = withPlannedLesson(
    await (await request.get("/api/curriculum")).json(),
  );
  const first: Detail = await (
    await request.get("/api/lessons/chat-request")
  ).json();
  return { catalog, first };
}

async function openMap(page: Page) {
  await page.getByTestId("app-curriculum-button").click();
  await expect(page.getByTestId("curriculum-title")).toBeVisible();
}

const lessonHeading = (page: Page, title: string) =>
  page.getByRole("heading", { name: title, exact: true, level: 1 });

const byLesson = (id: string) => `[data-lesson-id="${id}"]`;

test("domain cards and roadmap show real counts, and a run mark appears only after a real run", async ({
  page,
  request,
}) => {
  const { catalog, first } = await load(request);
  let runs = 0;
  page.on("request", (req) => {
    if (isRunCreation(req)) runs++;
  });
  const firstLesson = catalog.lessons.find((lesson) => lesson.id === first.id)!;
  const planned = catalog.lessons.find(
    (lesson) => lesson.status === "planned",
  )!;
  await page.goto("/");
  await expect(lessonHeading(page, first.title)).toBeVisible();
  await openMap(page);

  // Domains: one MagicBento card per category with counts from the catalog.
  const cards = page.getByTestId("curriculum-domain-card");
  await expect(cards).toHaveCount(catalog.categories.length);
  for (const category of catalog.categories) {
    const lessons = catalog.lessons.filter(
      (lesson) => lesson.category_id === category.id,
    );
    const available = lessons.filter(
      (lesson) => lesson.status === "available",
    ).length;
    const card = cards.and(page.locator(`[data-category="${category.id}"]`));
    await expect(card).toHaveAttribute("data-available", String(available));
    await expect(card).toHaveAttribute(
      "data-planned",
      String(lessons.length - available),
    );
  }
  const homeDomain = cards
    .and(page.locator(`[data-category="${firstLesson.category_id}"]`))
    .getByTestId("curriculum-domain-progress");
  await expect(homeDomain).toHaveAttribute("data-opened", "1");
  await expect(homeDomain).toHaveAttribute("data-ran", "0");

  // Roadmap: every lesson is a node; available lessons are highlighted, planned ones are not runnable.
  await page.getByTestId("curriculum-view-roadmap").click();
  const nodes = page.getByTestId("roadmap-node");
  await expect(nodes).toHaveCount(catalog.lessons.length);
  await expect(
    nodes.and(page.locator('[data-status="available"]')),
  ).toHaveCount(
    catalog.lessons.filter((lesson) => lesson.status === "available").length,
  );
  const firstNode = nodes.and(page.locator(byLesson(first.id)));
  const firstMarks = firstNode.getByTestId("roadmap-node-progress");
  await expect(firstMarks).toHaveAttribute("data-opened", "true");
  await expect(firstMarks).toHaveAttribute("data-ran", "false");

  await page.getByRole("button", { name: /fit view/i }).click();
  await nodes.and(page.locator(byLesson(planned.id))).click();
  const detail = page.getByTestId("roadmap-detail");
  await expect(detail).toHaveAttribute("data-lesson-id", planned.id);
  await expect(detail.getByTestId("roadmap-detail-planned")).toBeVisible();
  await expect(detail.getByTestId("roadmap-detail-start")).toHaveCount(0);
  await expect(page.getByTestId("curriculum-title")).toBeVisible();

  // Clicking an available lesson opens it; one real (offline-adapter) run completes.
  await firstNode.click();
  await expect(lessonHeading(page, first.title)).toBeVisible();
  await page.getByTestId("scene-tab-lab").click();
  await page.getByTestId("lab-run-button").click();
  await expect
    .poll(async () => (await progressOf(page)).lessons[first.id].runs.count)
    .toBe(1);

  // The map remembers the roadmap view for this visit and now shows the run mark.
  await openMap(page);
  await expect(firstMarks).toHaveAttribute("data-ran", "true");
  await page.getByTestId("curriculum-view-domains").click();
  await expect(homeDomain).toHaveAttribute("data-ran", "1");
  expect(runs).toBe(1);
});

test("keyboard moves between roadmap lessons, Enter opens an available lesson only", async ({
  page,
  request,
}) => {
  const { catalog, first } = await load(request);
  let runs = 0;
  page.on("request", (req) => {
    if (isRunCreation(req)) runs++;
  });
  const next = catalog.lessons.find((lesson) => lesson.number === 2)!;
  const last = [...catalog.lessons].sort((a, b) => b.number - a.number)[0];
  await page.goto("/");
  await openMap(page);
  await page.getByTestId("curriculum-view-roadmap").click();
  const nodes = page.getByTestId("roadmap-node");
  await expect(nodes).toHaveCount(catalog.lessons.length);
  const focused = page.locator(":focus");
  const detail = page.getByTestId("roadmap-detail");

  // Only one node is in the tab order (roving tabindex).
  await expect(nodes.and(page.locator('[tabindex="0"]'))).toHaveCount(1);
  await nodes.and(page.locator(byLesson(first.id))).focus();
  await page.keyboard.press("End");
  await expect(focused).toHaveAttribute("data-lesson-id", last.id);
  await expect(detail).toHaveAttribute("data-lesson-id", last.id);
  if (last.status === "planned") {
    await page.keyboard.press("Enter");
    await expect(detail.getByTestId("roadmap-detail-planned")).toBeVisible();
    await expect(page.getByTestId("curriculum-title")).toBeVisible();
  }

  await page.keyboard.press("Home");
  await expect(focused).toHaveAttribute("data-lesson-id", first.id);
  await page.keyboard.press("ArrowRight");
  await expect(focused).toHaveAttribute("data-lesson-id", next.id);
  await page.keyboard.press("ArrowLeft");
  await expect(focused).toHaveAttribute("data-lesson-id", first.id);
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("Enter");
  await expect(lessonHeading(page, next.title)).toBeVisible();
  expect(runs).toBe(0);
});

test("on a phone-width screen the route becomes a list and nothing scrolls sideways", async ({
  page,
  request,
}) => {
  const { catalog, first } = await load(request);
  await page.goto("/");
  await openMap(page);
  await page.getByTestId("curriculum-view-roadmap").click();
  await expect(page.getByTestId("curriculum-roadmap")).toBeVisible();
  await page.setViewportSize({ width: 375, height: 812 });
  const list = page.getByTestId("curriculum-roadmap-list");
  await expect(list).toBeVisible();
  await expect(page.getByTestId("curriculum-roadmap")).toHaveCount(0);
  const items = list.getByTestId("roadmap-list-item");
  await expect(items).toHaveCount(catalog.lessons.length);
  await expect(
    items
      .and(page.locator('[data-status="planned"]'))
      .first()
      .getByRole("button"),
  ).toHaveCount(0);
  // Polls: the view switch's pill springs into place and may overshoot for a
  // few frames; only a layout that keeps scrolling sideways fails.
  const noSideways = () =>
    page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1);
  await expect.poll(noSideways).toBe(true);
  await page.getByTestId("curriculum-view-domains").click();
  await expect(page.getByTestId("curriculum-domain-card")).toHaveCount(
    catalog.categories.length,
  );
  await expect.poll(noSideways).toBe(true);
  await page.getByTestId("curriculum-view-list").click();
  await expect(page.getByTestId("curriculum-category-heading")).toHaveCount(
    catalog.categories.length,
  );
  await expect.poll(noSideways).toBe(true);
  await page.getByTestId("curriculum-view-roadmap").click();
  await items
    .and(page.locator(byLesson(first.id)))
    .getByRole("button")
    .click();
  await expect(lessonHeading(page, first.title)).toBeVisible();
});

// Counts live WebGL contexts in the page: created minus lost, with the peak.
// Chrome force-loses the oldest context past its limit (~16) and logs a warning.
const countWebglContexts = () => {
  const stats = { created: 0, lost: 0, live: 0, peak: 0 };
  (window as unknown as { __webgl: typeof stats }).__webgl = stats;
  const original = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (
    this: HTMLCanvasElement,
    type: string,
    ...rest: unknown[]
  ) {
    const context = (original as (...args: unknown[]) => unknown).call(
      this,
      type,
      ...rest,
    );
    const canvas = this as HTMLCanvasElement & { __counted?: boolean };
    if (context && type.startsWith("webgl") && !canvas.__counted) {
      canvas.__counted = true;
      stats.created++;
      stats.live++;
      stats.peak = Math.max(stats.peak, stats.live);
      canvas.addEventListener("webglcontextlost", () => {
        stats.lost++;
        stats.live--;
      });
    }
    return context;
  } as typeof original;
};

test("every domain card shows its own live backdrop without hover, within the WebGL context limit", async ({
  page,
  request,
}) => {
  const { catalog } = await load(request);
  await page.addInitScript(countWebglContexts);
  const warnings: string[] = [];
  page.on("console", (message) => {
    if (/too many active webgl contexts|context lost/i.test(message.text()))
      warnings.push(message.text());
  });
  await page.goto("/");
  test.skip(
    !(await page.evaluate(() => {
      const gl = document.createElement("canvas").getContext("webgl");
      gl?.getExtension("WEBGL_lose_context")?.loseContext();
      return !!gl;
    })),
    "this browser has no WebGL",
  );
  await openMap(page);
  const windows = page.getByTestId("curriculum-domain-window");
  await expect(windows).toHaveCount(catalog.categories.length);
  await expect(
    windows.and(page.locator('[data-atmosphere="live"]')),
  ).toHaveCount(catalog.categories.length);
  // Each domain keeps its own preset (no shared resting texture).
  const presets = await windows
    .locator("[data-backdrop]")
    .evaluateAll((nodes) =>
      nodes.map((node) => node.getAttribute("data-backdrop")),
    );
  expect(new Set(presets).size).toBe(catalog.categories.length);

  // Scroll card by card without hovering: each window mounts its shader on its own.
  await page.mouse.move(0, 0);
  for (const tile of await windows.all()) {
    await tile.scrollIntoViewIfNeeded();
    await expect(tile.locator("canvas").first()).toBeAttached();
  }
  // Scroll back and forth: off-screen shaders release their contexts.
  for (let pass = 0; pass < 2; pass++) {
    await page.getByTestId("curriculum-title").scrollIntoViewIfNeeded();
    await windows.last().scrollIntoViewIfNeeded();
  }
  await expect(windows.last().locator("canvas").first()).toBeAttached();
  const stats = await page.evaluate(
    () =>
      (window as unknown as { __webgl: { live: number; peak: number } })
        .__webgl,
  );
  expect(stats.peak).toBeLessThanOrEqual(16);
  expect(warnings).toEqual([]);
});

test("with reduced motion the map is static and fully visible", async ({
  page,
  request,
}) => {
  const { catalog } = await load(request);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await openMap(page);
  const domains = page.getByTestId("curriculum-domains");
  await expect(domains).toHaveAttribute("data-animate", "false");
  const cards = page.getByTestId("curriculum-domain-card");
  await expect(cards).toHaveCount(catalog.categories.length);
  await cards.first().hover();
  await expect(domains).toHaveAttribute("data-animate", "false");
  // Static motion keeps the gradient windows: no shader, not even on hover.
  const windows = page.getByTestId("curriculum-domain-window");
  await expect(
    windows.and(page.locator('[data-atmosphere="still"]')),
  ).toHaveCount(catalog.categories.length);
  await expect(windows.locator("canvas")).toHaveCount(0);
  for (const card of await cards.all()) {
    await expect(card).toBeVisible();
    await expect(card).toHaveCSS("opacity", "1");
  }
  await page.getByTestId("curriculum-view-roadmap").click();
  const nodes = page.getByTestId("roadmap-node");
  await expect(nodes).toHaveCount(catalog.lessons.length);
  await expect(nodes.first()).toBeVisible();
});
