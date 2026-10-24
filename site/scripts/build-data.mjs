// Generates the site's build-time data from the repository, so the site never holds a
// hand-copied lesson list:
//   src/generated/curriculum.json   catalog.json + catalog.en.json → curriculum map
//   src/generated/recordings.json   index of lessons/*/recordings/*.json
//   public/data/recordings/...      the recordings themselves, copied unchanged
//   public/screenshots/<locale>/    screenshots from docs/assets/screenshots
// Runs before `dev`, `build` and `test` (see package.json).
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { buildCurriculum } from "./lib/curriculum.mjs";
import { groupRecordings, recordingEntry } from "./lib/recordings.mjs";

const site = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const root = path.resolve(site, "..");
const LOCALES = ["en"]; // overlay languages next to the zh-CN source
const SCREENSHOTS = ["home", "lesson-understand", "lesson-code", "lesson-lab", "curriculum"];

const readJson = (file) => JSON.parse(fs.readFileSync(file, "utf8"));
const overlaysNextTo = (file) =>
  Object.fromEntries(
    LOCALES.map((locale) => {
      const overlay = file.replace(/\.json$/, `.${locale}.json`);
      return [locale, fs.existsSync(overlay) ? readJson(overlay) : null];
    }),
  );
const writeJson = (file, value) => {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify(value, null, 2) + "\n");
};

const catalogFile = path.join(root, "curriculum", "catalog.json");
const catalog = readJson(catalogFile);
const curriculum = buildCurriculum(catalog, overlaysNextTo(catalogFile));
writeJson(path.join(site, "src", "generated", "curriculum.json"), curriculum);

// Lesson folders declare their slug in lesson.json; the folder name is not the slug.
const numbers = new Map(catalog.lessons.map((lesson, index) => [lesson.id, index + 1]));
const lessonsDir = path.join(root, "lessons");
const published = path.join(site, "public", "data", "recordings");
fs.rmSync(published, { recursive: true, force: true });
const entries = [];
for (const folder of fs.readdirSync(lessonsDir).sort()) {
  const manifestFile = path.join(lessonsDir, folder, "lesson.json");
  const recordingsDir = path.join(lessonsDir, folder, "recordings");
  if (!fs.existsSync(manifestFile) || !fs.existsSync(recordingsDir)) continue;
  const manifest = readJson(manifestFile);
  const lesson = { manifest, overlays: overlaysNextTo(manifestFile), number: numbers.get(manifest.id) };
  if (!lesson.number) throw new Error(`lessons/${folder}: ${manifest.id} is not in the catalog`);
  for (const file of fs.readdirSync(recordingsDir).sort()) {
    if (!file.endsWith(".json")) continue;
    const source = path.join(recordingsDir, file);
    const relative = path.relative(root, source).split(path.sep).join("/");
    const name = file.slice(0, -".json".length);
    entries.push(recordingEntry(relative, name, readJson(source), lesson));
    const target = path.join(published, manifest.id, file);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.copyFileSync(source, target);
  }
}
const groups = groupRecordings(entries);
writeJson(path.join(site, "src", "generated", "recordings.json"), groups);

const shots = path.join(site, "public", "screenshots");
fs.rmSync(shots, { recursive: true, force: true });
for (const locale of ["zh-CN", ...LOCALES]) {
  for (const name of SCREENSHOTS) {
    const source = path.join(root, "docs", "assets", "screenshots", locale, `${name}.png`);
    if (!fs.existsSync(source)) throw new Error(`missing screenshot ${path.relative(root, source)}`);
    fs.mkdirSync(path.join(shots, locale), { recursive: true });
    fs.copyFileSync(source, path.join(shots, locale, `${name}.png`));
  }
}

console.log(
  `site data: ${curriculum.lessonCount} lessons in ${curriculum.categories.length} categories, ` +
    `${entries.length} recordings in ${groups.length} replays`,
);
