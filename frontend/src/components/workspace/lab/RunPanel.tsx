import { useTranslation } from "react-i18next";
import { Check, History, MessageSquare } from "lucide-react";
import type { StudioState } from "../../../hooks/useStudio";
import { providerName } from "../../../lib/providerName";
import LatticeLoader from "../../react-bits/LatticeLoader";
import { Answer } from "../../Answer";
import { Button } from "../../ui/button";
import { Composer } from "./Composer";
import { RuntimeLanguageNote } from "./RunLanguage";
import { resumedFromOf } from "./approvals";
import { streamProgress, type StreamProgress } from "./streaming";

/**
 * Text of a streamed response exactly as its chunks arrived, up to the cursor:
 * each delta event adds what it carried, no typing effect. Ended streams say
 * how they ended (a stopped stream keeps only what arrived before the stop).
 */
function StreamText({
  progress,
  lang,
}: {
  progress: StreamProgress;
  lang?: string;
}) {
  const { t } = useTranslation("lab", { keyPrefix: "bench.answer" });
  const status = progress.finished
    ? (progress.facts?.status ?? "completed")
    : "receiving";
  return (
    <div
      className="stream-text"
      data-testid="lab-stream-text"
      data-status={status}
    >
      <p className="stream-text-meta">
        {t(`stream.${status}` as "stream.receiving", {
          chunks: progress.chunks,
          defaultValue: status,
        })}
      </p>
      <div className="answer-content stream-text-body" lang={lang}>
        {progress.text}
      </div>
    </div>
  );
}

/** The final answer of the run at the replay cursor, or what it is waiting for. */
function AnswerPane({ studio: s }: { studio: StudioState }) {
  const { t } = useTranslation("lab", { keyPrefix: "bench.answer" });
  const stream = streamProgress(s.visible);
  const resumed = resumedFromOf(s.events);
  return (
    <section className="lab-answer" aria-live="polite">
      <div className="pane-heading">
        <span>
          <MessageSquare size={17} />
          {t("title")}
        </span>
        {s.answer && <Check size={15} />}
      </div>
      <RuntimeLanguageNote
        locale={s.runLocale}
        kind="run"
        testId="lab-run-locale"
      />
      {resumed && (
        <p className="composer-restored" data-testid="lab-resumed-from">
          <History size={14} aria-hidden="true" />
          <span>
            {t("resumedFrom", {
              run: resumed.runId.slice(0, 8),
              name: resumed.name || resumed.checkpointId,
            })}
          </span>
        </p>
      )}
      {s.answer ? (
        <Answer
          content={String(s.answer.data.content || t("noText"))}
          lang={s.runLocale ?? undefined}
        />
      ) : stream && (stream.text || stream.finished) ? (
        <StreamText progress={stream} lang={s.runLocale ?? undefined} />
      ) : (
        <div className="answer-placeholder">
          {s.running ? (
            <LatticeLoader
              pattern="snake"
              color="var(--accent)"
              fontSize={13}
              label={s.requiresModel ? t("waitingModel") : t("waitingLocal")}
            />
          ) : (
            <>
              {t("empty")}
              <span>{t("emptyReplay")}</span>
            </>
          )}
        </div>
      )}
    </section>
  );
}

/** Which provider and model a run would use; the lesson program needs none. */
function ConnectionBar({
  studio: s,
  onConfigure,
}: {
  studio: StudioState;
  onConfigure: () => void;
}) {
  const { t } = useTranslation("lab", { keyPrefix: "bench.connection" });
  return (
    <div className="lab-connection">
      <i />
      <span>
        {s.requiresModel
          ? providerName(s.status?.provider_id, s.status?.provider_label) ||
            t("none")
          : t("local")}
        <small>
          {s.requiresModel ? s.status?.model || t("noModel") : t("localNote")}
        </small>
      </span>
      <Button variant="ghost" size="sm" onClick={onConfigure}>
        {t("settings")}
      </Button>
    </div>
  );
}

/** Top of the lab bench: ask on the left; the answer and the connection on the right. */
export function RunPanel({
  studio,
  onConfigure,
  onRun,
}: {
  studio: StudioState;
  onConfigure: () => void;
  onRun: () => void;
}) {
  return (
    <div className="lab-command-column">
      <Composer studio={studio} onConfigure={onConfigure} onRun={onRun} />
      <AnswerPane studio={studio} />
      <ConnectionBar studio={studio} onConfigure={onConfigure} />
    </div>
  );
}
