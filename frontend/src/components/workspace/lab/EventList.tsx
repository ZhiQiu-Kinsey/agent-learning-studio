import { useEffect, useId, useRef } from "react";
import { useTranslation } from "react-i18next";
import { motion } from "motion/react";
import { Waypoints } from "lucide-react";
import { useReducedMotion } from "../../../motion";
import type { StudioState } from "../../../hooks/useStudio";
import { Button } from "../../ui/button";
import { useEventText } from "./useEventText";

/** Selection pill glides between events; a snappy spring, no overshoot. */
const PILL_SPRING = {
  type: "spring",
  stiffness: 520,
  damping: 40,
  mass: 0.8,
} as const;

/** The run's events up to the replay cursor, in order; click one to inspect it. */
export function EventList({ studio: s }: { studio: StudioState }) {
  const { t } = useTranslation("lab", { keyPrefix: "bench.list" });
  const { label, summary } = useEventText();
  const reducedMotion = useReducedMotion();
  const pillId = useId();
  const list = useRef<HTMLDivElement>(null);
  // Follow a live run to its newest event.
  useEffect(() => {
    if (s.running && list.current)
      list.current.scrollTop = list.current.scrollHeight;
  }, [s.events.length, s.running]);
  return (
    <div className="trace-list-pane" data-testid="lab-trace-list">
      <div className="subpane-label">
        {t("title")} <small>EVENTS</small>
      </div>
      <div className="timeline" ref={list} data-testid="lab-timeline">
        {s.visible.map((event, index) => {
          const selected = s.active === event;
          return (
            <Button
              key={index}
              variant="ghost"
              className={`event event-${event.type} ${selected ? "is-selected" : ""}`}
              data-testid={`lab-event-${event.type.replace(/[._]/g, "-")}`}
              data-event-index={index}
              aria-pressed={selected}
              onClick={() => s.selectEvent(index)}
            >
              {selected && (
                <motion.span
                  layoutId={`${pillId}-event`}
                  className="event-pill"
                  aria-hidden="true"
                  transition={reducedMotion ? { duration: 0 } : PILL_SPRING}
                />
              )}
              <span className="event-index">
                {String(index + 1).padStart(2, "0")}
              </span>
              <span className="event-text">
                <strong>{label(event)}</strong>
                <small>{summary(event)}</small>
              </span>
              <span className="event-round">
                {event.round ? `R${event.round}` : ""}
              </span>
            </Button>
          );
        })}
        {!s.visible.length && (
          <div className="trace-list-empty">
            <Waypoints size={24} />
            <p>{s.events.length ? t("rewound") : t("empty")}</p>
            <small>{s.events.length ? t("rewoundHint") : t("emptyHint")}</small>
          </div>
        )}
      </div>
    </div>
  );
}
