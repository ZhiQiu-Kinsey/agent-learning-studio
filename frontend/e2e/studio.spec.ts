import { test, expect } from "@playwright/test";
import type { CurriculumData } from "../src/types";
import { isRunCreation, mockRunStream, runOffline } from "./runs";

// 学生界面固定真实调用。自动化测试在网络边界改用后端测试适配器，
// 检查真实 Python 工具与网页行为，不消耗凭据、不产生不稳定的模型费用。
test.beforeEach(async ({ page }) => {
  // These regression cases exercise established lessons; first-visit onboarding has its own suite.
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

test("source is served from the lesson, and replay never sends another run", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  let runCount = 0;
  page.on("request", (req) => {
    if (isRunCreation(req)) runCount++;
  });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "工具选择", exact: true }),
  ).toBeVisible();
  await page.getByRole("tab", { name: "Python 源码" }).click();
  const detail = await (await request.get("/api/lessons/1")).json();
  await expect(page.locator(".learn-code-frame pre")).toHaveText(
    detail.sources[0].content,
  );
  await page.getByRole("tab", { name: "实验工作台", exact: true }).click();
  await page.getByRole("button", { name: "运行练习" }).click();
  await expect(page.locator(".answer-content")).toContainText("42");
  await expect(page.locator(".trace-status")).toHaveText("已完成");
  await expect(page.locator(".event-request")).toHaveCount(2);
  expect(
    await page
      .locator(".event-request")
      .first()
      .evaluate((el) => el.getBoundingClientRect().height),
  ).toBeGreaterThanOrEqual(64);
  await page.locator(".event-request").nth(1).click();
  await expect(page.locator(".event-detail pre")).toContainText("tool_call_id");
  await expect(page.locator(".event-detail pre")).toContainText("42");
  await page.getByRole("button", { name: "回到起点" }).click();
  await expect(page.locator(".event")).toHaveCount(0);
  await expect(page.locator(".answer-content")).toHaveCount(0);
  await page.getByRole("button", { name: "下一步", exact: true }).click();
  await expect(page.locator(".event")).toHaveCount(1);
  await page.getByRole("button", { name: "播放回放" }).click();
  await expect(page.locator(".answer-content")).toContainText("42", {
    timeout: 20_000,
  });
  const scrubber = page.getByRole("slider", { name: "回放进度" });
  await scrubber.focus();
  await scrubber.press("Home");
  await expect(scrubber).toHaveAttribute("aria-valuenow", "0");
  await expect(page.locator(".event")).toHaveCount(0);
  await expect(page.locator(".answer-content")).toHaveCount(0);
  await scrubber.press("End");
  await expect(page.locator(".answer-content")).toContainText("42");
  expect(runCount).toBe(1);
  expect(errors).toEqual([]);
});

test("dependent call receives the real time result, and the full trace can be exported", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: /依赖式多轮调用/ }).click();
  await page.getByRole("tab", { name: "实验工作台", exact: true }).click();
  await expect(page.getByRole("combobox", { name: "练习场景" })).toHaveText(
    "小时与分钟相加",
  );
  await page.getByRole("tab", { name: "实验工作台", exact: true }).click();
  await page.getByRole("button", { name: "运行练习" }).click();
  await expect(page.locator(".trace-status")).toHaveText("已完成");
  await expect(page.locator(".event-request")).toHaveCount(3);
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载本次运行记录" }).click();
  const download = await downloadPromise;
  const stream = await download.createReadStream();
  const chunks: Buffer[] = [];
  for await (const chunk of stream!) chunks.push(Buffer.from(chunk));
  const trace = JSON.parse(Buffer.concat(chunks).toString("utf8"));
  const time = trace.events.find(
    (e: any) => e.type === "tool_result" && e.data.name === "get_current_time",
  ).data.result.result;
  const addition = trace.events.find(
    (e: any) =>
      e.type === "tool_call" && e.data.function.name === "add_numbers",
  );
  expect(JSON.parse(addition.data.function.arguments)).toEqual({
    a: time.hour,
    b: time.minute,
  });
  expect(trace.run_id).toMatch(/^[0-9a-f]{32}$/);
  expect(trace.events.every((e: any) => e.schema_version === 2)).toBe(true);
});

