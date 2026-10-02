import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useReducedMotion } from "../../../motion";
import type { Trace } from "../../../types";
import CountUp from "../../react-bits/CountUp";

function RunMetric({ value }: { value: number }) {
  const reduced = useReducedMotion();
  const previous = useRef(value);
  useEffect(() => {
    previous.current = value;
  }, [value]);
  return (
    <b>
      <span className="sr-only">{value}</span>
      <span aria-hidden="true">
        {reduced ? (
          value
        ) : (
          <CountUp
            key={value}
            from={previous.current}
            to={value}
            duration={0.35}
          />
        )}
      </span>
    </b>
  );
}

/** Counts of what is shown at the replay cursor: requests, tool calls, events. */
export function RunMetrics({
  visible,
  cursor,
}: {
  visible: readonly Trace[];
  cursor: number;
}) {
  const { t } = useTranslation("lab", { keyPrefix: "bench.metrics" });
  const requests = visible.filter((e) => e.type === "request").length;
  const tools = visible.filter((e) => e.type === "tool_call").length;
  return (
    <div className="inspector-summary" data-testid="lab-run-metrics">
      <span>
        <RunMetric value={requests} /> {t("requests")}
      </span>
      <span>
        <RunMetric value={tools} /> {t("tools")}
      </span>
      <span>
        <RunMetric value={cursor} /> {t("events")}
      </span>
    </div>
  );
}
