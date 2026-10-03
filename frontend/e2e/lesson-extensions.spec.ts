import {
  expect,
  test,
  type APIRequestContext,
  type Page,
} from "@playwright/test";
import type { CurriculumData, Detail, Trace } from "../src/types";
import { mockRunStream, runOffline } from "./runs";
import { t, tPattern } from "./i18n";
import { chooseExercise } from "./navigation";

// Fixture courses exist only at the browser's API boundary, never in the catalog.
async function fixtureLesson(
  page: Page,
  request: APIRequestContext,
  changes: Partial<Detail> = {},
) {
  const source: Detail = await (await request.get("/api/lessons/tool-selection")).json();
  const lesson: Detail = {
    ...source,
    id: "44",
    title: "扩展契约测试课",
    capabilities: {
      requires_model: false,
      custom_runtime: true,
      supports_inputs: true,
    },
    ui: { lab: "structured-inputs" },
    input_defaults: { strategy: "default" },
    exercises: [
      {
        id: "custom",
        title: "自定义参数",
        question: "检查参数",
        inputs: { limit: 2 },
      },
      { id: "defaults", title: "课程默认参数", question: "检查默认值" },
      {
        id: "empty",
        title: "明确的空对象",
        question: "检查空输入",
        inputs: {},
      },
    ],
    ...changes,
  };
  await page.addInitScript(() =>
    localStorage.setItem("agent-lab-entry", "lesson"),
  );
  await page.route("**/api/status", (route) =>
    route.fulfill({
      json: { model: "", config_ready: false, api_key_configured: false },
    }),
  );
  await page.route("**/api/lessons", async (route) => {
    const response = await route.fetch();
    const catalog = await response.json();
    await route.fulfill({
      json: { ...catalog, lessons: [...catalog.lessons, lesson] },
    });
  });
  await page.route("**/api/curriculum", async (route) => {
    const response = await route.fetch();
    const data: CurriculumData = await response.json();
    const category = data.categories[0];
    const module = category.modules[0];
    module.lesson_ids.push(lesson.id);
    data.lessons.push({
      ...data.lessons[0],
      id: lesson.id,
      title: lesson.title,
      status: "available",
      category_id: category.id,
      module_id: module.id,
    });
    await route.fulfill({ json: data });
  });
  await page.route(`**/api/lessons/${lesson.id}`, (route) =>
    route.fulfill({ json: lesson }),
  );
  await page.goto("/");
  await page
    .getByTestId("course-nav")
    .getByRole("button", { name: lesson.title })
    .click();
  await expect(
    page.getByRole("heading", { name: lesson.title, exact: true }),
  ).toBeVisible();
  return lesson;
}

function stream(events: Pick<Trace, "type" | "data">[]) {
  return events
    .map(
      (event) =>
        `data: ${JSON.stringify({
          ...event,
          schema_version: 1,
          round: null,
          timestamp: new Date().toISOString(),
        })}\n\n`,
    )
    .join("");
}

test("reusable evidence reports render real checks and tables, select older reports and rewind", async ({
  page,
  request,
}) => {
  let runs = 0;
  const full = {
    title: "完整上下文",
    summary: "保留了来源",
    checks: [{ label: "证据可见", passed: true, detail: "资料包含目标事实" }],
    metrics: [{ label: "字符数", value: 120 }],
    table: { columns: ["策略", "结果"], rows: [["完整", "有依据"]] },
  };
  const windowed = {
    title: "窗口上下文",
    summary: "证据被截断",
    checks: [
      {
        label: "证据可见",
        passed: false,
        detail: "最近片段缺少目标事实",
      },
    ],
    metrics: [{ label: "字符数", value: 20 }],
  };
  await mockRunStream(
    page,
    stream([
      { type: "run_start", data: {} },
      { type: "lesson.report", data: full },
      { type: "lesson.report", data: windowed },
      { type: "answer", data: { content: "对照完成" } },
      { type: "done", data: { status: "completed" } },
    ]),
    () => runs++,
  );
  await fixtureLesson(page, request, {
    ui: { lab: "structured-inputs", inspector: "evidence-board" },
  });
  await page.getByTestId("scene-tab-lab").click();
  await page.getByTestId("lab-run-button").click();
  const board = page.getByRole("region", { name: t("lab:evidence.region") });
  await expect(
    board.getByRole("heading", { name: windowed.title }),
  ).toBeVisible();
  await expect(board.locator('[data-verdict="failed"]')).toContainText(
    windowed.checks[0].detail,
  );
  await board.getByRole("button", { name: full.title, exact: true }).click();
  await expect(board.locator('[data-verdict="passed"]')).toContainText(
    full.checks[0].detail,
  );
  await expect(
    board.getByRole("cell", { name: full.table.rows[0][1], exact: true }),
  ).toBeVisible();
  await expect(
    page.getByTestId("lab-event-detail").locator("pre"),
  ).toContainText(JSON.stringify(full.metrics[0].label));
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBe(true);
  await page.getByTestId("lab-replay-rewind").click();
  await expect(board).toContainText(t("lab:evidence.empty"));
  await expect(board.getByTestId("evidence-checks")).toHaveCount(0);
  expect(runs).toBe(1);
});

