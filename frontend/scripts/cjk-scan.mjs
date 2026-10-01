// Counts hardcoded CJK copy in TS/TSX source (string literals, template parts,
// JSX text) via the TypeScript AST, so comments never count. Used by the
// ratchet test and `npm run i18n:baseline`. Idea from OpenMAIC
// tests/workbench/workbench-i18n.test.ts (MIT, Copyright (c) 2026 THU-MAIC).
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const CJK = /[　-〿㐀-䶿一-鿿豈-﫿＀-￯]/;
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
export const srcDir = path.join(root, "src");
export const baselinePath = path.join(srcDir, "i18n", "cjk-baseline.json");

const skip = (file) =>
  /\.(test|spec)\.tsx?$/.test(file) || file.endsWith(".d.ts");

// Locale files and the registry's self-names are data, not hardcoded copy.
const skipDir = (dir) => dir === path.join(srcDir, "i18n");

function* walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) { if (!skipDir(full)) yield* walk(full); }
    else if (/\.tsx?$/.test(entry.name) && !skip(entry.name)) yield full;
  }
}

export function countCjk(text, fileName = "file.tsx") {
  const source = ts.createSourceFile(fileName, text, ts.ScriptTarget.Latest, true,
    fileName.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  let count = 0;
  const visit = (node) => {
    if (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) return;
    if (ts.isTemplateExpression(node)) {
      // One template literal is one piece of copy, however many parts it has.
      const parts = [node.head.text, ...node.templateSpans.map((span) => span.literal.text)];
      if (parts.some((part) => CJK.test(part))) count++;
      node.templateSpans.forEach((span) => visit(span.expression));
      return;
    }
    if (
      (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node) ||
        ts.isJsxText(node)) &&
      CJK.test(node.text)
    )
      count++;
    ts.forEachChild(node, visit);
  };
  visit(source);
  return count;
}

export function scanSource() {
  const counts = {};
  for (const file of walk(srcDir)) {
    const count = countCjk(fs.readFileSync(file, "utf8"), file);
    if (count) counts[path.relative(srcDir, file).split(path.sep).join("/")] = count;
  }
  return Object.fromEntries(Object.entries(counts).sort(([a], [b]) => a.localeCompare(b)));
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  const counts = scanSource();
  fs.writeFileSync(baselinePath, `${JSON.stringify(counts, null, 2)}\n`);
  const total = Object.values(counts).reduce((sum, n) => sum + n, 0);
  console.log(`CJK baseline: ${total} literals in ${Object.keys(counts).length} files`);
}
