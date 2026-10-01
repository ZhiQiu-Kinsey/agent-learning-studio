import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "../../components/ui/button";
import { AgentStage } from "../../stage/AgentStage";
import type { Trace } from "../../types";
import type { Flow, Illustration } from "../types.gen";

/**
 * A teaching illustration rendered by the same stage as real runs. Every event
 * carries provenance=illustration, so the stage draws it dashed with the
 * "not a run record" watermark. Stepping is manual: nothing plays by itself.
 */
export function IllustrationFlow({
  block,
  illustration,
}: {
  block: Flow;
  illustration: Illustration;
}) {
  const { t } = useTranslation("blocks", { keyPrefix: "flow" });
  const events = useMemo<Trace[]>(
    () =>
      illustration.events.map((event) => ({
        type: event.type,
        round: event.round ?? null,
        timestamp: "",
        data: event.data,
        provenance: "illustration",
      })),
    [illustration],
  );
  const [cursor, setCursor] = useState(1);
  return (
    <section
      className="illustration-flow"
      aria-label={block.title ?? t("region")}
      data-testid="illustration-flow"
    >
      {block.title && <h3>{block.title}</h3>}
      <AgentStage events={events} cursor={cursor} live={false} />
      <div className="illustration-controls">
        <Button
          size="sm"
          variant="ghost"
          disabled={cursor <= 1}
          onClick={() => setCursor(cursor - 1)}
        >
          {t("back")}
        </Button>
        <span>{t("position", { current: cursor, total: events.length })}</span>
        {cursor < events.length ? (
          <Button size="sm" onClick={() => setCursor(cursor + 1)}>
            {t("step")}
          </Button>
        ) : (
          <Button size="sm" variant="outline" onClick={() => setCursor(1)}>
            {t("restart")}
          </Button>
        )}
      </div>
      {block.caption && <p className="illustration-caption">{block.caption}</p>}
    </section>
  );
}
