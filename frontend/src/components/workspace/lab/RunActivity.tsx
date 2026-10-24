import { useTranslation } from "react-i18next";
import type { StageSpan } from "../../../stage/derive";
import { useElapsedMs } from "../../../stage/useElapsed";
import type { Trace } from "../../../types";
import LatticeLoader from "../../react-bits/LatticeLoader";
import ThoughtLine from "../../react-bits/ThoughtLine";
import type { StreamProgress } from "./streaming";
import { useEventText } from "./useEventText";

/**
 * The run's activity line. While the run waits at an approval gate it says so,
 * with the real time since the request; while a model request is open (request
 * sent, no response yet) it says "waiting for the model response", or, for a
 * stream, how many chunks really arrived; otherwise it names the latest event.
 */
export function RunActivity({
  openLlm,
  openApproval,
  stream,
  last,
}: {
  openLlm: StageSpan | undefined;
  openApproval?: StageSpan;
  stream?: StreamProgress | null;
  last: Trace | undefined;
}) {
  const { t, i18n } = useTranslation("lab", { keyPrefix: "bench.wait" });
  const { label, summary } = useEventText();
  const elapsed = useElapsedMs(openApproval?.startAt ?? openLlm?.startAt);
  const number = new Intl.NumberFormat(i18n.language, {
    maximumFractionDigits: 0,
  });
  if (openApproval)
    return (
      <div
        className="trace-activity is-waiting"
        data-testid="lab-approval-wait"
      >
        <ThoughtLine
          label={t("approval")}
          working
          glyph="dot"
          elapsed={elapsed == null ? undefined : elapsed / 1000}
          showTimer={elapsed != null}
          collapsible={false}
          color="var(--text)"
          glyphColor="var(--role-tool)"
          fontSize={13}
        />
      </div>
    );
  const streaming =
    openLlm && stream && !stream.finished && stream.chunks > 0 ? stream : null;
  if (openLlm)
    return (
      <div className="trace-activity is-waiting" data-testid="lab-model-wait">
        <ThoughtLine
          label={
            streaming
              ? `${t("streaming", { chunks: streaming.chunks })}${
                  streaming.firstChunkMs !== null
                    ? ` · ${t("firstChunk", { ms: number.format(streaming.firstChunkMs) })}`
                    : ""
                }`
              : `${t("model")} · ${t("round", { round: openLlm.round ?? 1 })}`
          }
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
              value: number.format(elapsed / 1000),
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
