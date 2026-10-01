import {
  expect,
  test,
  type APIRequestContext,
  type Page,
} from "@playwright/test";
import type { CurriculumData, Detail, Trace } from "../src/types";

// Fixture courses exist only at the browser's API boundary, never in the catalog.
async function fixtureLesson(
  page: Page,
  request: APIRequestContext,
  changes: Partial<Detail> = {},
) {
  const source: Detail = await (await request.get("/api/lessons/1")).json();
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
    .getByRole("navigation", { name: "课程列表" })
    .getByRole("button", { name: new RegExp(lesson.title) })
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
  await page.route("**/api/run", async (route) => {
    runs++;
    await route.fulfill({
      contentType: "text/event-stream",
      body: stream([
        { type: "run_start", data: {} },
        {
          type: "lesson.report",
          data: {
            title: "完整上下文",
            summary: "保留了来源",
            checks: [
              { label: "证据可见", passed: true, detail: "资料包含目标事实" },
            ],
            metrics: [{ label: "字符数", value: 120 }],
            table: { columns: ["策略", "结果"], rows: [["完整", "有依据"]] },
          },
        },
        {
          type: "lesson.report",
          data: {
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
          },
        },
        { type: "answer", data: { content: "对照完成" } },
        { type: "done", data: { status: "completed" } },
      ]),
    });
  });
  await fixtureLesson(page, request, {
    ui: { lab: "structured-inputs", inspector: "evidence-board" },
  });
  await page.getByRole("tab", { name: "实验工作台", exact: true }).click();
  await page.getByRole("button", { name: "运行练习", exact: true }).click();
  const board = page.getByRole("region", { name: "本课实验报告" });
  await expect(
    board.getByRole("heading", { name: "窗口上下文" }),
  ).toBeVisible();
  await expect(board.locator('[data-verdict="failed"]')).toContainText(
    "最近片段缺少目标事实",
  );
  await board.getByRole("button", { name: "完整上下文", exact: true }).click();
  await expect(board.locator('[data-verdict="passed"]')).toContainText(
    "资料包含目标事实",
  );
  await expect(
    board.getByRole("cell", { name: "有依据", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".event-detail pre")).toContainText('"字符数"');
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBe(true);
  await page.getByRole("button", { name: "回到起点" }).click();
  await expect(board).toContainText("运行一个练习");
  await expect(board.locator(".evidence-checks")).toHaveCount(0);
  expect(runs).toBe(1);
});

