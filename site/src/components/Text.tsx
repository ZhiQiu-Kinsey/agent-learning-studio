import type { ElementType } from "react";
import { pick } from "../data/localized";
import type { Localized } from "../data/types";
import { useSiteLocale } from "./useSiteLocale";

/** Catalog text in the UI language; a source-language fallback carries lang="zh-CN". */
export function Text({
  value,
  as: Tag = "span",
  className,
}: {
  value: Localized;
  as?: ElementType;
  className?: string;
}) {
  const shown = pick(value, useSiteLocale());
  return (
    <Tag className={className} lang={shown.lang}>
      {shown.text}
    </Tag>
  );
}
