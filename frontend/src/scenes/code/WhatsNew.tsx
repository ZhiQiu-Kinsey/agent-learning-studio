import type { CSSProperties } from "react";
import { useTranslation } from "react-i18next";
import { whatsNewItems, type LessonCode } from "./model";
import { basename } from "./paths";

/** 本课新增: symbols new or changed since the previous lesson; click to jump. */
export function WhatsNew({
  code,
  onJump,
}: {
  code: LessonCode;
  onJump: (path: string, start: number, end: number) => void;
}) {
  const { t } = useTranslation("lesson", { keyPrefix: "code.whatsNew" });
  const items = whatsNewItems(code);
  const compare = code.whats_new.compare_with;
  const unchanged = code.whats_new.unchanged.length;
  return (
    <section
      className="code-whats-new"
      data-testid="code-whats-new"
      aria-labelledby="code-whats-new-title"
    >
      <span className="reading-eyebrow">{t("eyebrow")}</span>
      <h2 id="code-whats-new-title">{t("title")}</h2>
      <p>
        {compare
          ? t("compared", { number: compare.number, title: compare.title })
          : t("first")}
      </p>
      {items.length ? (
        <ul>
          {items.map((item, index) => (
            <li
              key={`${item.path}:${item.name}:${item.start}`}
              style={{ "--i": index } as CSSProperties}
            >
              <button
                type="button"
                data-testid="code-whats-new-item"
                data-symbol={item.name}
                data-status={item.status}
                data-path={item.path}
                data-line={item.start}
                title={item.path}
                onClick={() => onJump(item.path, item.start, item.end)}
              >
                <span className="code-symbol-status">
                  {t(`status.${item.status}`)}
                </span>
                <span className="code-symbol-name">{item.name}</span>
                <span className="code-symbol-meta">
                  {t(`kind.${item.kind}`)} ·{" "}
                  {t("location", {
                    file: basename(item.path),
                    line: item.start,
                  })}
                </span>
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p>{t("none")}</p>
      )}
      {compare && unchanged > 0 && (
        <p className="code-whats-new-unchanged">
          {t("unchanged", { value: unchanged })}
        </p>
      )}
    </section>
  );
}
