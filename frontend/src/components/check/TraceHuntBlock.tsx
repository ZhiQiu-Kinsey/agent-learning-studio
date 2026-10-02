import { useState } from "react";
import { Check, FlaskConical, Search, X } from "lucide-react";
import SparkBurst from "../react-bits/SparkBurst";
import { useTranslation } from "react-i18next";
import { toolNameOf } from "../../content/selector";
import {
  huntState,
  judgeHunt,
  type HuntVerdict,
} from "../../content/traceHunt";
import type { TraceHunt } from "../../content/types.gen";
import { huntEvidenceId, track, useProgress } from "../../progress";
import type { Trace } from "../../types";
import { Button } from "../ui/button";

const shortRun = (runId: string) => runId.slice(0, 8);

/**
 * 轨迹找错：只在学习者自己这次真实运行的事件里找；没有运行就请他先去实验，
 * 没有命中就如实说明“本次运行没有出现这条证据”，不拿示意或录制顶替。
 */
export function TraceHuntBlock({
  block,
  lessonId,
  events,
  running,
  runId,
  onOpenLab,
}: {
  block: TraceHunt;
  lessonId: string;
  events: readonly Trace[];
  running: boolean;
  runId: string;
  onOpenLab: () => void;
}) {
  const { t } = useTranslation("lesson", { keyPrefix: "check.hunt" });
  const state = huntState(block.target, events, running);
  const own = state.status === "no-run" ? [] : state.events;
  const currentRun = runId || own.find((event) => event.run_id)?.run_id || "";
  // 选择只属于当前这次运行；换了运行就重新找。
  const [pick, setPick] = useState<{
    run: string;
    count: number;
    index: number;
    verdict: HuntVerdict;
  } | null>(null);
  const picked =
    pick && pick.run === currentRun && pick.count === own.length ? pick : null;
  const recorded =
    useProgress().lessons[lessonId]?.evidence[huntEvidenceId(block.id)];

  const choose = (index: number) => {
    const event = own[index];
    const verdict = judgeHunt(block.target, event);
    setPick({ run: currentRun, count: own.length, index, verdict });
    // 只有真实运行 id 可以作为证据来源；拿不到就不写记录。
    if (verdict.correct && currentRun)
      track.evidenceFound(
        lessonId,
        huntEvidenceId(block.id),
        currentRun,
        typeof event.seq === "number" ? event.seq : undefined,
      );
  };

  return (
    <section
      className="check-block trace-hunt"
      data-testid="trace-hunt"
      data-block-id={block.id}
      aria-labelledby={`${block.id}-title`}
    >
      <div className="check-eyebrow">
        <Search size={14} aria-hidden="true" />
        {t("eyebrow")}
      </div>
      <h3 id={`${block.id}-title`}>{t("title")}</h3>
      <p className="trace-hunt-prompt">{block.prompt}</p>
      {recorded && (
        <p className="trace-hunt-recorded" data-testid="trace-hunt-recorded">
          <Check size={14} aria-hidden="true" />
          {t("recorded", { run: shortRun(recorded.runId) })}
        </p>
      )}

      {state.status === "no-run" && (
        <div className="trace-hunt-empty" data-testid="trace-hunt-no-run">
          <p>{t("noRun")}</p>
          <Button type="button" onClick={onOpenLab}>
            <FlaskConical size={15} aria-hidden="true" />
            {t("goLab")}
          </Button>
        </div>
      )}
      {state.status === "running" && (
        <p className="trace-hunt-empty" role="status">
          {t("running")}
        </p>
      )}
      {state.status === "no-evidence" && (
        <p className="trace-hunt-empty" data-testid="trace-hunt-no-evidence">
          {t("noEvidence")}
        </p>
      )}

      {state.status === "ready" && (
        <>
          {currentRun && (
            <p className="trace-hunt-source">
              {t("source", { run: shortRun(currentRun) })}
            </p>
          )}
          <p className="trace-hunt-count" id={`${block.id}-list`}>
            {t("count", { count: own.length })}
          </p>
          <ol
            className="trace-hunt-events"
            aria-label={t("list")}
            aria-describedby={`${block.id}-list`}
          >
            {own.map((event, index) => {
              const name = toolNameOf(event);
              const chosen = picked?.index === index;
              return (
                <li
                  key={`${event.seq ?? index}-${event.type}`}
                  data-testid="trace-hunt-event"
                  data-index={index}
                  data-chosen={
                    chosen
                      ? picked!.verdict.correct
                        ? "correct"
                        : "incorrect"
                      : undefined
                  }
                >
                  <Button
                    type="button"
                    variant="outline"
                    className="trace-hunt-pick"
                    aria-pressed={chosen}
                    onClick={() => choose(index)}
                  >
                    <span className="trace-hunt-step">
                      {t("step", { step: index + 1 })}
                    </span>
                    <code>{event.type}</code>
                    {event.round != null && (
                      <span>{t("round", { round: event.round })}</span>
                    )}
                    {name && <code className="trace-hunt-tool">{name}</code>}
                    <span className="sr-only">{t("pick")}</span>
                  </Button>
                  <details className="trace-hunt-data">
                    <summary>{t("inspect")}</summary>
                    <pre>{JSON.stringify(event.data, null, 2)}</pre>
                  </details>
                </li>
              );
            })}
          </ol>
        </>
      )}

      <div role="status" aria-live="polite" className="trace-hunt-verdict">
        {picked && (
          <div
            className={`check-feedback ${picked.verdict.correct ? "is-correct" : "is-incorrect"}`}
            data-testid="trace-hunt-feedback"
            data-correct={picked.verdict.correct}
          >
            <strong>
              {picked.verdict.correct && <SparkBurst key={picked.index} />}
              {picked.verdict.correct ? (
                <Check size={15} aria-hidden="true" />
              ) : (
                <X size={15} aria-hidden="true" />
              )}
              {picked.verdict.correct
                ? t("correct", { step: picked.index + 1 })
                : t("incorrect", { step: picked.index + 1 })}
            </strong>
            {!picked.verdict.correct && picked.verdict.unmet.length > 0 && (
              <p>
                {t("unmet.title")}
                {picked.verdict.unmet
                  .map((condition) => t(`unmet.${condition}`))
                  .join(" · ")}
              </p>
            )}
            {picked.verdict.correct && (
              <p data-testid="trace-hunt-explanation">
                <b>{t("explanation")}</b>
                {block.explanation}
              </p>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
