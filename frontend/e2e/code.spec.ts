import {
  test,
  expect,
  type APIRequestContext,
  type Page,
} from "@playwright/test";
import { fileURLToPath } from "node:url";
import type { Detail } from "../src/types";
import type { LessonCode } from "../src/scenes/code/model";
import { runOffline } from "./runs";
import { t } from "./i18n";
import { openLessonById } from "./navigation";

const capture = (name: string) =>
  fileURLToPath(new URL(`../../.runtime/${name}`, import.meta.url));

async function openCodeScene(
  page: Page,
  lesson?: { request: APIRequestContext; id: string },
) {
  await page.addInitScript(() =>
    localStorage.setItem("agent-lab-entry", "lesson"),
  );
  await page.goto("/");
  if (lesson) await openLessonById(page, lesson.request, lesson.id);
  await page.getByTestId("scene-tab-code").click();
  await expect(page.getByTestId("scene-code")).toBeVisible();
}

const box = async (page: Page, testId: string) =>
  (await page.getByTestId(testId).boundingBox())!;

test("reading code shows files, code and notes side by side, and what's new jumps to the real line", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  // 工具定义第一次出现在“工具定义与调用提议”：add_numbers 在这里算本课新增。
  const code: LessonCode = await (
    await request.get("/api/lessons/tool-proposals/code")
  ).json();
  const detail: Detail = await (await request.get("/api/lessons/tool-proposals")).json();
  await openCodeScene(page, { request, id: detail.id });

  // 三栏：文件列表、代码、批注在同一行从左到右排列。
  const files = await box(page, "code-files");
  const frame = await box(page, "learn-source-code");
  const notes = await box(page, "code-notes");
  expect(files.x + files.width).toBeLessThanOrEqual(frame.x);
  expect(frame.x + frame.width).toBeLessThanOrEqual(notes.x);
  expect(Math.abs(frame.y - notes.y)).toBeLessThan(2);
  await expect(page.getByTestId("code-file")).toHaveCount(
    detail.sources.length,
  );

  // “本课新增”只列新增与变化的符号，来自服务端 AST 计算。
  const items = page.getByTestId("code-whats-new-item");
  await expect(items).toHaveCount(
    code.whats_new.added.length + code.whats_new.changed.length,
  );
  const target = code.whats_new.added.find(
    (item) => item.name === "add_numbers",
  )!;
  await items.and(page.locator('[data-symbol="add_numbers"]')).click();
  const source = page.getByTestId("learn-source-code");
  await expect(source).toHaveAttribute("data-path", target.path);
  const line = source.locator(`[data-line="${target.start}"]`);
  await expect(line).toHaveAttribute("data-focused", "true");
  await expect(line).toBeInViewport();
  await expect(line).toContainText("def add_numbers");
  await expect(source.locator(`[data-line="${target.end}"]`)).toHaveAttribute(
    "data-focused",
    "true",
  );

  // 批注与所在行对齐，点击后定位到该行；被批注的行高亮。
  const fileNotes = code.annotations
    .filter((block) => block.path === target.path)
    .flatMap((block) => block.notes)
    .sort((a, b) => a.line - b.line);
  const noteButtons = page.getByTestId("code-note");
  await expect(noteButtons).toHaveCount(fileNotes.length);
  const first = fileNotes[0];
  const firstLine = source.locator(`[data-line="${first.line}"]`);
  await expect(firstLine).toHaveAttribute("data-annotated", "true");
  // 同一时刻读取两者位置（平滑滚动中分开读取会有偏差）。
  const offset = await page.evaluate((lineNumber) => {
    const note = document.querySelector('[data-testid="code-note"]')!;
    const row = document.querySelector(
      `[data-testid="learn-source-code"] [data-line="${lineNumber}"]`,
    )!;
    return note.getBoundingClientRect().top - row.getBoundingClientRect().top;
  }, first.line);
  expect(Math.abs(offset)).toBeLessThan(2);
  await expect(noteButtons.first()).toContainText(first.text);
  const last = fileNotes[fileNotes.length - 1];
  await noteButtons.last().click();
  await expect(noteButtons.last()).toHaveAttribute("aria-pressed", "true");
  await expect(source.locator(`[data-line="${last.line}"]`)).toBeInViewport();
  await expect(source.locator(`[data-line="${last.line}"]`)).toHaveAttribute(
    "data-active",
    "true",
  );

  // 工具函数旁的入口：还没有运行时如实说明，不伪造结果。
  const evidence = page
    .getByTestId("code-notes")
    .getByTestId("code-evidence")
    .and(page.locator('[data-tool="add_numbers"]'));
  await evidence.click();
  await expect(page.getByTestId("code-evidence-status")).toHaveText(
    t("lesson:code.evidence.noRun", { name: "add_numbers" }),
  );
  await expect(page.getByTestId("scene-tab-code")).toHaveAttribute(
    "aria-selected",
    "true",
  );

  // 设计决策在最后，提示词与工具定义仍然保留。
  await expect(page.getByTestId("code-decision")).toHaveCount(1);
  await expect(page.getByTestId("code-prompt")).toBeVisible();
  expect(
    await page.getByTestId("scene-code").evaluate((scene) => {
      const sections = [...scene.children].map((child) =>
        child.getAttribute("data-testid"),
      );
      return sections.at(-1);
    }),
  ).toBe("code-decisions");
  await page.screenshot({
    path: capture("code-scene-1440.png"),
    animations: "disabled",
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

test("a tool's evidence link opens its latest real tool_result in the lab", async ({
  page,
  request,
}) => {
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
  let runs = 0;
  await runOffline(page, () => runs++);
  await page.addInitScript(() =>
    localStorage.setItem("agent-lab-entry", "lesson"),
  );
  await page.goto("/");
  // 真正执行工具的是“执行工具与回传结果”。
  await openLessonById(page, request, "tool-selection");
  await page.getByTestId("scene-tab-lab").click();
  await page.getByTestId("lab-run-button").click();
  await expect(page.getByTestId("lab-answer")).toContainText("42");
  await expect(page.getByTestId("lab-run-button")).toBeEnabled();
  // 选中别的事件，确认入口会改选这次运行里最近的 tool_result。
  await page.getByTestId("lab-event-request").first().click();
  await page.getByTestId("scene-tab-code").click();
  await page
    .getByTestId("code-tools")
    .getByTestId("code-evidence")
    .and(page.locator('[data-tool="add_numbers"]'))
    .click();
  await expect(page.getByTestId("scene-tab-lab")).toHaveAttribute(
    "aria-selected",
    "true",
  );
  const detail = page.getByTestId("lab-event-detail").locator("pre");
  await expect(detail).toContainText("tool_call_id");
  await expect(detail).toContainText('"name": "add_numbers"');
  await expect(detail).toContainText("42");
  // 这次运行没有调用的工具：如实说明，不跳转。
  await page.getByTestId("scene-tab-code").click();
  await page
    .getByTestId("code-tools")
    .getByTestId("code-evidence")
    .and(page.locator('[data-tool="get_current_time"]'))
    .click();
  await expect(page.getByTestId("code-evidence-status")).toHaveText(
    t("lesson:code.evidence.notCalled", { name: "get_current_time" }),
  );
  expect(runs).toBe(1);
});

test("reading code collapses to one column on a phone without horizontal overflow", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 390, height: 844 });
  await openCodeScene(page);
  await page.getByTestId("code-file").nth(1).click();
  const files = await box(page, "code-files");
  const frame = await box(page, "learn-source-code");
  const notes = await box(page, "code-notes");
  expect(frame.y).toBeGreaterThanOrEqual(files.y + files.height - 1);
  expect(notes.y).toBeGreaterThanOrEqual(frame.y + frame.height - 1);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBe(true);
  // 窄屏上点击批注仍能定位到代码行（减少动画时立即跳转）。
  const note = page.getByTestId("code-note").first();
  const line = await note.getAttribute("data-line");
  await note.click();
  await expect(
    page.getByTestId("learn-source-code").locator(`[data-line="${line}"]`),
  ).toBeInViewport();
  await page.screenshot({
    path: capture("code-scene-390.png"),
    animations: "disabled",
    fullPage: true,
  });
});
