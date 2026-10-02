// Development helper: screenshots the main pages (home, onboarding, map, lesson scenes).
// Usage: node scripts/capture-pages.mjs <baseURL> <outDir> [theme] [width]
import { chromium } from "@playwright/test";

const [base = "http://127.0.0.1:5190", out = "../.runtime/pages", theme = "dark", width = "1440"] =
  process.argv.slice(2);
const browser = await chromium.launch({ channel: "chrome", args: ["--use-angle=default"] });
const page = await browser.newPage({ viewport: { width: Number(width), height: 1000 } });
await page.addInitScript((value) => {
  localStorage.setItem("agent-lab-theme", value);
}, theme);
const shot = async (name, full = false) => {
  await page.waitForTimeout(1600);
  await page.screenshot({ path: `${out}/${name}-${theme}-${width}.png`, fullPage: full });
};
await page.goto(`${base}/`);
await page.getByTestId("home-page").waitFor();
await shot("home");
await shot("home-full", true);
await page.getByTestId("home-start-onboarding").click();
await page.getByTestId("onboarding-chapter").waitFor();
await shot("onboarding");
await page.getByTestId("app-curriculum-button").click();
await page.getByTestId("curriculum-map").waitFor();
await shot("curriculum");
await page.getByTestId("app-home-button").click();
await page.getByTestId("home-first-lesson").click();
for (const scene of ["understand", "code", "lab", "check", "review"]) {
  await page.getByTestId(`scene-tab-${scene}`).click();
  await shot(`lesson-${scene}`);
}
await browser.close();
console.log("captured");