test("an interrupted event stream resumes from the last received seq without duplicates or gaps", async ({
  page,
  request,
}) => {
  const fromSeq: (string | null)[] = [];
  let runId = "";
  await page.route(
    (url) => /^\/api\/runs\/[^/]+\/events$/.test(url.pathname),
    async (route) => {
      const url = new URL(route.request().url());
      fromSeq.push(url.searchParams.get("from_seq"));
      if (fromSeq.length > 1) return route.fallback();
      runId = url.pathname.split("/")[3];
      // 只转发真实事件流的前 3 条后断开，模拟网络中断。
      const frames = (await (await route.fetch()).text())
        .split("\n\n")
        .filter((frame) => frame.includes("data: "));
      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: frames.slice(0, 3).join("\n\n") + "\n\n",
      });
    },
  );
  await page.goto("/");
  await page.getByRole("tab", { name: "实验工作台", exact: true }).click();
  await page.getByRole("button", { name: "运行练习" }).click();
  await expect(page.locator(".trace-status")).toHaveText("已完成");
  await expect(page.locator(".answer-content")).toContainText("42");
  expect(fromSeq).toEqual(["1", "4"]);
  const stored = (await (await request.get(`/api/runs/${runId}/events`)).text())
    .split("\n")
    .filter((line) => line.startsWith("data: "))
    .map((line) => JSON.parse(line.slice(6)));
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载本次运行记录" }).click();
  const download = await downloadPromise;
  const chunks: Buffer[] = [];
  for await (const chunk of (await download.createReadStream())!)
    chunks.push(Buffer.from(chunk));
  const trace = JSON.parse(Buffer.concat(chunks).toString("utf8"));
  expect(trace.run_id).toBe(runId);
  expect(trace.events).toEqual(stored);
  expect(trace.events.map((e: any) => e.seq)).toEqual(
    stored.map((_: unknown, index: number) => index + 1),
  );
});

test("zero division returns an error result and live mode excludes fault injection presets", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: /错误处理与安全边界/ }).click();
  await page.getByRole("tab", { name: "实验工作台", exact: true }).click();
  await page.getByRole("combobox", { name: "练习场景" }).click();
  await page.getByRole("option", { name: "除数为零", exact: true }).click();
  await page.getByRole("tab", { name: "实验工作台", exact: true }).click();
  await page.getByRole("button", { name: "运行练习" }).click();
  await expect(page.locator(".trace-status")).toHaveText("已完成");
  await page.locator(".event-tool_result").click();
  await expect(page.locator(".event-detail pre")).toContainText('"ok": false');
  await expect(page.locator(".answer-content")).toContainText("0");
  await page.getByRole("tab", { name: "实验工作台", exact: true }).click();
  await page.getByRole("combobox", { name: "练习场景" }).click();
  await expect(
    page.getByRole("listbox", { name: "练习场景" }).getByRole("option"),
  ).toHaveCount(2);
  await expect(
    page.getByRole("option", { name: /未知工具|损坏参数|JSON/ }),
  ).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect(page.getByLabel("你的问题", { exact: true })).toBeEditable();
});

test("small screen opens course navigation and keeps content within viewport", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByRole("button", { name: "打开课程菜单" }).click();
  await page.getByRole("button", { name: /依赖式多轮调用/ }).click();
  await expect(
    page.getByRole("heading", { name: "依赖式多轮调用", exact: true }),
  ).toBeVisible();
  await page.getByRole("tab", { name: "实验工作台", exact: true }).click();
  await expect(page.getByRole("button", { name: "运行练习" })).toBeEnabled();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBeTruthy();
});

test("answers render Markdown without executing model-supplied HTML", async ({
  page,
}) => {
  const events = [
    {
      type: "answer",
      round: 1,
      timestamp: new Date().toISOString(),
      data: {
        content:
          '# 计算结果\n\n**42**\n\n```python\nprint(42)\n```\n\n<img src="x" onerror="window.agentInjected=true">\n<script>window.agentInjected=true</script>',
      },
    },
    {
      type: "done",
      round: null,
      timestamp: new Date().toISOString(),
      data: { status: "completed", duration_ms: 1 },
    },
  ];
  await mockRunStream(
    page,
    events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join(""),
  );
  await page.goto("/");
  await page.getByRole("tab", { name: "实验工作台", exact: true }).click();
  await page.getByRole("button", { name: "运行练习" }).click();
  await expect(page.locator(".answer-content strong")).toHaveText("42");
  await expect(page.locator(".answer-content code")).toContainText("print(42)");
  await expect(
    page.locator(".answer-content script, .answer-content img"),
  ).toHaveCount(0);
  expect(
    await page.evaluate(() => (window as any).agentInjected),
  ).toBeUndefined();
});

