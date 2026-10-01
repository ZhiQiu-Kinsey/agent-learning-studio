import fs from "node:fs";

// 浏览器测试按键读取界面文案，界面语言或措辞调整后断言随 locales 同步。
// 键写作 "namespace:path.to.key"，省略命名空间时为 common，与组件里的 t() 一致。
const localeDir = new URL("../src/i18n/locales/zh-CN/", import.meta.url);
const namespaces = new Map<string, Record<string, unknown>>();

function load(namespace: string) {
  let resource = namespaces.get(namespace);
  if (!resource) {
    resource = JSON.parse(
      fs.readFileSync(new URL(`${namespace}.json`, localeDir), "utf8"),
    ) as Record<string, unknown>;
    namespaces.set(namespace, resource);
  }
  return resource;
}

function lookup(key: string) {
  const [namespace, path] = key.includes(":")
    ? (key.split(":", 2) as [string, string])
    : ["common", key];
  const value = path
    .split(".")
    .reduce<unknown>(
      (node, part) =>
        node && typeof node === "object"
          ? (node as Record<string, unknown>)[part]
          : undefined,
      load(namespace),
    );
  if (typeof value !== "string") throw new Error(`zh-CN 文案中没有键 ${key}`);
  return value;
}

const placeholder = /\{\{\s*(\w+)\s*\}\}/g;

/** 按键返回 zh-CN 文案，并像 i18next 一样替换 {{name}} 占位符。 */
export function t(key: string, params: Record<string, string | number> = {}) {
  return lookup(key).replace(placeholder, (match, name: string) => {
    if (!(name in params)) throw new Error(`${key} 缺少参数 ${name}`);
    return String(params[name]);
  });
}

/** 文案含运行时才知道的参数时，未给出的占位符匹配任意文本。 */
export function tPattern(
  key: string,
  params: Record<string, string | number> = {},
) {
  const source = lookup(key)
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
