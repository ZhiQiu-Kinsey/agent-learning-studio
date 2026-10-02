import { useTranslation } from "react-i18next";
import type { StageSpan } from "../../../stage/derive";
import { useElapsedMs } from "../../../stage/useElapsed";
import type { Trace } from "../../../types";
import LatticeLoader from "../../react-bits/LatticeLoader";
import ThoughtLine from "../../react-bits/ThoughtLine";
import { useEventText } from "./useEventText";

/**
 * The run's activity line. While a model request is open (request sent, no
 * response yet) it says "waiting for the model response" with the real time
 * since that request's server timestamp; otherwise it names the latest event.
 */
export function RunActivity({
  openLlm,
  last,
}: {
  openLlm: StageSpan | undefined;
  last: Trace | undefined;
}) {
  const { t, i18n } = useTranslation("lab", { keyPrefix: "bench.wait" });
  const { label, summary } = useEventText();
  const elapsed = useElapsedMs(openLlm?.startAt);
  if (openLlm)
    return (
      <div className="trace-activity is-waiting" data-testid="lab-model-wait">
        <ThoughtLine
          label={`${t("model")} · ${t("round", { round: openLlm.round ?? 1 })}`}
          working
          glyph={
            <LatticeLoader
              pattern="orbit"
              cellSize={4}
              gap={1.5}
              color="var(--role-model)"
              className="trace-activity-lattice"
            />
          }
          elapsed={elapsed == null ? undefined : elapsed / 1000}
          showTimer={elapsed != null}
          collapsible={false}
          color="var(--text)"
          fontSize={13}
        />
        <span className="sr-only">
          {elapsed != null &&
            t("seconds", {
              value: new Intl.NumberFormat(i18n.language, {
                maximumFractionDigits: 0,
              }).format(elapsed / 1000),
            })}
        </span>
      </div>
    );
  return (
    <div className="trace-activity">
      <ThoughtLine
        label={
          last
            ? `${label(last)} · ${summary(last).slice(0, 50)}`
            : t("connecting")
        }
        working
        showTimer={false}
        glyph="dot"
        collapsible={false}
        color="var(--text-muted)"
        glyphColor="var(--accent)"
        fontSize={13}
      />
    </div>
  );
}