test("new lesson reuses structured inputs, local execution and arbitrary event replay without platform branches", async ({
  page,
  request,
}) => {
  const payloads: Record<string, unknown>[] = [];
  const snapshot = {
    title: "状态快照",
    summary: "参数已传入运行器",
    state: { counter: 7 },
  };
  await mockRunStream(
    page,
    stream([
      {
        type: "run_start",
        data: { provider_label: "本地 Python", model: "local-python" },
      },
      { type: "lesson.state_snapshot", data: snapshot },
      { type: "answer", data: { content: "已验证自定义输入" } },
      { type: "done", data: { status: "completed" } },
    ]),
    (payload) => payloads.push(payload),
  );
  const lesson = await fixtureLesson(page, request);
  await page.getByTestId("scene-tab-lab").click();
  const inputs = page.getByTestId("lab-inputs-json");
  const run = page.getByTestId("lab-run-button");
  const eventJson = page.getByTestId("lab-event-detail").locator("pre");
  await expect(inputs).toHaveValue(
    JSON.stringify({ strategy: "default", limit: 2 }, null, 2),
  );
  await expect(run).toBeEnabled();
  await expect(page.getByTestId("lab-configure-button")).toHaveCount(0);

  await inputs.fill('{"limit":');
  await expect(page.getByRole("alert")).toHaveText(
    t("errors:client.inputsSyntax"),
  );
  await expect(run).toBeDisabled();
  await inputs.fill("[]");
  await expect(page.getByRole("alert")).toHaveText(
    t("errors:client.inputsNotObject"),
  );
  expect(payloads).toHaveLength(0);

  await inputs.fill('{"limit":7,"nested":{"enabled":true},"items":[]}');
  await page.getByTestId("lab-question-input").fill("");
  await expect(run).toBeEnabled();
  await run.click();
  await expect(page.getByTestId("lab-trace-status")).toHaveText("已完成");
  // 自定义运行器不调用模型：舞台上没有模型节点。
  await expect(page.getByTestId("agent-stage")).toBeVisible();
  await expect(page.getByTestId("stage-node-model")).toHaveCount(0);
  expect(payloads[0]).toMatchObject({
    lesson_id: "44",
    question: "",
    exercise_id: "custom",
    inputs: { limit: 7, nested: { enabled: true }, items: [] },
  });
  const customEvent = page
    .getByTestId("lab-timeline")
    .getByRole("button")
    .filter({ hasText: snapshot.title });
  await expect(customEvent).toContainText(snapshot.summary);
  await customEvent.click();
  await expect(eventJson).toContainText('"counter": 7');
  await page.getByTestId("lab-replay-rewind").click();
  await expect(
    page.getByTestId("lab-timeline").getByRole("button"),
  ).toHaveCount(0);
  await page.getByTestId("lab-replay-step").click();
  await page.getByTestId("lab-replay-step").click();
  await expect(customEvent).toBeVisible();
  expect(payloads).toHaveLength(1);

  await chooseExercise(page, lesson.exercises[1].id);
  await expect(inputs).toHaveValue(
    JSON.stringify({ strategy: "default" }, null, 2),
  );
  await chooseExercise(page, lesson.exercises[2].id);
  await expect(inputs).toHaveValue(
    JSON.stringify({ strategy: "default" }, null, 2),
  );
  await inputs.fill("{}");
  await run.click();
  await expect(page.getByTestId("lab-trace-status")).toHaveText("已完成");
  expect(payloads[1].inputs).toEqual({});
});

