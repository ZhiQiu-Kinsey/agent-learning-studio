import { test, expect } from "@playwright/test";
import type { Detail } from "../src/types";
import { t } from "./i18n";

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() =>
    localStorage.setItem("agent-lab-entry", "lesson"),
  );
});

test("motion setting merges the OS preference with the learner's choice", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const detail: Detail = await (await request.get("/api/lessons/1")).json();
  const lessonHeading = page.getByRole("heading", {
    name: detail.title,
    exact: true,
  });
  const root = page.locator("html");
  const picker = page.getByRole("combobox", { name: t("motion.label") });
  // 课程页顶部的两个氛围画布（Aurora 与 DotGrid）。
  const ambient = page.getByTestId("lesson-masthead").locator("canvas");

  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.goto("/");
  await expect(root).toHaveAttribute("data-motion", "full");
  await expect(root).toHaveAttribute("data-motion-preference", "system");
  await expect(root).toHaveAttribute("lang", "zh-CN");
  await expect(lessonHeading).toBeVisible();

  // Following the system: OS reduce turns everything static and drops ambient canvases.
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(root).toHaveAttribute("data-motion", "static");
  await expect(ambient).toHaveCount(0);

  // An explicit learner choice wins and survives a reload (set before first paint).
  await picker.click();
  await page
    .getByRole("option", { name: t("motion.reduced"), exact: true })
    .click();
  await expect(root).toHaveAttribute("data-motion", "reduced");
  await page.reload();
  await expect(root).toHaveAttribute("data-motion", "reduced");
  await expect(picker).toHaveText(t("motion.reduced"));
  await expect(ambient).toHaveCount(0);
  await expect(lessonHeading).toBeVisible();

  await picker.click();
  await page
    .getByRole("option", { name: t("motion.static"), exact: true })
    .click();
  await expect(root).toHaveAttribute("data-motion", "static");
  const transition = await page
    .getByTestId("app-curriculum-button")
    .evaluate((element) => getComputedStyle(element).transitionDuration);
  expect(transition.split(",").every((value) => parseFloat(value) < 0.001)).toBe(
    true,
  );

  await picker.click();
  await page
    .getByRole("option", { name: t("motion.system"), exact: true })
    .click();
  await expect(root).toHaveAttribute("data-motion", "static");
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await expect(root).toHaveAttribute("data-motion", "full");
  expect(errors).toEqual([]);
});

test("only one WebGL effect runs and it stops when motion is reduced", async ({
  page,
  request,
}) => {
  const detail: Detail = await (await request.get("/api/lessons/1")).json();
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: detail.title, exact: true }),
  ).toBeVisible();
  const webglCanvases = () =>
    page.evaluate(
      () =>
        [...document.querySelectorAll("canvas")].filter((canvas) => {
          try {
            return !!(canvas.getContext("webgl2") ?? canvas.getContext("webgl"));
          } catch {
            return false;
          }
        }).length,
    );
  // getContext returns the existing context for WebGL canvases and null for 2D ones.
  await expect.poll(webglCanvases).toBeLessThanOrEqual(1);
  await page.getByRole("combobox", { name: t("motion.label") }).click();
  await page
    .getByRole("option", { name: t("motion.reduced"), exact: true })
    .click();
  await expect.poll(webglCanvases).toBe(0);
});
