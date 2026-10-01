// Counts brittle selectors left in the Playwright specs, via the TypeScript AST
// so comments and fixture data never count:
// - cjkSelectors: Chinese text used to find elements (getByRole names,
//   getByText/Label/Title, locator/filter hasText);
// - cjkAssertions: Chinese text hardcoded as an expected value (toHaveText,
//   toContainText, ...), i.e. copy not yet read from src/i18n/locales;
// - classSelectors: CSS class selectors passed to locator().
// The ratchet test only lets these numbers go down; run
// `npm run e2e:selectors` after migrating more selectors to tighten it.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const CJK = /[　-〿㐀-䶿一-鿿豈-﫿＀-￯]/;
// A dot followed by an identifier start, not inside an attribute value; "..", "./x" never match.
const CLASS_SELECTOR = /(^|[\s>+~,(:])\.[A-Za-z_-][\w-]*/;
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
export const e2eDir = path.join(root, "e2e");
export const baselinePath = path.join(e2eDir, "selector-baseline.json");

const FINDERS = new Set([
  "getByRole",
  "getByText",
  "getByLabel",
  "getByTitle",
  "getByPlaceholder",
  "getByAltText",
]);
const TEXT_OPTIONS = new Set(["hasText", "hasNotText"]);

const isCjkLiteral = (node) =>
  ((ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) &&
    CJK.test(node.text)) ||
  (ts.isRegularExpressionLiteral(node) && CJK.test(node.text)) ||
  (ts.isTemplateExpression(node) &&
    [
      node.head.text,
      ...node.templateSpans.map((span) => span.literal.text),
    ].some((part) => CJK.test(part)));

/** Literal CJK copy anywhere inside `node`, not descending into functions. */
function countCjk(node) {
  if (isCjkLiteral(node)) return 1;
  if (ts.isFunctionLike(node)) return 0;
  let count = 0;
  ts.forEachChild(node, (child) => {
    count += countCjk(child);
  });
  return count;
}

/** Only the hasText / hasNotText values of an options object. */
function countTextOptions(node) {
  if (!node || !ts.isObjectLiteralExpression(node)) return 0;
  return node.properties
    .filter(
      (property) =>
        ts.isPropertyAssignment(property) &&
        TEXT_OPTIONS.has(property.name.getText()),
    )
    .reduce((sum, property) => sum + countCjk(property.initializer), 0);
}

export function countSelectors(text, fileName = "file.spec.ts") {
  const source = ts.createSourceFile(
    fileName,
    text,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TS,
  );
  const counts = { cjkSelectors: 0, cjkAssertions: 0, classSelectors: 0 };
  const visit = (node) => {
    if (
      ts.isCallExpression(node) &&
      ts.isPropertyAccessExpression(node.expression)
    ) {
      const method = node.expression.name.text;
      const [first, second] = node.arguments;
      if (FINDERS.has(method))
        counts.cjkSelectors += node.arguments.reduce(
          (sum, arg) => sum + countCjk(arg),
          0,
        );
      else if (method === "locator") {
        if (first && isCjkLiteral(first)) counts.cjkSelectors++;
        if (
          first &&
          (ts.isStringLiteral(first) ||
            ts.isNoSubstitutionTemplateLiteral(first)) &&
          CLASS_SELECTOR.test(first.text.replace(/\[[^\]]*\]/g, ""))
        )
          counts.classSelectors++;
        counts.cjkSelectors += countTextOptions(second);
      } else if (method === "filter")
        // Array.prototype.filter takes a function; only locator options count.
        counts.cjkSelectors += countTextOptions(first);
      else if (/^to[A-Z]/.test(method))
        counts.cjkAssertions += node.arguments.reduce(
          (sum, arg) => sum + countCjk(arg),
          0,
        );
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  return counts;
}

export function scanSpecs(dir = e2eDir) {
  const result = {};
  for (const name of fs.readdirSync(dir).sort()) {
    if (!name.endsWith(".spec.ts")) continue;
    result[name] = countSelectors(
      fs.readFileSync(path.join(dir, name), "utf8"),
      name,
    );
  }
  return result;
}

export const totals = (scan) =>
  Object.values(scan).reduce(
    (sum, counts) => {
      for (const key of Object.keys(sum)) sum[key] += counts[key];
      return sum;
    },
    { cjkSelectors: 0, cjkAssertions: 0, classSelectors: 0 },
  );

if (
  process.argv[1] &&
  fileURLToPath(import.meta.url) === path.resolve(process.argv[1])
) {
  const dir = process.argv[2] ? path.resolve(process.argv[2]) : e2eDir;
  const scan = scanSpecs(dir);
  if (dir === e2eDir)
    fs.writeFileSync(baselinePath, `${JSON.stringify(scan, null, 2)}\n`);
  else console.log(JSON.stringify(scan, null, 2));
  const sum = totals(scan);
  console.log(
    `E2E selectors: ${sum.cjkSelectors} Chinese selectors, ${sum.cjkAssertions} Chinese assertions, ${sum.classSelectors} class selectors`,
  );
}
