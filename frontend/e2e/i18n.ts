import fs from "node:fs";

// 浏览器测试按键读取界面文案，界面语言或措辞调整后断言随 locales 同步。
// 键写作 "namespace:path.to.key"，省略命名空间时为 common，与组件里的 t() 一致。
// 现有用例在 zh-CN 下运行（playwright.config.ts 的 locale）；英文界面的用例用 tIn("en", …)。
const resources = new Map<string, Record<string, unknown>>();

function load(locale: string, namespace: string) {
  const id = `${locale}/${namespace}`;
  let resource = resources.get(id);
  if (!resource) {
    const file = new URL(
      `../src/i18n/locales/${locale}/${namespace}.json`,
      import.meta.url,
    );
    resource = JSON.parse(fs.readFileSync(file, "utf8")) as Record<
      string,
      unknown
    >;
    resources.set(id, resource);
  }
  return resource;
}

function lookup(locale: string, key: string, count?: unknown) {
  const [namespace, path] = key.includes(":")
    ? (key.split(":", 2) as [string, string])
    : ["common", key];
  const find = (keyPath: string) =>
    keyPath
      .split(".")
      .reduce<unknown>(
        (node, part) =>
          node && typeof node === "object"
            ? (node as Record<string, unknown>)[part]
            : undefined,
        load(locale, namespace),
      );
  let value = find(path);
  // Plural keys (en): pick the form the way i18next does for `count`.
  if (value === undefined && typeof count === "number")
    value = find(
      `${path}_${new Intl.PluralRules(locale).select(count)}`,
    ) ?? find(`${path}_other`);
  if (typeof value !== "string")
    throw new Error(`${locale} 文案中没有键 ${key}`);
  return value;
}

const placeholder = /\{\{\s*(\w+)\s*\}\}/g;

function fill(
  locale: string,
  key: string,
  params: Record<string, string | number>,
) {
  return lookup(locale, key, params.count).replace(
    placeholder,
    (match, name: string) => {
      if (!(name in params)) throw new Error(`${key} 缺少参数 ${name}`);
      return String(params[name]);
    },
  );
}

/** 按键返回 zh-CN 文案，并像 i18next 一样替换 {{name}} 占位符。 */
export function t(key: string, params: Record<string, string | number> = {}) {
  return fill("zh-CN", key, params);
}

/** 按键返回指定界面语言的文案（如 "en"）。 */
export function tIn(
  locale: string,
  key: string,
  params: Record<string, string | number> = {},
) {
  return fill(locale, key, params);
}

/** 文案含运行时才知道的参数时，未给出的占位符匹配任意文本。 */
export function tPattern(
  key: string,
  params: Record<string, string | number> = {},
) {
  const source = lookup("zh-CN", key, params.count)
    .split(placeholder)
    .map((part, index) =>
      index % 2
        ? part in params
          ? escape(String(params[part]))
          : ".+?"
        : escape(part),
    )
    .join("");
  return new RegExp(source);
}

const escape = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
