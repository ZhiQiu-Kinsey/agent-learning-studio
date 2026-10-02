import { useTranslation } from "react-i18next";
import type { Detail } from "../../types";
import { basename, dirname } from "./paths";

/** The lesson's source files; the current one carries aria-current. */
export function FileList({
  sources,
  activeIndex,
  onSelect,
}: {
  sources: Detail["sources"];
  activeIndex: number;
  onSelect: (index: number) => void;
}) {
  const { t } = useTranslation("lesson", { keyPrefix: "code" });
  return (
    <nav
      className="code-files"
      aria-label={t("files")}
      data-testid="code-files"
    >
      <ul>
        {sources.map((file, index) => (
          <li key={file.path}>
            <button
              type="button"
              data-testid="code-file"
              data-path={file.path}
              aria-current={index === activeIndex ? "true" : undefined}
              title={file.path}
              onClick={() => onSelect(index)}
            >
              <span className="code-file-name">
                {basename(file.path)}
                {file.role && file.role !== "lesson" && (
                  <span
                    className="code-file-role"
                    data-role={file.role}
                    title={t(`role.${file.role}Help`)}
                  >
                    {t(`role.${file.role}`)}
                  </span>
                )}
              </span>
              <span className="code-file-dir">{dirname(file.path)}</span>
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}
