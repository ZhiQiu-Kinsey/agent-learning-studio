import { test, expect } from "@playwright/test";
import { fileURLToPath } from "node:url";
const capture = (name: string) =>
  fileURLToPath(new URL(`../../.runtime/${name}`, import.meta.url));

test("themes persist, follow system changes, sync tabs and cover mobile screens", async ({
  page,
  context,
}) => {
  const errors: string[] = [];
  await page.addInitScript(() =>
    localStorage.setItem("agent-lab-entry", "lesson"),
  );
  page.on("pageerror", (error) => errors.push(error.message));
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/");
  const root = page.locator("html");
  const picker = page.getByRole("combobox", { name: "页面主题" });
  await expect(root).toHaveAttribute("data-theme", "light");
  await picker.click();
  await page.getByRole("option", { name: "深色", exact: true }).click();
  await expect(root).toHaveAttribute("data-theme", "dark");
  await page.reload();
  await expect(picker).toHaveText("深色");
  await expect(root).toHaveAttribute("data-theme", "dark");
  await expect(
    page.getByRole("heading", { name: "工具选择", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    animations: "disabled",
    path: capture("theme-dark.png"),
  });
  await page.getByRole("tab", { name: "Python 源码" }).click();
  await expect(page.locator(".learn-code-frame code")).toBeVisible();
  await page.screenshot({
    animations: "disabled",
    path: capture("theme-code.png"),
  });
  await page.getByRole("button", { name: "完整课程表", exact: true }).click();
  await expect(page.locator(".curriculum-category")).toHaveCount(8);
  await page.screenshot({
    animations: "disabled",
    path: capture("theme-curriculum.png"),
  });
  await page.getByTitle("配置模型连接", { exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  const inputColors = await page
    .getByLabel("模型 ID", { exact: true })
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
  await page.getByRole("button", { name: "关闭连接设置" }).click();
  await page.emulateMedia({ colorScheme: "dark" });
  await picker.click();
  await page.getByRole("option", { name: "浅色", exact: true }).click();
  await expect(root).toHaveAttribute("data-theme", "light");
  await picker.click();
  await page.getByRole("option", { name: "跟随系统", exact: true }).click();
  await expect(root).toHaveAttribute("data-theme", "dark");
  await page.emulateMedia({ colorScheme: "light" });
  await expect(root).toHaveAttribute("data-theme", "light");
  const second = await context.newPage();
  await second.goto("/");
  await second.getByRole("combobox", { name: "页面主题" }).click();
  await second.getByRole("option", { name: "深色", exact: true }).click();
  await expect(picker).toHaveText("深色");
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
}) => {
  await page.addInitScript(() =>
    localStorage.setItem("agent-lab-entry", "lesson"),
  );
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "工具选择", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".lesson-masthead")).toHaveCSS("opacity", "1");
  await page.getByRole("button", { name: "完整课程表", exact: true }).click();
  const heading = page.getByRole("heading", {
    name: "完整课程表",
    exact: true,
  });
  await expect(heading).toBeVisible();
  await expect(heading.locator("..").locator("..").locator("..")).toHaveCSS(
    "opacity",
    "1",
  );
  await expect(page.locator(".curriculum-category")).toHaveCount(8);
});

test("changing reduced motion immediately restores offscreen lesson text", async ({
  page,
}) => {
  await page.addInitScript(() =>
    localStorage.setItem("agent-lab-entry", "lesson"),
  );
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.goto("/");
  const sections = page.locator(".reading-section");
  await expect(sections.last()).toBeAttached();
  await expect(sections.last()).not.toBeInViewport();
  await expect(sections.last()).toHaveCSS("opacity", "0.65");

  // Changing the OS preference must finish already-mounted entrance effects,
  // including content the learner has not scrolled to yet.
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const section of await sections.all()) {
    await expect(section).toHaveCSS("opacity", "1");
    await expect(section).toHaveCSS("transform", "none");
  }
  await expect(page.locator(".lesson-hero")).not.toHaveClass(/is-animating/);
  await expect(page.locator(".rb-blur-text > span")).toHaveCount(0);
});
