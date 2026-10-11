import i18n from "../i18n";

/**
 * Display name of a model provider in the UI language. The server's label is
 * written in the source language (it is also recorded in run events, where it
 * stays as recorded); providers whose name needs translating have a key under
 * settings:providerNames, the others keep their own (brand) name.
 */
export function providerName(id: string | undefined, label: string | undefined) {
  const key = `settings:providerNames.${id}`;
  if (id && i18n.exists(key)) return i18n.t(key as never) as string;
  return label || id || "";
}
