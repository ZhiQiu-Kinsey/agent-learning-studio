import { test, expect } from "@playwright/test";
import type { CurriculumData, Detail } from "../src/types";
import { isRunCreation, mockRunStream, runOffline } from "./runs";
import { t } from "./i18n";
import { chooseExercise, openLessonById } from "./navigation";
import { lessonView } from "../src/content/view";

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
  const detail: Detail = await (
    await request.get("/api/lessons/tool-selection")
  ).json();
  await page.goto("/");
  // 第一门课不带工具；加法、工具结果与两次请求在“执行工具与回传结果”里。
  await openLessonById(page, request, detail.id);
  await page.getByTestId("scene-tab-code").click();
  // 默认只显示标注范围；“显示完整文件”后与真实源码逐字一致。
  const sourceFrame = page.getByTestId("learn-source-code");
  await expect(sourceFrame.getByTestId("code-gap").first()).toBeVisible();
  await sourceFrame.getByTestId("code-show-all").click();
  const shownPath = await sourceFrame.getAttribute("data-path");
  await expect(sourceFrame.locator("pre")).toHaveText(
    detail.sources.find((item) => item.path === shownPath)!.content,
  );
  await page.getByTestId("scene-tab-lab").click();
  await page.getByTestId("lab-run-button").click();
  const answer = page.getByTestId("lab-answer");
  const events = page.getByTestId("lab-timeline").getByRole("button");
  const requests = page.getByTestId("lab-event-request");
  const eventJson = page.getByTestId("lab-event-detail").locator("pre");
  await expect(answer).toContainText("42");
  await expect(page.getByTestId("lab-trace-status")).toHaveText("已完成");
  await expect(requests).toHaveCount(2);
  expect(
    // Layout height: entrance animations scale rows briefly.
    await requests.first().evaluate((el) => (el as HTMLElement).offsetHeight),
  ).toBeGreaterThanOrEqual(64);
  await requests.nth(1).click();
  await expect(eventJson).toContainText("tool_call_id");
  await expect(eventJson).toContainText("42");
  await page.getByTestId("lab-replay-rewind").click();
  await expect(events).toHaveCount(0);
  await expect(answer).toHaveCount(0);
  await page.getByTestId("lab-replay-step").click();
  await expect(events).toHaveCount(1);
  await page.getByTestId("lab-replay-play").click();
  await expect(answer).toContainText("42", {
    timeout: 20_000,
  });
  const scrubber = page.getByTestId("lab-replay-toolbar").getByRole("slider");
  await scrubber.focus();
  await scrubber.press("Home");
  await expect(scrubber).toHaveAttribute("aria-valuenow", "0");
  await expect(events).toHaveCount(0);
  await expect(answer).toHaveCount(0);
  await scrubber.press("End");
  await expect(answer).toContainText("42");
  expect(runCount).toBe(1);
  expect(errors).toEqual([]);
});

