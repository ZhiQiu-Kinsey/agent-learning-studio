import { CheckCircle2, CircleHelp, ShieldAlert } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { InspectorExtensionProps } from "../types";
import "./tool-outcomes.css";

/** This view reads visible events only: rewind also rewinds the outcome counts. */
export default function ToolOutcomes({
  studio,
  children,
}: InspectorExtensionProps) {
  const { t } = useTranslation("lab", { keyPrefix: "toolOutcomes" });
  const outcomes = studio.visible
    .map((event, index) => ({ event, index }))
    .filter(({ event }) => event.type === "tool_result")
    .map(({ event, index }) => {
      const result = event.data.result;
      const ok =
        result && typeof result === "object" && "ok" in result
          ? result.ok
          : undefined;
      return { index, name: String(event.data.name || t("defaultTool")), ok };
    });
  const passed = outcomes.filter((item) => item.ok === true).length;
  const failed = outcomes.filter((item) => item.ok === false).length;
  const unknown = outcomes.length - passed - failed;
  return (
    <>
      {children}
      <section className="tool-outcomes" aria-label={t("region")}>
        <div className="tool-outcomes-heading">
          <strong>{t("title")}</strong>
          <small>{t("source")}</small>
        </div>
        <div className="tool-outcome-counts" aria-live="polite">
          <span>
            <CheckCircle2 size={14} />
            {t("passed")} {passed}
          </span>
          <span>
            <ShieldAlert size={14} />
            {t("failed")} {failed}
          </span>
          {unknown > 0 && (
            <span>
              <CircleHelp size={14} />
              {t("unknown")} {unknown}
            </span>
          )}
        </div>
        {outcomes.length ? (
          <div className="tool-outcome-links">
            {outcomes.map(({ index, name, ok }) => (
              <button
                key={index}
                type="button"
                data-outcome={
                  ok === true ? "passed" : ok === false ? "failed" : "unknown"
                }
                aria-label={t("locate", { n: index + 1, name })}
                aria-pressed={studio.active === studio.visible[index]}
                onClick={() => studio.selectEvent(index)}
              >
                <span>{name}</span>
                <span>
                  {ok === true
                    ? t("passed")
                    : ok === false
                      ? t("failed")
                      : t("unknown")}{" "}
                  · {t("eventN", { n: index + 1 })}
                </span>
              </button>
            ))}
          </div>
        ) : (
          <p>{t("empty")}</p>
        )}
      </section>
    </>
  );
}
