import { test, expect, type APIRequestContext, type Page } from "@playwright/test";
import { t } from "./i18n";
import { lessonView } from "../src/content/view";
import { selectEvents } from "../src/content/selector";
import { ownRunEvents } from "../src/content/traceHunt";
import type { Checkpoint, TraceHunt } from "../src/content/types.gen";
import type { CurriculumData, Detail, Trace } from "../src/types";
import { runOffline } from "./runs";

const progressOf = (page: Page) =>
  page.evaluate(() =>
    JSON.parse(localStorage.getItem("agent-lab-progress") ?? "null"),
  );

/** 读取服务端运行存储里这次运行的全部事件（与页面收到的是同一份）。 */
async function runEvents(request: APIRequestContext, runId: string) {
  const text = await (await request.get(`/api/runs/${runId}/events`)).text();
  return text
    .split("\n")
    .filter((line) => line.startsWith("data: "))
    .map((line) => JSON.parse(line.slice(6)) as Trace);
}

test.beforeEach(async ({ page }) => {
  await page.route("**/api/status", async (route) => {
    const response = await route.fetch();
    // The test ends right after a reload; a status request still in flight then
    // has its response disposed with the page. Nothing is waiting for it.
    const body = await response.json().catch(() => undefined);
    if (body === undefined) return;
    await route.fulfill({ response, json: { ...body, config_ready: true } });
  });
  await runOffline(page);
});

test("progress records only real local actions and survives a reload", async ({
  page,
  request,
}) => {
  await page.addInitScript(() =>
    localStorage.setItem("agent-lab-entry", "lesson"),
  );
  await page.goto("/");
  const detail = await (await request.get("/api/lessons/chat-request")).json();
  await expect
    .poll(async () => (await progressOf(page))?.lastLessonId)
    .toBe(detail.id);
  let lesson = (await progressOf(page)).lessons[detail.id];
  expect(lesson.scenes.understand).toBeTruthy();
  expect(lesson.runs.count).toBe(0);
  expect(lesson.quizzes).toEqual({});

  // A completed self-check stores the score and the confidence that were actually given.
  await page.getByTestId("scene-tab-check").click();
  const quizBlock = detail.learning.scenes.check.blocks.find(
    (block: { type: string }) => block.type === "quiz",
  );
  const questions = lessonView(detail.learning).quiz;
  for (const [index, question] of questions.entries()) {
    const group = page.getByRole("group", { name: question.prompt, exact: true });
    await group
      .getByRole("radiogroup", { name: t("quiz:confidence.region"), exact: true })
      .getByRole("radio", { name: t("quiz:confidence.high"), exact: true })
      .click();
    const option = question.options.find((item) =>
      index === 0 ? item.id !== question.correct : item.id === question.correct,
    )!;
    await group
      .getByRole("radio", { name: option.text, exact: true })
      .click();
  }
  await page
    .getByRole("button", { name: t("quiz:submit"), exact: true })
    .click();
  lesson = (await progressOf(page)).lessons[detail.id];
  expect(lesson.scenes.check).toBeTruthy();
  expect(lesson.quizzes[quizBlock.id]).toMatchObject({
    correct: questions.length - 1,
    total: questions.length,
    attempts: 1,
  });
  expect(lesson.quizzes[quizBlock.id].answers).toEqual(
    Object.fromEntries(
      questions.map((question, index) => [
        question.id,
        { correct: index !== 0, confidence: "high" },
      ]),
    ),
  );

  // One finished run counts once; replaying it does not count again.
  await page.getByTestId("scene-tab-lab").click();
  await page.getByTestId("lab-run-button").click();
  await expect
    .poll(async () => (await progressOf(page)).lessons[detail.id].runs.count)
    .toBe(1);
  lesson = (await progressOf(page)).lessons[detail.id];
  expect(lesson.scenes.lab).toBeTruthy();
  expect(lesson.runs.lastRunId).toMatch(/\S/);
  await page.getByTestId("lab-replay-rewind").click();
  // 等重新加载后的状态请求结束，避免测试收尾时拦截器仍在读取响应。
  await Promise.all([
    page.waitForResponse((response) => response.url().endsWith("/api/status")),
    page.reload(),
  ]);
  await expect(page.getByTestId("lesson-masthead")).toBeVisible();
  expect((await progressOf(page)).lessons[detail.id].runs.count).toBe(1);
});