test("dependent call receives the real time result, and the full trace can be exported", async ({
  page,
  request,
}) => {
  const detail: Detail = await (
    await request.get("/api/lessons/dependent-calls")
  ).json();
  await page.goto("/");
  await page
    .getByTestId("course-nav")
    .getByRole("button", { name: detail.title })
    .click();
  await page.getByTestId("scene-tab-lab").click();
  await expect(page.getByTestId("lab-question-input")).toHaveValue(
    detail.exercises.find((item) => !item.offline_only)!.question,
  );
  await page.getByTestId("scene-tab-lab").click();
  await page.getByTestId("lab-run-button").click();
  await expect(page.getByTestId("lab-trace-status")).toHaveText("已完成");
  await expect(page.getByTestId("lab-event-request")).toHaveCount(3);
  const downloadPromise = page.waitForEvent("download");
  await page.getByTestId("lab-download-trace").click();
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
  // 默认打开的是第一门课（不带工具）；这里要看工具调用的事件流，打开执行工具的课。
  await openLessonById(page, request, "tool-selection");
  await page.getByTestId("scene-tab-lab").click();
  await page.getByTestId("lab-run-button").click();
  await expect(page.getByTestId("lab-trace-status")).toHaveText("已完成");
  await expect(page.getByTestId("lab-answer")).toContainText("42");
  expect(fromSeq).toEqual(["1", "4"]);
  const stored = (await (await request.get(`/api/runs/${runId}/events`)).text())
    .split("\n")
    .filter((line) => line.startsWith("data: "))
    .map((line) => JSON.parse(line.slice(6)));
  const downloadPromise = page.waitForEvent("download");
  await page.getByTestId("lab-download-trace").click();
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

test("zero division returns an error result; fault injection runs locally without a model", async ({
  page,
  request,
}) => {
  const detail: Detail = await (
    await request.get("/api/lessons/fail-safely")
  ).json();
  const zero = detail.exercises.find((item) => item.id === "zero")!;
  const injected = detail.exercises.filter(
    (item) => item.requires_model === false,
  );
  expect(injected.map((item) => item.id)).toEqual(["unknown", "malformed"]);
  await page.goto("/");
  await page
    .getByTestId("course-nav")
    .getByRole("button", { name: detail.title })
    .click();
  await page.getByTestId("scene-tab-lab").click();
  await chooseExercise(page, zero.id);
  await page.getByTestId("lab-run-button").click();
  await expect(page.getByTestId("lab-trace-status")).toHaveText("已完成");
  await page.getByTestId("lab-event-tool-result").click();
  await expect(
    page.getByTestId("lab-event-detail").locator("pre"),
  ).toContainText('"ok": false');
  await expect(page.getByTestId("lab-answer")).toContainText("0");

  // The fault-injection experiment: the course program builds the faulty call,
  // the runner rejects it before any function runs, and no model is called.
  await page
    .getByRole("radio", { name: t("lesson:lab.experimentTab", { number: 2 }) })
    .click();
  for (const item of injected) {
    await page.getByTestId(`experiment-arm-${item.id}`).click();
    await expect(page.getByTestId("lab-composer-mode")).toHaveText(
      t("lab:bench.composer.modeLocal"),
    );
    await page.getByTestId("lab-run-button").click();
    await expect(page.getByTestId("lab-trace-status")).toHaveText(
      t("lab:bench.status.completed"),
    );
    await expect(page.getByTestId("stage-node-model")).toHaveCount(0);
    await expect(page.getByTestId("lab-event-request")).toHaveCount(0);
    await expect(
      page
        .getByTestId("lab-timeline")
        .getByRole("button")
        .filter({ hasText: t("lab:bench.event.programCall") }),
    ).toHaveCount(1);
    await page.getByTestId("lab-event-tool-result").click();
    await expect(
      page.getByTestId("lab-event-detail").locator("pre"),
    ).toContainText('"ok": false');
  }
});

test("small screen opens course navigation and keeps content within viewport", async ({
  page,
  request,
}) => {
  const detail: Detail = await (
    await request.get("/api/lessons/dependent-calls")
  ).json();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByTestId("app-open-course-menu").click();
  // 打开的抽屉是对话框，背后的侧栏对辅助技术隐藏。
  await page
    .getByRole("dialog")
    .getByTestId("course-nav")
    .getByRole("button", { name: detail.title })
    .click();
  await expect(
    page.getByRole("heading", { name: detail.title, exact: true }),
  ).toBeVisible();
  await page.getByTestId("scene-tab-lab").click();
  await expect(page.getByTestId("lab-run-button")).toBeEnabled();
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
  await page.getByTestId("scene-tab-lab").click();
  await page.getByTestId("lab-run-button").click();
  const answer = page.getByTestId("lab-answer");
  await expect(answer.locator("strong")).toHaveText("42");
  await expect(answer.locator("code")).toContainText("print(42)");
  await expect(answer.locator("script, img")).toHaveCount(0);
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
  const lesson = await (await request.get("/api/lessons/chat-request")).json();
  const submit = page.getByRole("button", {
    name: t("quiz:submit"),
    exact: true,
  });
  const feedback = page.getByTestId("quiz-feedback");
  const questions = lessonView(lesson.learning).quiz;
  const groupOf = (prompt: string) =>
    page.getByRole("group", { name: prompt, exact: true });
  // 每题两组单选：作答前的把握，以及题目选项（radiogroup 名称就是题干）。
  const confidenceOf = (prompt: string) =>
    groupOf(prompt).getByRole("radiogroup", {
      name: t("quiz:confidence.region"),
      exact: true,
    });
  const optionsOf = (prompt: string) =>
    groupOf(prompt).getByRole("radiogroup", { name: prompt, exact: true });
  await page.goto("/");
  await page.getByTestId("scene-tab-check").click();
  await expect(page.getByRole("radio", { checked: true })).toHaveCount(0);
  await expect(submit).toBeDisabled();
  const levels = ["low", "medium", "high"] as const;
  for (const [index, question] of questions.entries()) {
    const option = question.options.find((option: any) =>
      index === 0
        ? option.id !== question.correct
        : option.id === question.correct,
    );
    // 先评把握，选项才开放作答。
    await expect(
      optionsOf(question.prompt).getByRole("radio").first(),
    ).toBeDisabled();
    await confidenceOf(question.prompt)
      .getByRole("radio", {
        name: t(`quiz:confidence.${levels[index % 3]}`),
        exact: true,
      })
      .click();
    await optionsOf(question.prompt)
      .getByRole("radio", { name: option.text, exact: true })
      .click();
    await expect(
      page.getByRole("radio", { name: option.text, exact: true }),
    ).toBeChecked();
  }
  await submit.click();
  await expect(feedback).toHaveCount(questions.length);
  for (const [index, question] of questions.entries()) {
    const chosen =
      index === 0
        ? question.options.find((option) => option.id !== question.correct)!.id
        : question.correct;
    await expect(feedback.nth(index)).toContainText(question.explanation);
    await expect(feedback.nth(index)).toContainText(
      t("quiz:confidence.recorded", {
        level: t(`quiz:confidence.${levels[index % 3]}`),
      }),
    );
    // 选项级反馈：对的和错的选项都给出解释，并标明与学习者选择的关系。
    const items = feedback.nth(index).getByTestId("quiz-option-feedback");
    await expect(items).toHaveCount(question.options.length);
    for (const [optionIndex, option] of question.options.entries()) {
      const verdict =
        option.id === question.correct
          ? option.id === chosen
            ? "correct-chosen"
            : "correct-missed"
          : option.id === chosen
            ? "wrong-chosen"
            : "wrong-other";
      await expect(items.nth(optionIndex)).toHaveAttribute(
        "data-verdict",
        verdict,
      );
      await expect(items.nth(optionIndex)).toContainText(
        t(`quiz:verdict.${verdict}`),
      );
      expect(option.feedback).toBeTruthy();
      await expect(items.nth(optionIndex)).toContainText(option.feedback!);
    }
  }
  await page
    .getByRole("button", { name: t("quiz:reset"), exact: true })
    .click();
  await expect(page.getByRole("radio", { checked: true })).toHaveCount(0);
  await expect(feedback).toHaveCount(0);
  await expect(submit).toBeDisabled();
  const firstQuestion = questions[0];
  const firstOption = optionsOf(firstQuestion.prompt).getByRole("radio", {
    name: firstQuestion.options[0].text,
    exact: true,
  });
  await expect(firstOption).toBeDisabled();
  const firstConfidence = confidenceOf(firstQuestion.prompt).getByRole(
    "radio",
    { name: t("quiz:confidence.low"), exact: true },
  );
  await firstConfidence.focus();
  await page.keyboard.press("Space");
  await expect(firstConfidence).toBeChecked();
  await firstOption.focus();
  await page.keyboard.press("Space");
  await expect(firstOption).toBeChecked();
  await expect(
    optionsOf(firstQuestion.prompt).getByRole("radio", { checked: true }),
  ).toHaveCount(1);
  await expect(page.getByRole("radio", { checked: true })).toHaveCount(2);
  expect(runs).toBe(0);
});

test("the complete curriculum groups real plans and only starts implemented lessons", async ({
  page,
  request,
}) => {
  const curriculum: CurriculumData = await (
    await request.get("/api/curriculum")
  ).json();
  const firstLesson: Detail = await (
    await request.get("/api/lessons/chat-request")
  ).json();
  let runs = 0;
  page.on("request", (req) => {
    if (isRunCreation(req)) runs++;
  });
  const lessons = page.getByTestId("curriculum-lesson");
  const plannedLessons = lessons.and(page.locator('[data-status="planned"]'));
  const runnable = page.getByTestId("curriculum-controls").getByRole("switch");
  const search = page.getByTestId("curriculum-search-input");
  await page.goto("/");
  await page.getByTestId("app-curriculum-button").click();
  await expect(page.getByTestId("curriculum-title")).toBeVisible();
  await page.getByTestId("curriculum-view-list").click();
  await expect(page.getByTestId("curriculum-category-heading")).toHaveCount(
    curriculum.categories.length,
  );
  await expect(page.getByTestId("curriculum-module")).toHaveCount(
    curriculum.categories.reduce(
      (count, category) => count + category.modules.length,
      0,
    ),
  );
  await expect(lessons).toHaveCount(curriculum.lessons.length);
  const planned = plannedLessons.first();
  await planned.getByTestId("curriculum-lesson-trigger").click();
  await expect(
    planned.getByTestId("curriculum-lesson-experiments"),
  ).toBeVisible();
  await expect(planned.getByTestId("curriculum-lesson-start")).toHaveCount(0);
  await search.fill("不存在的课程xyz");
  await expect(lessons).toHaveCount(0);
  await search.fill("");
  await runnable.click();
  await expect(runnable).toBeChecked();
  await expect(lessons).toHaveCount(
    curriculum.lessons.filter((lesson) => lesson.status === "available").length,
  );
  await expect(plannedLessons).toHaveCount(0);
  const first = lessons.first();
  await first.getByTestId("curriculum-lesson-trigger").click();
  await first.getByTestId("curriculum-lesson-start").click();
  await expect(
    page.getByRole("heading", { name: firstLesson.title, exact: true }),
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
  const model = page.getByLabel(t("settings:model"), { exact: true });
  await page.goto("/");
  await page.getByTestId("app-connection-button").click();
  await page
    .getByRole("combobox", { name: t("settings:provider"), exact: true })
    .click();
  await page.getByRole("option", { name: "Anthropic", exact: true }).click();
  await expect(model).toHaveValue("");
  await model.fill("test-model");
  await page
    .getByLabel(t("settings:apiKey"), { exact: true })
    .fill("fixture-secret-never-persist");
  await page
    .getByRole("button", { name: t("settings:save"), exact: true })
    .click();
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
  await page.getByTestId("scene-tab-lab").click();
  await page.getByTestId("lab-run-button").click();
  // 事件标签仍硬编码在 Laboratory.tsx，抽取进 locales 后改为按键读取。
  await expect(page.getByTestId("lab-event-request")).toContainText(
    "标准化请求",
  );
  await expect(page.getByTestId("lab-event-response")).toContainText(
    "标准化响应",
  );
  await page.getByTestId("lab-event-request").click();
  const detail = page.getByTestId("lab-event-detail");
  await expect(detail).toContainText("HTTP");
  await expect(detail.locator("pre")).toContainText("test-model");
});

test("settings dialog traps keyboard focus and Escape restores the opener", async ({
  page,
}) => {
  await page.goto("/");
  const opener = page.getByTestId("app-connection-button");
  await opener.click();
  const dialog = page.getByRole("dialog", { name: t("settings:title") });
  await expect(dialog).toBeVisible();
  await expect(
    page.getByRole("combobox", { name: t("settings:provider"), exact: true }),
  ).toBeEnabled();
  const first = dialog.getByRole("button", { name: t("settings:close") });
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

test("lesson scenes support arrow keys, Home and End with matching content", async ({
  page,
}) => {
  await page.goto("/");
  const tabs = page.getByTestId("scene-tabs");
  const guide = tabs.getByTestId("scene-tab-understand");
  const source = tabs.getByTestId("scene-tab-code");
  const quiz = tabs.getByTestId("scene-tab-check");
  const review = tabs.getByTestId("scene-tab-review");
  await expect(tabs).toHaveRole("tablist");
  await guide.focus();
  await page.keyboard.press("ArrowRight");
  await expect(source).toBeFocused();
  await expect(source).toHaveAttribute("aria-selected", "true");
  await expect(
    page.getByTestId("learn-source-code").locator("code"),
  ).toBeVisible();
  await page.keyboard.press("End");
  await expect(review).toBeFocused();
  await expect(page.getByTestId("scene-review")).toBeVisible();
  await page.keyboard.press("ArrowLeft");
  await expect(quiz).toBeFocused();
  await expect(quiz).toHaveAttribute("aria-selected", "true");
  await expect(page.getByTestId("quiz-pane")).toBeVisible();
  await page.keyboard.press("Home");
  await expect(guide).toBeFocused();
  await expect(guide).toHaveAttribute("aria-selected", "true");
  await expect(page.getByTestId("learn-reading-document")).toBeVisible();
});

test("switching scenes preserves answers, inputs and run evidence without new requests", async ({
  page,
  request,
}) => {
  let runs = 0;
  page.on("request", (req) => {
    if (isRunCreation(req)) runs++;
  });
  await page.goto("/");
  await openLessonById(page, request, "tool-selection");
  await page.getByTestId("scene-tab-check").click();
  const firstAnswer = page.getByRole("radio").first();
  await firstAnswer.click();
  await page.getByTestId("scene-tab-lab").click();
  await page.getByTestId("lab-run-button").click();
  const answer = page.getByTestId("lab-answer");
  const events = page.getByTestId("lab-timeline").getByRole("button");
  const input = page.getByTestId("lab-question-input");
  await expect(answer).toContainText("42");
  const question = await input.inputValue();
  const count = await events.count();
  await page.getByTestId("scene-tab-understand").click();
  await page.getByTestId("scene-tab-check").click();
  await expect(firstAnswer).toHaveAttribute("aria-checked", "true");
  await page.getByTestId("scene-tab-lab").click();
  await expect(input).toHaveValue(question);
  await expect(events).toHaveCount(count);
  await expect(answer).toContainText("42");
  expect(runs).toBe(1);
});

test("understand scene leads into the lab by keyboard and metrics settle on real counts", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await openLessonById(page, request, "tool-selection");
  const start = page.getByTestId("understand-start-lab");
  await start.focus();
  await start.press("Enter");
  await expect(page.getByTestId("scene-tab-lab")).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(page.getByTestId("lab-workspace")).toBeVisible();
  await page
    .getByRole("button", { name: t("lab:bench.composer.openCommands") })
    .click();
  await expect(page.getByRole("option").first()).toBeVisible();
  await page.keyboard.press("Escape");
  await page.getByTestId("lab-run-button").click();
  await expect(page.getByTestId("lab-trace-status")).toHaveText("已完成");
  const metrics = page
    .getByTestId("lab-run-metrics")
    .locator('b [aria-hidden="true"]');
  // Counters animate when scrolled into view, as a learner would see them.
  await metrics.nth(0).scrollIntoViewIfNeeded();
  await expect(metrics.nth(0)).toHaveText("2");
  await expect(metrics.nth(1)).toHaveText("1");
});

test("new layouts use normal reading flow and side-by-side execution evidence", async ({
  page,
}) => {
  await page.goto("/");
  const reading = page.getByTestId("learn-reading-document");
  await expect(reading).toBeVisible();
  await expect(page.getByTestId("learn-main")).toHaveCSS("max-height", "none");
  const header = page.getByTestId("learn-observations").locator("h3");
  await expect(header).toHaveCSS("margin-top", "0px");
  await expect(header).toHaveCSS("margin-bottom", "0px");
  await page.getByTestId("scene-tab-lab").click();
  const list = await page.getByTestId("lab-trace-list").boundingBox();
  const detail = await page.getByTestId("lab-event-detail").boundingBox();
  expect(detail!.x).toBeGreaterThanOrEqual(list!.x + list!.width - 1);
  expect(Math.abs(detail!.y - list!.y)).toBeLessThan(1);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBeTruthy();
  await page.getByTestId("scene-tab-understand").click();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBeTruthy();
});
