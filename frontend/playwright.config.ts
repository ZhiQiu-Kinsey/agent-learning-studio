import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  fullyParallel: false,
  workers: 1, // 本地服务有运行互斥；按顺序执行课程练习。
  reporter: 'list',
  use: {
    baseURL: process.env.AGENT_LAB_URL || 'http://127.0.0.1:8765',
    channel: 'chrome',
    headless: true,
    viewport: { width: 1440, height: 1000 },
    // 现有用例按 zh-CN 文案断言；英文界面的用例自己切换语言（e2e/locale.spec.ts）。
    locale: 'zh-CN',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
});
