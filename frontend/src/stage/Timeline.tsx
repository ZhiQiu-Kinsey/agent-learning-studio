import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { Trace } from "../types";
import type { StageSpan } from "./derive";
import { layoutTimeline, type TimelineScale } from "./timelineLayout";

export function Timeline({
  events,
  spans,
  cursor,
  onSeek,
}: {
  events: readonly Trace[];
  /** Spans of the whole run, so bars keep their place while scrubbing. */
  spans: StageSpan[];
  cursor: number;
  onSeek: (cursor: number) => void;
}) {
  const { t, i18n } = useTranslation("stage", { keyPrefix: "timeline" });
  const [scale, setScale] = useState<TimelineScale>("time");
  if (events.length < 2) return null;
  const { lanes, ticks, totalMs, fellBack } = layoutTimeline(
    events,
    spans,
    scale,
  );
  const marker = cursor > 0 ? ticks[cursor - 1] : 0;
  return (
    <section
      className="timeline"
      aria-label={t("region")}
      data-testid="timeline"
    >
      <header>
        <div
          role="radiogroup"
          aria-label={t("scale")}
          className="timeline-scale"
        >
          {(["time", "uniform"] as const).map((option) => (
            <button
              key={option}
              type="button"
              role="radio"
              aria-checked={scale === option}
              onClick={() => setScale(option)}
            >
              {t(option)}
            </button>
          ))}
        </div>
        {totalMs !== null && (
          <small>
            {t("total", {
              value: new Intl.NumberFormat(i18n.language).format(totalMs),
            })}
          </small>
        )}
        {fellBack && <small>{t("unreadable")}</small>}
      </header>
      <div className="timeline-lanes">
        {lanes.map((lane) => (
          <div className="timeline-lane" key={lane.id} data-kind={lane.kind}>
            <span className="timeline-lane-label">
              {lane.kind === "llm"
                ? t("lane.llm")
                : t("lane.tool", { name: lane.name })}
            </span>
            <div className="timeline-track">
              {lane.bars.map(({ span, left, width }) => {
                const target = (span.endIndex ?? span.startIndex) + 1;
                return (
                  <button
                    key={`${span.id}-${span.startIndex}`}
                    type="button"
                    className="timeline-bar"
                    data-status={span.status}
                    data-reached={span.startIndex < cursor || undefined}
                    style={{ left: `${left}%`, width: `${width}%` }}
                    aria-label={t("seek", { index: target })}
                    onClick={() => onSeek(target)}
                  />
                );
              })}
              <span
                className="timeline-cursor"
                style={{ left: `${marker}%` }}
                aria-hidden="true"
              />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