test("trace hunt uses the learner's own run, and review shows exactly the local actions", async ({
  page,
  request,
}) => {
  await page.addInitScript(() =>
    localStorage.setItem("agent-lab-entry", "lesson"),
  );
  await page.goto("/");
  const detail: Detail = await (await request.get("/api/lessons/chat-request")).json();
  const curriculum: CurriculumData = await (
    await request.get("/api/curriculum")
  ).json();
  const hunt = detail.learning!.scenes.check!.blocks.find(
    (block): block is TraceHunt => block.type === "trace-hunt",
  )!;
  const checkpoint = detail.learning!.scenes.check!.blocks.find(
    (block): block is Checkpoint => block.type === "checkpoint",
  )!;

  // Nothing done yet: an empty review, and the hunt asks for a real run first.
  await page.getByTestId("scene-tab-review").click();
  await expect(page.getByTestId("review-empty")).toHaveText(
    t("lesson:review.empty"),
  );
  await page.getByTestId("scene-tab-check").click();
  const noRun = page.getByTestId("trace-hunt-no-run");
  await expect(noRun).toContainText(t("lesson:check.hunt.noRun"));
  await expect(page.getByTestId("trace-hunt-event")).toHaveCount(0);
  await noRun
    .getByRole("button", { name: t("lesson:check.hunt.goLab"), exact: true })
    .click();
  await expect(page.getByTestId("scene-tab-lab")).toHaveAttribute(
    "aria-selected",
    "true",
  );

  // Two real runs; the hunt lists the events of the latest one.
  for (const expected of [1, 2]) {
    await page.getByTestId("lab-run-button").click();
    await expect
      .poll(async () => (await progressOf(page))?.lessons[detail.id].runs.count)
      .toBe(expected);
  }
  const runId: string = (await progressOf(page)).lessons[detail.id].runs
    .lastRunId;
  const events = ownRunEvents(await runEvents(request, runId));
  const targets = selectEvents(hunt.target, events);
  expect(targets.length).toBeGreaterThan(0);
  const wrong = events.findIndex((_, index) => !targets.includes(index));

  await page.getByTestId("scene-tab-check").click();
  const items = page.getByTestId("trace-hunt-event");
  await expect(items).toHaveCount(events.length);
  const feedback = page.getByTestId("trace-hunt-feedback");
  await items.nth(wrong).getByRole("button").click();
  await expect(feedback).toHaveAttribute("data-correct", "false");
  await expect(feedback).toContainText(
    t("lesson:check.hunt.incorrect", { step: wrong + 1 }),
  );
  expect(
    (await progressOf(page)).lessons[detail.id].evidence[
      `trace-hunt:${hunt.id}`
    ],
  ).toBeUndefined();
  await items.nth(targets[0]).getByRole("button").click();
  await expect(feedback).toHaveAttribute("data-correct", "true");
  await expect(page.getByTestId("trace-hunt-explanation")).toContainText(
    hunt.explanation,
  );
  expect(
    (await progressOf(page)).lessons[detail.id].evidence[
      `trace-hunt:${hunt.id}`
    ],
  ).toMatchObject({ runId, seq: events[targets[0]].seq });

  // A self-reported checkpoint is stored, not scored.
  const firstItem = page
    .getByTestId("checkpoint-block")
    .getByRole("checkbox")
    .first();
  await firstItem.check();
  expect(
    Object.keys((await progressOf(page)).lessons[detail.id].checkpoints),
  ).toEqual([`${checkpoint.id}/${checkpoint.items[0].id}`]);

  // Review numbers equal what really happened on this device, also after a reload.
  const next = curriculum.lessons.find(
    (lesson) => lesson.number === detail.number + 1,
  )!;
  const expectReview = async () => {
    await page.getByTestId("scene-tab-review").click();
    await expect(page.getByTestId("review-empty")).toHaveCount(0);
    for (const [id, value] of [
      ["runs", 2],
      ["evidence", 1],
      ["checkpoints", 1],
      ["quiz", 0],
    ] as const) {
      const stat = page.getByTestId(`review-${id}`);
      await expect(stat).toHaveAttribute("data-value", String(value));
      await expect(stat.locator("dd > span")).toHaveText(String(value));
    }
    await expect(
      page.getByTestId("review-scenes").locator('[data-visited="true"]'),
    ).toHaveCount(4); // 理解（打开课程）、回顾、自检、实验；读码没有打开过
    const nextCard = page.getByTestId("review-next");
    await expect(nextCard).toContainText(next.title);
    for (const prerequisite of next.prerequisites)
      await expect(
        nextCard.locator(`[data-lesson="${prerequisite}"]`),
      ).toContainText(
        prerequisite === detail.id
          ? t("lesson:review.next.runs", { count: 2 })
          : t("lesson:review.next.noRuns"),
      );
  };
  await expectReview();
  await page.reload();
  await expectReview();
  await page.getByTestId("scene-tab-check").click();
  await expect(
    page.getByTestId("checkpoint-block").getByRole("checkbox").first(),
  ).toBeChecked();
  // After a reload the latest run is read back from the run store (same
  // question, no new model request): the hunt uses it again and keeps the record.
  await expect(page.getByTestId("trace-hunt-no-run")).toHaveCount(0);
  await expect(page.getByTestId("trace-hunt-event")).toHaveCount(events.length);
  await expect(page.getByTestId("trace-hunt")).toContainText(
    t("lesson:check.hunt.source", { run: runId.slice(0, 8) }),
  );
  await expect(page.getByTestId("trace-hunt-recorded")).toContainText(
    t("lesson:check.hunt.recorded", { run: runId.slice(0, 8) }),
  );
});

test("onboarding checkpoints are self-reported and persist locally", async ({
  page,
  request,
}) => {
  await page.addInitScript(() => localStorage.removeItem("agent-lab-entry"));
  await page.goto("/");
  await page.getByTestId("home-start-onboarding").click();
  const content = await (await request.get("/api/onboarding")).json();
  const first = page
    .getByTestId("onboarding-checks")
    .getByRole("checkbox")
    .first();
  await first.check();
  const stored = (await progressOf(page)).lessons.onboarding.checkpoints;
  const checkpoint = content.chapters[0].scenes.check.blocks[0].items[0].id;
  expect(Object.keys(stored)).toEqual([
    `${content.chapters[0].id}/${checkpoint}`,
  ]);
  await page.reload();
  await page.getByTestId("home-start-onboarding").click();
  await expect(
    page.getByTestId("onboarding-checks").getByRole("checkbox").first(),
  ).toBeChecked();
  await page
    .getByTestId("onboarding-checks")
    .getByRole("checkbox")
    .first()
    .uncheck();
  expect((await progressOf(page)).lessons.onboarding.checkpoints).toEqual({});
});