test("unknown view keys including URLs and prototype names show the default views without importing server code", async ({
  page,
  request,
}) => {
  const external: string[] = [];
  page.on("request", (req) => {
    if (req.url().includes("unknown-extension.invalid"))
      external.push(req.url());
  });
  const unavailable = (slot: string) =>
    t("lab:extension.unavailable", { slot: t(`lab:extension.slot.${slot}`) });
  await fixtureLesson(page, request, {
    ui: {
      guide: "https://unknown-extension.invalid/guide.js",
      lab: "__proto__",
      inspector: "constructor",
    },
  });
  await expect(page.getByRole("alert")).toHaveText(unavailable("guide"));
  await expect(page.getByTestId("learn-reading-document")).toBeVisible();
  await page.getByTestId("scene-tab-lab").click();
  await expect(
    page.getByRole("alert").filter({ hasText: unavailable("lab") }),
  ).toBeVisible();
  await expect(
    page.getByRole("alert").filter({ hasText: unavailable("inspector") }),
  ).toBeVisible();
  await expect(page.getByTestId("lab-workspace")).toBeVisible();
  await expect(page.getByTestId("agent-stage")).toBeVisible();
  expect(external).toEqual([]);
});

for (const failure of ["load", "render"] as const) {
  test(`extension ${failure} failure keeps the platform inspector usable`, async ({
    page,
    request,
  }) => {
    await page.route("**/assets/ToolOutcomes-*.js", (route) =>
      failure === "load"
        ? route.fulfill({ status: 503, body: "fixture unavailable" })
        : route.fulfill({
            contentType: "text/javascript",
            body: "export default function BrokenView(){throw new Error('fixture rendering failed')}",
          }),
    );
    await fixtureLesson(page, request, { ui: { inspector: "tool-outcomes" } });
    await page.getByTestId("scene-tab-lab").click();
    await expect(page.getByRole("alert")).toHaveText(
      t("lab:extension.failed", { slot: t("lab:extension.slot.inspector") }),
    );
    await expect(page.getByTestId("agent-stage")).toBeVisible();
    await expect(page.getByTestId("lab-run-button")).toBeEnabled();
    await page.getByTestId("lab-tab-source").click();
    await expect(
      page.getByTestId("lab-source-panel").locator("code"),
    ).toBeVisible();
  });
}

test("lesson three custom inspector follows real tool outcomes, event selection and rewind", async ({
  page,
  request,
}) => {
  await page.addInitScript(() =>
    localStorage.setItem("agent-lab-entry", "lesson"),
  );
  await page.route("**/api/status", (route) =>
    route.fulfill({
      json: { model: "fixture", config_ready: true, api_key_configured: true },
    }),
  );
  const detail: Detail = await (await request.get("/api/lessons/fail-safely")).json();
  const zero = detail.exercises.find((item) => item.id === "zero")!;
  const passed = (n: number) => `${t("lab:toolOutcomes.passed")} ${n}`;
  const failed = (n: number) => `${t("lab:toolOutcomes.failed")} ${n}`;
  let runs = 0;
  await runOffline(page, () => runs++);
  await page.goto("/");
  await page
    .getByTestId("course-nav")
    .getByRole("button", { name: detail.title })
    .click();
  await page.getByTestId("scene-tab-lab").click();
  const inspector = page.getByRole("region", {
    name: t("lab:toolOutcomes.region"),
  });
  await expect(inspector).toContainText(passed(0));
  await page.getByTestId("lab-run-button").click();
  await expect(page.getByTestId("lab-trace-status")).toHaveText("已完成");
  await expect(inspector).toContainText(passed(1));
  await expect(inspector).toContainText(failed(0));
  await chooseExercise(page, zero.id);
  await page.getByTestId("lab-run-button").click();
  await expect(page.getByTestId("lab-trace-status")).toHaveText("已完成");
  await expect(inspector).toContainText(passed(0));
  await expect(inspector).toContainText(failed(1));
  await inspector
    .getByRole("button", { name: tPattern("lab:toolOutcomes.locate") })
    .click();
  await expect(
    page.getByTestId("lab-event-detail").locator("pre"),
  ).toContainText('"ok": false');
  await page.getByTestId("lab-replay-rewind").click();
  await expect(inspector).toContainText(failed(0));
  await expect(inspector.getByRole("button")).toHaveCount(0);
  expect(runs).toBe(2);
});