test("lesson self-check explains mistakes and can be reset without calling the model", async ({
  page,
  request,
}) => {
  let runs = 0;
  page.on("request", (req) => {
    if (isRunCreation(req)) runs++;
  });
  const lesson = await (await request.get("/api/lessons/1")).json();
  await page.goto("/");
  await page.getByRole("tab", { name: "课后自测" }).click();
  await expect(page.getByRole("radio", { checked: true })).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "检查答案", exact: true }),
  ).toBeDisabled();
  for (const [index, question] of lesson.learning.quiz.entries()) {
    const option = question.options.find((option: any) =>
      index === 0
        ? option.id !== question.correct_option
        : option.id === question.correct_option,
    );
    await page
      .getByRole("group", { name: question.prompt, exact: true })
      .getByRole("radio", { name: option.text, exact: true })
      .click();
    await expect(
      page.getByRole("radio", { name: option.text, exact: true }),
    ).toBeChecked();
  }
  await page.getByRole("button", { name: "检查答案", exact: true }).click();
  await expect(page.locator(".quiz-feedback")).toHaveCount(
    lesson.learning.quiz.length,
  );
  for (const [index, question] of lesson.learning.quiz.entries()) {
    await expect(page.locator(".quiz-feedback").nth(index)).toContainText(
      question.explanation,
    );
  }
  await page.getByRole("button", { name: "重新作答", exact: true }).click();
  await expect(page.getByRole("radio", { checked: true })).toHaveCount(0);
  await expect(page.locator(".quiz-feedback")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "检查答案", exact: true }),
  ).toBeDisabled();
  const firstQuestion = lesson.learning.quiz[0];
  const firstOption = page
    .getByRole("group", { name: firstQuestion.prompt, exact: true })
    .getByRole("radio", { name: firstQuestion.options[0].text, exact: true });
  await firstOption.focus();
  await page.keyboard.press("Space");
  await expect(firstOption).toBeChecked();
  await expect(page.getByRole("radio", { checked: true })).toHaveCount(1);
  expect(runs).toBe(0);
});

test("the complete curriculum groups real plans and only starts implemented lessons", async ({
  page,
  request,
}) => {
  const curriculum: CurriculumData = await (
    await request.get("/api/curriculum")
  ).json();
  let runs = 0;
  page.on("request", (req) => {
    if (isRunCreation(req)) runs++;
  });
  await page.goto("/");
  await page.getByRole("button", { name: "完整课程表", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "完整课程表", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".curriculum-category")).toHaveCount(
    curriculum.categories.length,
  );
  await expect(page.locator(".curriculum-module")).toHaveCount(
    curriculum.categories.reduce(
      (count, category) => count + category.modules.length,
      0,
    ),
  );
  await expect(page.locator(".curriculum-lesson")).toHaveCount(
    curriculum.lessons.length,
  );
  const planned = page
    .locator('.curriculum-lesson[data-status="planned"]')
    .first();
  await planned.locator(".curriculum-lesson-trigger").click();
  await expect(
    planned.getByRole("heading", { name: "实验计划" }),
  ).toBeVisible();
  await expect(planned.getByRole("button", { name: /开始第/ })).toHaveCount(0);
  await page.getByLabel("搜索课程", { exact: true }).fill("不存在的课程xyz");
  await expect(page.locator(".curriculum-lesson")).toHaveCount(0);
  await page.getByLabel("搜索课程", { exact: true }).fill("");
  await page.getByRole("switch", { name: "仅显示可运行课程" }).click();
  await expect(
    page.getByRole("switch", { name: "仅显示可运行课程" }),
  ).toBeChecked();
  await expect(page.locator(".curriculum-lesson")).toHaveCount(
    curriculum.lessons.filter((lesson) => lesson.status === "available").length,
  );
  await expect(
    page.locator('.curriculum-lesson[data-status="planned"]'),
  ).toHaveCount(0);
  const first = page.locator(".curriculum-lesson").first();
  await first.locator(".curriculum-lesson-trigger").click();
  await first.getByRole("button", { name: "开始第 1 课", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "工具选择", exact: true }),
  ).toBeVisible();
  expect(runs).toBe(0);
});

