import { test, expect, type Page, type Route } from "@playwright/test";
import { t } from "./i18n";
import { openLessonById } from "./navigation";

// 审批卡、流式文字与只读回放的界面呈现。事件流用固定 SSE 文本模拟（这些事件形状由
// tests/test_approvals.py、tests/test_streaming.py 对真实后端验证）；这里只检查界面怎样显示它们，
// 以及“批准”按钮提交的请求体。没有课程真的发出请求，也不调用模型。
const RUN_ID = "f".repeat(32);
const DIGEST = `sha256:${"a".repeat(64)}`;
let seq = 0;

function envelope(type: string, data: Record<string, unknown>, extra = {}) {
  seq += 1;
  return {
    schema_version: 2,
    run_id: RUN_ID,
    seq,
    type,
    round: 1,
    timestamp: new Date(Date.UTC(2026, 9, 20, 0, 0, seq)).toISOString(),
    span_id: "run-1",
    parent_span_id: null,
    span_kind: "run",
    actor: "agent",
    role: null,
    provenance: "real_run",
    representation: null,
    sdk: null,
    data,
    ...extra,
  };
}

const sse = (events: object[]) =>
  events
    .map(
      (event) =>
        `id: ${(event as { seq: number }).seq}\ndata: ${JSON.stringify(event)}\n\n`,
    )
    .join("");

test.beforeEach(async ({ page }) => {
  seq = 0;
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
  await page.route(
    (url) => url.pathname === "/api/runs",
    async (route) => {
      if (route.request().method() !== "POST") return route.fallback();
      await route.fulfill({ status: 202, json: { run_id: RUN_ID } });
    },
  );
});

async function openLab(
  page: Page,
  request: import("@playwright/test").APIRequestContext,
) {
  await page.goto("/");
  await openLessonById(page, request, "chat-request");
  await page.getByTestId("scene-tab-lab").click();
}

test("a pending approval can be approved once, then reads as a record", async ({
  page,
  request,
}) => {
  const start = envelope("run_start", {
    lesson_id: "chat-request",
    locale: "zh-CN",
  });
  const requested = envelope(
    "approval_requested",
    {
      approval_id: "approval-1",
      kind: "file.write",
      summary: "write notes/plan.md",
      payload: { path: "notes/plan.md", content: "draft" },
      payload_digest: DIGEST,
      editable: false,
      timeout_s: 300,
      expires_at: new Date(Date.now() + 300_000).toISOString(),
      risk: "high",
    },
    { span_id: "approval-1", span_kind: "approval" },
  );
  let decided: (body: Record<string, unknown>) => void = () => undefined;
  const decision = new Promise<Record<string, unknown>>(
    (resolve) => (decided = resolve),
  );
  await page.route(/\/api\/runs\/[0-9a-f]+\/approvals$/, async (route) => {
    decided(route.request().postDataJSON());
    await route.fulfill({ status: 200, json: { status: "accepted" } });
  });
  await page.route(/\/api\/runs\/[0-9a-f]+\/events/, async (route: Route) => {
    const from = Number(
      new URL(route.request().url()).searchParams.get("from_seq") ?? "1",
    );
    if (from <= 1)
      // No done yet: the page reconnects from the next seq, which waits for the decision.
      return route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: sse([start, requested]),
      });
    const body = await decision;
    const resolved = envelope(
      "approval_resolved",
      {
        approval_id: "approval-1",
        outcome: "approved",
        decided_by: "learner",
        note: body.note,
        payload_digest: DIGEST,
        requested_digest: DIGEST,
        edited: false,
        waited_ms: 1500,
      },
      { span_id: "approval-1", span_kind: "approval" },
    );
    const answer = envelope("answer", { content: "written notes/plan.md" });
    const done = envelope("done", { status: "completed", duration_ms: 2000 });
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: sse([resolved, answer, done]),
    });
  });
  await openLab(page, request);
  await page.getByTestId("lab-run-button").click();
  const card = page.getByTestId("lab-approval-card");
  await expect(card).toHaveAttribute("data-status", "pending");
  await expect(page.getByTestId("lab-trace-status")).toHaveText(
    t("lab:bench.status.awaitingApproval"),
  );
  await page.getByTestId("lab-approval-note").fill("path checked");
  await page.getByTestId("lab-approval-approve").click();
  expect(await decision).toEqual({
    approval_id: "approval-1",
    decision: "approve",
    payload_digest: DIGEST,
    note: "path checked",
  });
  await expect(card).toHaveAttribute("data-status", "approved");
  await expect(card.getByTestId("lab-approval-readonly")).toBeVisible();
  await expect(page.getByTestId("lab-approval-approve")).toHaveCount(0);
  await expect(page.getByTestId("lab-trace-status")).toHaveText(
    t("lab:bench.status.completed"),
  );
  // The record carries the learner's reason; nothing on the page can decide again.
  await expect(card).toContainText("path checked");
});

test("a stopped stream shows only the chunks that arrived, labelled as stopped", async ({
  page,
  request,
}) => {
  const chunk = (text: string) => ({
    choices: [{ index: 0, delta: { content: text }, finish_reason: null }],
  });
  const llm = {
    span_id: "llm-1",
    span_kind: "llm",
    representation: "http_body",
  };
  const events = [
    envelope("run_start", { lesson_id: "chat-request", locale: "zh-CN" }),
    envelope(
      "request",
      { stream: true, body: { stream: true }, representation: "http_body" },
      llm,
    ),
    envelope(
      "response_delta",
      {
        chunks: [chunk("Partial ")],
        chunk_range: [1, 1],
        text: "Partial ",
        received_ms: [180, 180],
      },
      llm,
    ),
    envelope(
      "response_delta",
      {
        chunks: [chunk("answer")],
        chunk_range: [2, 2],
        text: "answer",
        received_ms: [260, 260],
      },
      llm,
    ),
    envelope(
      "response",
      {
        body: {
          choices: [
            {
              index: 0,
              message: { role: "assistant", content: "Partial answer" },
              finish_reason: null,
            },
          ],
        },
        stream: {
          assembled_from_chunks: true,
          status: "cancelled",
          chunk_count: 2,
          first_chunk_ms: 180,
          first_token_ms: 180,
          cancel_reason: "user_stop",
          discarded_after_cancel: 0,
          done_marker: false,
        },
        representation: "http_body",
      },
      llm,
    ),
    envelope("done", {
      status: "cancelled",
      duration_ms: 400,
      cancel_reason: "user_stop",
    }),
  ];
  await page.route(/\/api\/runs\/[0-9a-f]+\/events/, (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: sse(events),
    }),
  );
  await openLab(page, request);
  await page.getByTestId("lab-run-button").click();
  const text = page.getByTestId("lab-stream-text");
  await expect(text).toHaveAttribute("data-status", "cancelled");
  await expect(text).toContainText("Partial answer");
  await expect(page.getByTestId("lab-event-response-delta")).toHaveCount(2);
});