test("new lesson reuses structured inputs, local execution and arbitrary event replay without platform branches", async ({
  page,
  request,
}) => {
  const payloads: Record<string, unknown>[] = [];
  await page.route("**/api/run", async (route) => {
    payloads.push(route.request().postDataJSON());
    await route.fulfill({
      contentType: "text/event-stream",
      body: stream([
        {
          type: "run_start",
          data: { provider_label: "本地 Python", model: "local-python" },
        },
        {
          type: "lesson.state_snapshot",
          data: {
            title: "状态快照",
            summary: "参数已传入课程程序",
            state: { counter: 7 },
          },
        },
        { type: "answer", data: { content: "已验证自定义输入" } },
        { type: "done", data: { status: "completed" } },
      ]),
    });
  });
  await fixtureLesson(page, request);
  await page.getByRole("tab", { name: "实验工作台", exact: true }).click();
  const inputs = page.getByLabel("实验参数 JSON", { exact: true });
  const run = page.getByRole("button", { name: "运行练习", exact: true });
  await expect(inputs).toHaveValue(
    JSON.stringify({ strategy: "default", limit: 2 }, null, 2),
  );
  await expect(run).toBeEnabled();
  await expect(
    page.getByRole("button", { name: "配置模型连接", exact: true }),
  ).toHaveCount(0);

  await inputs.fill('{"limit":');
  await expect(page.getByRole("alert")).toContainText("JSON 格式");
  await expect(run).toBeDisabled();
  await inputs.fill("[]");
  await expect(page.getByRole("alert")).toContainText("JSON 对象");
  expect(payloads).toHaveLength(0);

  await inputs.fill('{"limit":7,"nested":{"enabled":true},"items":[]}');
  await page.getByLabel("你的问题", { exact: true }).fill("");
  await expect(run).toBeEnabled();
  await run.click();
  await expect(page.locator(".trace-status")).toHaveText("已完成");
  await expect(
    page.getByRole("button", { name: "查看模型决策事件" }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "查看课程步骤事件" }).click();
  await expect(page.locator(".event-detail pre")).toContainText('"counter": 7');
  expect(payloads[0]).toMatchObject({
    lesson_id: "44",
    question: "",
    exercise_id: "custom",
    inputs: { limit: 7, nested: { enabled: true }, items: [] },
  });
  const customEvent = page.locator(".event").filter({ hasText: "状态快照" });
  await expect(customEvent).toContainText("参数已传入课程程序");
  await customEvent.click();
  await expect(page.locator(".event-detail pre")).toContainText('"counter": 7');
  await page.getByRole("button", { name: "回到起点" }).click();
  await expect(page.locator(".event")).toHaveCount(0);
  await page.getByRole("button", { name: "下一步", exact: true }).click();
  await page.getByRole("button", { name: "下一步", exact: true }).click();
  await expect(customEvent).toBeVisible();
  expect(payloads).toHaveLength(1);

  await page.getByRole("combobox", { name: "练习场景" }).click();
  await page.getByRole("option", { name: "课程默认参数", exact: true }).click();
  await expect(inputs).toHaveValue(
    JSON.stringify({ strategy: "default" }, null, 2),
  );
  await page.getByRole("combobox", { name: "练习场景" }).click();
  await page.getByRole("option", { name: "明确的空对象", exact: true }).click();
  await expect(inputs).toHaveValue(
    JSON.stringify({ strategy: "default" }, null, 2),
  );
  await inputs.fill("{}");
  await run.click();
  await expect(page.locator(".trace-status")).toHaveText("已完成");
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
  await fixtureLesson(page, request, {
    ui: {
      guide: "https://unknown-extension.invalid/guide.js",
      lab: "__proto__",
      inspector: "constructor",
    },
  });
  await expect(page.getByRole("alert")).toContainText(
    "课程导读的专属视图暂不可用",
  );
  await expect(page.locator(".reading-document")).toBeVisible();
  await page.getByRole("tab", { name: "实验工作台", exact: true }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "实验工作台" }),
  ).toBeVisible();
  await expect(
    page.getByRole("alert").filter({ hasText: "执行观察" }),
  ).toBeVisible();
  await expect(page.locator(".lab-workspace")).toBeVisible();
  await expect(page.locator(".execution-flow")).toBeVisible();
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
    await page.getByRole("tab", { name: "实验工作台", exact: true }).click();
    await expect(page.getByRole("alert")).toContainText(
      "执行观察的专属视图加载失败",
    );
    await expect(page.locator(".execution-flow")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "运行练习", exact: true }),
    ).toBeEnabled();
    await page.getByRole("tab", { name: "Python 源码", exact: true }).click();
    await expect(page.locator(".lab-source code")).toBeVisible();
  });
}

test("lesson three custom inspector follows real tool outcomes, event selection and rewind", async ({
  page,
}) => {
  await page.addInitScript(() =>
    localStorage.setItem("agent-lab-entry", "lesson"),
  );
  await page.route("**/api/status", (route) =>
    route.fulfill({
      json: { model: "fixture", config_ready: true, api_key_configured: true },
    }),
  );
  let runs = 0;
  await page.route("**/api/run", async (route) => {
    runs++;
    const response = await route.fetch({
      postData: {
        ...route.request().postDataJSON(),
        mode: "offline",
      },
    });
    await route.fulfill({ response });
  });
  await page.goto("/");
  await page.getByRole("button", { name: /错误处理与安全边界/ }).click();
  await page.getByRole("tab", { name: "实验工作台", exact: true }).click();
  const inspector = page.getByRole("region", { name: "工具安全边界观察" });
  await expect(inspector).toContainText("通过 0");
  await page.getByRole("button", { name: "运行练习", exact: true }).click();
  await expect(page.locator(".trace-status")).toHaveText("已完成");
  await expect(inspector).toContainText("通过 1");
  await expect(inspector).toContainText("失败 0");
  await page.getByRole("combobox", { name: "练习场景" }).click();
  await page.getByRole("option", { name: "除数为零", exact: true }).click();
  await page.getByRole("button", { name: "运行练习", exact: true }).click();
  await expect(page.locator(".trace-status")).toHaveText("已完成");
  await expect(inspector).toContainText("通过 0");
  await expect(inspector).toContainText("失败 1");
  await inspector.getByRole("button", { name: /定位工具结果/ }).click();
  await expect(page.locator(".event-detail pre")).toContainText('"ok": false');
  await page.getByRole("button", { name: "回到起点" }).click();
  await expect(inspector).toContainText("失败 0");
  await expect(inspector.getByRole("button")).toHaveCount(0);
  expect(runs).toBe(2);
});
