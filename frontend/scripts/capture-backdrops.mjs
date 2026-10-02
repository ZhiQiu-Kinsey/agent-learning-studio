// Development helper: screenshots dev/backdrops.html two presets at a time (WebGL pool = 2).
import { chromium } from "@playwright/test";
const [base = "http://127.0.0.1:5190", out = "../.runtime/pages"] = process.argv.slice(2);
const names = (process.argv[4] ?? "threads,blinds,grainient,rays,galaxy,ripple,terminal,radar,web,aurora,veil,topography,orb").split(",");
const browser = await chromium.launch({ channel: "chrome", args: ["--enable-gpu", "--ignore-gpu-blocklist"] });
const page = await browser.newPage({ viewport: { width: 1200, height: 480 } });
page.on("console", (m) => m.type() === "error" && console.log("console:", m.text()));
page.on("pageerror", (e) => console.log("pageerror:", e.message));
for (let i = 0; i < names.length; i += 2) {
  const pair = names.slice(i, i + 2);
  await page.goto(`${base}/dev/backdrops.html?only=${pair.join(",")}`);
  await page.waitForTimeout(3500);
  await page.screenshot({ path: `${out}/backdrop-${pair.join("-")}.png` });
}
await browser.close();
console.log("done");