test("provider settings submit only the selected profile and never persist the key in the browser", async ({
  page,
}) => {
  let saved: any;
  await page.route("**/api/providers", (route) =>
    route.fulfill({
      json: {
        active_provider: "bailian",
        providers: [
          {
            id: "bailian",
            label: "百炼",
            model: "existing-model",
            api_key_configured: true,
            config_ready: true,
            base_url_configured: true,
            supports_custom_base_url: false,
            requires_api_key: true,
          },
          {
            id: "anthropic",
            label: "Anthropic",
            model: "",
            api_key_configured: false,
            config_ready: false,
            base_url_configured: false,
            supports_custom_base_url: true,
            requires_api_key: true,
          },
        ],
      },
    }),
  );
  await page.route("**/api/settings", async (route) => {
    saved = route.request().postDataJSON();
    await route.fulfill({ json: { api_key_configured: true } });
  });
  await page.goto("/");
  await page.getByTitle("配置模型连接", { exact: true }).click();
  await page.getByRole("combobox", { name: "服务商", exact: true }).click();
  await page.getByRole("option", { name: "Anthropic", exact: true }).click();
  await expect(page.getByLabel("模型 ID", { exact: true })).toHaveValue("");
  await page.getByLabel("模型 ID", { exact: true }).fill("test-model");
  await page
    .getByLabel("API Key（可选）", { exact: true })
    .fill("fixture-secret-never-persist");
  await page.getByRole("button", { name: "保存模型配置", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(saved).toEqual({
    provider_id: "anthropic",
    model: "test-model",
    api_key: "fixture-secret-never-persist",
  });
  const storage = await page.evaluate(() =>
    JSON.stringify({
      local: { ...localStorage },
      session: { ...sessionStorage },
    }),
  );
  expect(storage).not.toContain("fixture-secret-never-persist");
});

test("SDK events identify standardized data instead of claiming raw HTTP", async ({
  page,
}) => {
  const events = [
    {
      type: "run_start",
      data: {
        provider_id: "custom",
        provider_label: "SDK test",
        model: "test-model",
        trace_representation: "sdk_standardized",
      },
    },
    {
      type: "request",
      data: {
        representation: "sdk_standardized",
        body: {
          model: "test-model",
          messages: [{ role: "user", content: "hello" }],
        },
      },
    },
    {
      type: "response",
      data: {
        representation: "sdk_standardized",
        body: { choices: [{ message: { content: "hello" } }] },
        duration_ms: 1,
      },
    },
    { type: "answer", data: { content: "hello" } },
    { type: "done", data: { status: "completed", duration_ms: 1 } },
  ].map((e) => ({ ...e, round: 1, timestamp: new Date().toISOString() }));
  await mockRunStream(
    page,
    events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join(""),
  );
  await page.goto("/");
  await page.getByRole("tab", { name: "实验工作台", exact: true }).click();
  await page.getByRole("button", { name: "运行练习" }).click();
  await expect(page.locator(".event-request")).toContainText("标准化请求");
  await expect(page.locator(".event-response")).toContainText("标准化响应");
  await page.locator(".event-request").click();
  await expect(page.locator(".event-detail")).toContainText("HTTP");
  await expect(page.locator(".event-detail pre")).toContainText("test-model");
});

test("settings dialog traps keyboard focus and Escape restores the opener", async ({
  page,
}) => {
  await page.goto("/");
  const opener = page.getByTitle("配置模型连接", { exact: true });
  await opener.click();
  const dialog = page.getByRole("dialog", { name: "模型连接设置" });
  await expect(dialog).toBeVisible();
  await expect(
    page.getByRole("combobox", { name: "服务商", exact: true }),
  ).toBeEnabled();
  const first = dialog.getByRole("button", { name: "关闭连接设置" });
  await first.focus();
  await page.keyboard.press("Shift+Tab");
  const wrappedBack = await dialog.evaluate((element) =>
    element.contains(document.activeElement),
  );
  expect(wrappedBack).toBe(true);
  await expect(first).not.toBeFocused();
  await page.keyboard.press("Tab");
  await expect(first).toBeFocused();
  for (let index = 0; index < 10; index++) {
    await page.keyboard.press("Tab");
    expect(
      await dialog.evaluate((element) =>
        element.contains(document.activeElement),
      ),
    ).toBe(true);
  }
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(opener).toBeFocused();
});

test("course tabs support arrow keys, Home and End with matching content", async ({
  page,
}) => {
  await page.goto("/");
  const tabs = page.getByRole("tablist", { name: "课程学习内容" });
  const guide = tabs.getByRole("tab", { name: "课程导读", exact: true });
  const source = tabs.getByRole("tab", { name: "Python 源码", exact: true });
  const quiz = tabs.getByRole("tab", { name: "课后自测", exact: true });
  await guide.focus();
  await page.keyboard.press("ArrowRight");
  await expect(source).toBeFocused();
  await expect(source).toHaveAttribute("aria-selected", "true");
  await expect(page.locator(".learn-code-frame code")).toBeVisible();
  await page.keyboard.press("End");
  await expect(quiz).toBeFocused();
  await expect(quiz).toHaveAttribute("aria-selected", "true");
  await expect(page.locator(".quiz-pane")).toBeVisible();
  await page.keyboard.press("Home");
  await expect(guide).toBeFocused();
  await expect(guide).toHaveAttribute("aria-selected", "true");
  await expect(page.locator(".reading-document")).toBeVisible();
});

test("workspace modes preserve answers, inputs and run evidence without new requests", async ({
  page,
}) => {
  let runs = 0;
  page.on("request", (request) => {
    if (isRunCreation(request)) runs++;
  });
  await page.goto("/");
  await page.getByRole("tab", { name: "课后自测", exact: true }).click();
  const firstAnswer = page.getByRole("radio").first();
  await firstAnswer.click();
  await page.getByRole("tab", { name: "实验工作台", exact: true }).click();
  await page.getByRole("button", { name: "运行练习", exact: true }).click();
  await expect(page.locator(".answer-content")).toContainText("42");
  const question = await page
    .getByLabel("你的问题", { exact: true })
    .inputValue();
  const count = await page.locator(".event").count();
  await page.getByRole("tab", { name: "学习课程", exact: true }).click();
  await expect(firstAnswer).toHaveAttribute("aria-checked", "true");
  await page.getByRole("tab", { name: "实验工作台", exact: true }).click();
  await expect(page.getByLabel("你的问题", { exact: true })).toHaveValue(
    question,
  );
  await expect(page.locator(".event")).toHaveCount(count);
  await expect(page.locator(".answer-content")).toContainText("42");
  expect(runs).toBe(1);
});

test("React Bits learning navigation works by keyboard and metrics settle on real counts", async ({
  page,
}) => {
  await page.goto("/");
  const steps = page.getByRole("navigation", { name: "学习步骤导航" });
  const code = steps.getByRole("button", { name: /对照源码/ });
  await code.focus();
  await code.press("Enter");
  await expect(page.locator(".learn-code-frame code")).toBeVisible();
  await expect(code).toHaveAttribute("aria-current", "step");
  await steps.getByRole("button", { name: /运行与观察/ }).click();
  await expect(page.locator(".lab-workspace")).toBeVisible();
  await page.getByRole("combobox", { name: "练习场景" }).click();
  await expect(page.getByRole("option").first()).toBeVisible();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "运行练习", exact: true }).click();
  await expect(page.locator(".trace-status")).toHaveText("已完成");
  await expect(
    page.locator('.inspector-summary b [aria-hidden="true"]').nth(0),
  ).toHaveText("2");
  await expect(
    page.locator('.inspector-summary b [aria-hidden="true"]').nth(1),
  ).toHaveText("1");
});

test("new layouts use normal reading flow and side-by-side execution evidence", async ({
  page,
}) => {
  await page.goto("/");
  const reading = page.locator(".reading-document");
  await expect(reading).toBeVisible();
  await expect(page.locator(".learn-main")).toHaveCSS("max-height", "none");
  const header = page.locator(".reading-observations h3");
  await expect(header).toHaveCSS("margin-top", "0px");
  await expect(header).toHaveCSS("margin-bottom", "0px");
  await page.getByRole("tab", { name: "实验工作台", exact: true }).click();
  const list = await page.locator(".trace-list-pane").boundingBox();
  const detail = await page.locator(".event-detail").boundingBox();
  expect(detail!.x).toBeGreaterThanOrEqual(list!.x + list!.width - 1);
  expect(Math.abs(detail!.y - list!.y)).toBeLessThan(1);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBeTruthy();
  await page.getByRole("tab", { name: "学习课程", exact: true }).click();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBeTruthy();
});
