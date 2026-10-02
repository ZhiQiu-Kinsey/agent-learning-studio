import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { runOffline } from "./runs";

/** Fails on serious or critical WCAG A/AA violations; reports the rule ids. */
async function audit(page: Page, label: string) {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  const serious = result.violations
    .filter((item) => item.impact === "serious" || item.impact === "critical")
    .map((item) => `${label}: ${item.id} (${item.nodes.length}) ${item.nodes[0]?.target.join(" ")}`);
  expect(serious, serious.join("\n")).toEqual([]);
}

for (const theme of ["light", "dark"] as const) {
  test(`pages have no serious accessibility violations (${theme})`, async ({
    page,
  }) => {
    test.setTimeout(120_000);
    await page.addInitScript((value) => {
      localStorage.setItem("agent-lab-theme", value);
    }, theme);
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
    await page.emulateMedia({ reducedMotion: "reduce" });
    await runOffline(page);
    await page.goto("/");
    await expect(page.getByTestId("home-page")).toBeVisible();
    await audit(page, "home");

    await page.getByTestId("home-start-onboarding").click();
    await expect(page.getByTestId("onboarding-chapter")).toBeVisible();
    await audit(page, "onboarding");

    await page.getByTestId("app-curriculum-button").click();
    await expect(page.getByTestId("curriculum-map")).toBeVisible();
    await audit(page, "curriculum");

    await page.getByTestId("app-home-button").click();
    await page.getByTestId("home-first-lesson").click();
    for (const scene of ["understand", "code", "check", "review"]) {
      await page.getByTestId(`scene-tab-${scene}`).click();
      await expect(page.getByTestId(`scene-${scene}`)).toBeVisible();
      await audit(page, scene);
    }
    await page.getByTestId("scene-tab-lab").click();
    await page.getByTestId("lab-run-button").click();
    await expect(
      page.locator("[data-testid='agent-stage'][data-status='completed']"),
    ).toBeVisible();
    await audit(page, "lab");
  });
}
