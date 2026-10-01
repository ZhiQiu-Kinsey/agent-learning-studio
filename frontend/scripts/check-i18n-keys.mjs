// Locale key checker. Idea adapted from OpenMAIC scripts/check-i18n-keys.mjs
// (MIT, Copyright (c) 2026 THU-MAIC; see THIRD_PARTY_NOTICES.md), extended with
// namespaces, placeholders, empty values, plural categories and
// "identical to source" warnings.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const PLURAL = /_(zero|one|two|few|many|other)$/;
const placeholders = (value) =>
  [...value.matchAll(/\{\{\s*([\w.]+)\s*(?:,[^}]*)?\}\}/g)]
    .map((match) => match[1])
    .sort()
    .join(",");

function flatten(value, file, keyPath, into, errors) {
  if (typeof value === "string") {
    if (!value.trim()) errors.push(`${file}: "${keyPath}" is empty`);
    into.set(keyPath, value);
  } else if (Array.isArray(value)) {
    errors.push(`${file}: "${keyPath || "<root>"}" is an array; use keyed objects`);
  } else if (value && typeof value === "object") {
    const entries = Object.entries(value);
    if (!entries.length) errors.push(`${file}: "${keyPath || "<root>"}" is an empty object`);
    for (const [key, child] of entries)
      flatten(child, file, keyPath ? `${keyPath}.${key}` : key, into, errors);
  } else {
    errors.push(`${file}: "${keyPath || "<root>"}" must be a string or object`);
  }
  return into;
}

/** Split flat keys into plain keys and plural groups (base -> categories). */
function groupPlurals(keys) {
  const plain = new Set();
  const plural = new Map();
  for (const key of keys) {
    const match = key.match(PLURAL);
    const base = match && key.slice(0, -match[0].length);
    if (match && keys.has(`${base}_other`)) {
      if (!plural.has(base)) plural.set(base, new Set());
      plural.get(base).add(match[1]);
    } else plain.add(key);
  }
  return { plain, plural };
}

function readNamespace(dir, locale, namespace, errors) {
  const file = `${locale}/${namespace}`;
  try {
    const parsed = JSON.parse(
      fs.readFileSync(path.join(dir, locale, namespace), "utf8"),
    );
    return flatten(parsed, file, "", new Map(), errors);
  } catch (error) {
    errors.push(`${file}: ${error.message}`);
    return new Map();
  }
}

export function checkLocales(dir, sourceLocale = "zh-CN") {
  const errors = [];
  const warnings = [];
  const localeDirs = fs
    .readdirSync(dir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort();
  if (!localeDirs.includes(sourceLocale))
    return { errors: [`missing source locale ${sourceLocale}`], warnings, locales: localeDirs };

  const listNamespaces = (locale) =>
    fs.readdirSync(path.join(dir, locale)).filter((name) => name.endsWith(".json")).sort();
  const sourceNamespaces = listNamespaces(sourceLocale);
  const source = Object.fromEntries(
    sourceNamespaces.map((ns) => [ns, readNamespace(dir, sourceLocale, ns, errors)]),
  );

  for (const locale of localeDirs) {
    if (locale === sourceLocale) continue;
    let categories;
    try {
      categories = new Intl.PluralRules(locale).resolvedOptions().pluralCategories;
    } catch {
      errors.push(`${locale}: not a valid BCP 47 locale`);
      continue;
    }
    const present = listNamespaces(locale);
    for (const ns of present)
      if (!sourceNamespaces.includes(ns)) errors.push(`${locale}/${ns}: namespace not in source`);
    for (const ns of sourceNamespaces) {
      if (!present.includes(ns)) {
        errors.push(`${locale}/${ns}: missing namespace`);
        continue;
      }
      const base = source[ns];
      const target = readNamespace(dir, locale, ns, errors);
      const src = groupPlurals(new Set(base.keys()));
      const dst = groupPlurals(new Set(target.keys()));
      const where = `${locale}/${ns}`;
      for (const key of src.plain) if (!dst.plain.has(key)) errors.push(`${where}: missing "${key}"`);
      for (const key of dst.plain) if (!src.plain.has(key)) errors.push(`${where}: extra "${key}"`);
      for (const [key, forms] of src.plural) {
        const got = dst.plural.get(key) ?? new Set();
        const missing = categories.filter((form) => !got.has(form));
        if (missing.length) errors.push(`${where}: "${key}" lacks plural forms ${missing.join(", ")}`);
        for (const form of got)
          if (!categories.includes(form) && form !== "zero")
            errors.push(`${where}: "${key}_${form}" is not a plural form of ${locale}`);
        if (!forms.size) errors.push(`${where}: "${key}" has no source forms`);
      }
      for (const key of dst.plural.keys())
        if (!src.plural.has(key)) errors.push(`${where}: extra plural "${key}"`);

      const sourceOther = (key) => base.get(key) ?? base.get(key.replace(PLURAL, "_other"));
      for (const [key, value] of target) {
        const reference = sourceOther(key);
        if (reference === undefined) continue;
        if (placeholders(value) !== placeholders(reference))
          errors.push(`${where}: "${key}" placeholders differ from source`);
        if (value === reference && /\p{L}/u.test(value))
          warnings.push(`${where}: "${key}" is identical to source`);
      }
    }
  }
  return { errors, warnings, locales: localeDirs };
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  const dir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src/i18n/locales");
  const { errors, warnings, locales } = checkLocales(dir);
  for (const warning of warnings) console.warn(`warning: ${warning}`);
  if (errors.length) {
    for (const error of errors) console.error(`error: ${error}`);
    process.exit(1);
  }
  console.log(`i18n keys aligned across ${locales.length} locale(s): ${locales.join(", ")}`);
}
