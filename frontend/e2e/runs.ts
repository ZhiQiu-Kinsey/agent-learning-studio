import type { Page, Request } from "@playwright/test";

// 运行接口：POST /api/runs 创建运行，GET /api/runs/{id}/events 读取事件流。
const RUNS_PATH = "/api/runs";
const EVENTS_PATH = /^\/api\/runs\/[^/]+\/events$/;

/** 只统计创建运行的请求；读取事件、列表和回放都不算新运行。 */
export function isRunCreation(request: Request) {
  return (
    request.method() === "POST" && new URL(request.url()).pathname === RUNS_PATH
  );
}

/**
 * 学生界面固定真实调用；测试在网络边界把创建请求改为后端确定性测试模式，
 * 事件流仍由真实后端执行真实 Python 工具后返回。
 */
export async function runOffline(
  page: Page,
  onCreate?: (payload: Record<string, unknown>) => void,
) {
  await page.route(
    (url) => url.pathname === RUNS_PATH,
    async (route) => {
      if (route.request().method() !== "POST") return route.fallback();
      const payload = route.request().postDataJSON();
      onCreate?.(payload);
      const response = await route.fetch({
        postData: JSON.stringify({ ...payload, mode: "offline" }),
      });
      await route.fulfill({ response });
    },
  );
}

/** 用固定 SSE 文本模拟一次运行，用于检查界面对指定事件的呈现。 */
export async function mockRunStream(
  page: Page,
  body: string,
  onCreate?: (payload: Record<string, unknown>) => void,
) {
  await page.route(
    (url) => url.pathname === RUNS_PATH,
    async (route) => {
      if (route.request().method() !== "POST") return route.fallback();
      onCreate?.(route.request().postDataJSON());
      await route.fulfill({ status: 202, json: { run_id: "fixture-run" } });
    },
  );
  await page.route(
    (url) => EVENTS_PATH.test(url.pathname),
    (route) =>
      route.fulfill({ status: 200, contentType: "text/event-stream", body }),
  );
}
