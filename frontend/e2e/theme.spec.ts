import { test, expect } from "@playwright/test";
import { fileURLToPath } from "node:url";
import type { Detail } from "../src/types";
import { t } from "./i18n";
const capture = (name: string) =>
  fileURLToPath(new URL(`../../.runtime/${name}`, import.meta.url));

test("themes persist, follow system changes, sync tabs and cover mobile screens", async ({
  page,
  context,
  request,
}) => {
  const errors: string[] = [];
  await page.addInitScript(() =>
    localStorage.setItem("agent-lab-entry", "lesson"),
  );
  page.on("pageerror", (error) => errors.push(error.message));
  const detail: Detail = await (await request.get("/api/lessons/chat-request")).json();
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/");
  const root = page.locator("html");
  const picker = page.getByRole("combobox", { name: t("theme.label") });
  await expect(root).toHaveAttribute("data-theme", "light");
  await picker.click();
  await page
    .getByRole("option", { name: t("theme.dark"), exact: true })
    .click();
  await expect(root).toHaveAttribute("data-theme", "dark");
  await page.reload();
  await expect(picker).toHaveText(t("theme.dark"));
  await expect(root).toHaveAttribute("data-theme", "dark");
  await expect(
    page.getByRole("heading", { name: detail.title, exact: true }),
  ).toBeVisible();
  await page.screenshot({
    animations: "disabled",
    path: capture("theme-dark.png"),
  });
  await page.getByTestId("scene-tab-code").click();
  await expect(
    page.getByTestId("learn-source-code").locator("code"),
  ).toBeVisible();
  await page.screenshot({
    animations: "disabled",
    path: capture("theme-code.png"),
  });
  await page.getByTestId("app-curriculum-button").click();
  await page.getByTestId("curriculum-view-list").click();
  await expect(page.getByTestId("curriculum-category-heading")).toHaveCount(
    (await (await page.request.get("/api/curriculum")).json()).categories
      .length,
  );
  await page.screenshot({
    animations: "disabled",
    path: capture("theme-curriculum.png"),
  });
  await page.getByTestId("app-connection-button").click();
  await expect(page.getByRole("dialog")).toBeVisible();
  const inputColors = await page
    .getByLabel(t("settings:model"), { exact: true })
    .evaluate((element) => {
      const probe = document.createElement("span");
      probe.style.backgroundColor = "var(--surface)";
      document.body.append(probe);
      const expected = getComputedStyle(probe).backgroundColor;
      probe.remove();
      const style = getComputedStyle(element);
      const canvas = document.createElement("canvas");
      canvas.width = canvas.height = 1;
      const context = canvas.getContext("2d")!;
      const luminance = (color: string) => {
        context.fillStyle = color;
        context.fillRect(0, 0, 1, 1);
        const channels = [...context.getImageData(0, 0, 1, 1).data]
          .slice(0, 3)
          .map((channel) => {
            const value = channel / 255;
            return value <= 0.04045
              ? value / 12.92
              : ((value + 0.055) / 1.055) ** 2.4;
          });
        return (
          channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722
        );
      };
      const background = luminance(style.backgroundColor);
      const foreground = luminance(style.color);
      return {
        actual: style.backgroundColor,
        expected,
        foreground: style.color,
        contrast:
          (Math.max(background, foreground) + 0.05) /
          (Math.min(background, foreground) + 0.05),
      };
    });
  expect(inputColors.actual).toBe(inputColors.expected);
  expect(inputColors.actual).not.toBe("rgba(0, 0, 0, 0)");
  expect(inputColors.foreground).not.toBe(inputColors.actual);
  expect(inputColors.contrast).toBeGreaterThanOrEqual(4.5);
  await page.screenshot({
    animations: "disabled",
    path: capture("theme-settings.png"),
  });
  await page.getByRole("button", { name: t("settings:close") }).click();
  await page.emulateMedia({ colorScheme: "dark" });
  await picker.click();
  await page
    .getByRole("option", { name: t("theme.light"), exact: true })
    .click();
  await expect(root).toHaveAttribute("data-theme", "light");
  await picker.click();
  await page
    .getByRole("option", { name: t("theme.system"), exact: true })
    .click();
  await expect(root).toHaveAttribute("data-theme", "dark");
  await page.emulateMedia({ colorScheme: "light" });
  await expect(root).toHaveAttribute("data-theme", "light");
  const second = await context.newPage();
  await second.goto("/");
  await second.getByRole("combobox", { name: t("theme.label") }).click();
  await second
    .getByRole("option", { name: t("theme.dark"), exact: true })
    .click();
  await expect(picker).toHaveText(t("theme.dark"));
  await expect(root).toHaveAttribute("data-theme", "dark");
  await second.close();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(picker).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBeTruthy();
  await page.screenshot({
    animations: "disabled",
    path: capture("theme-mobile.png"),
  });
  expect(errors).toEqual([]);
});

test("reduced motion keeps learning and curriculum headings visible", async ({
  page,
  request,
}) => {
  await page.addInitScript(() =>
    localStorage.setItem("agent-lab-entry", "lesson"),
  );
  const detail: Detail = await (await request.get("/api/lessons/chat-request")).json();
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: detail.title, exact: true }),
  ).toBeVisible();
  await expect(page.getByTestId("lesson-masthead")).toHaveCSS("opacity", "1");
  await page.getByTestId("app-curriculum-button").click();
  const heading = page.getByTestId("curriculum-title");
  await expect(heading).toHaveRole("heading");
  await expect(heading).toBeVisible();
  await expect(page.getByTestId("curriculum-map")).toHaveCSS("opacity", "1");
  await expect(page.getByTestId("curriculum-domain-card")).toHaveCount(
    (await (await page.request.get("/api/curriculum")).json()).categories
      .length,
  );
  await page.getByTestId("curriculum-view-list").click();
  await expect(page.getByTestId("curriculum-category-heading")).toHaveCount(
    (await (await page.request.get("/api/curriculum")).json()).categories
      .length,
  );
});

test("changing reduced motion immediately restores offscreen lesson text", async ({
  page,
}) => {
  await page.addInitScript(() =>
    localStorage.setItem("agent-lab-entry", "lesson"),
  );
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.goto("/");
  const sections = page.getByTestId("learn-reading-section");
  await expect(sections.last()).toBeAttached();
  await expect(sections.last()).not.toBeInViewport();
  expect(
    Number(await sections.last().evaluate((node) => getComputedStyle(node).opacity)),
  ).toBeLessThan(1);

  // Changing the OS preference must finish already-mounted entrance effects,
  // including content the learner has not scrolled to yet.
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const section of await sections.all()) {
    await expect(section).toHaveCSS("opacity", "1");
    await expect(section).toHaveCSS("transform", "none");
  }
  // 课程标题的描边入场在静态动效下退回纯文本标题。
  await expect(
    page.getByTestId("lesson-masthead").getByRole("heading", { level: 1 }),
  ).not.toHaveAttribute("data-effect", /./);
  // 检查 BlurText 是否已停止逐词拆分的动画结构，属于动效断言，保留类名。
  await expect(page.locator(".rb-blur-text > span")).toHaveCount(0);
});
