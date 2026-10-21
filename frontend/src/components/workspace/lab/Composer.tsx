import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { FlaskConical, History } from "lucide-react";
import type { StudioState } from "../../../hooks/useStudio";
import { useFallbackLang } from "../../../hooks/useContentLanguage";
import PromptBar from "../../react-bits/PromptBar";
import { Button } from "../../ui/button";
import { RuntimeLanguageNote } from "./RunLanguage";

/**
 * Question bar (run / stop) and how this run is executed. The experiment card's
 * arms pick the exercise; the `/` menu in the bar is a shortcut to all of them.
 */
export function Composer({
  studio: s,
  onConfigure,
  onRun,
}: {
  studio: StudioState;
  onConfigure: () => void;
  onRun: () => void;
}) {
  const { t, i18n } = useTranslation("lab", { keyPrefix: "bench.composer" });
  const exercises = useMemo(
    () => s.detail?.exercises.filter((e) => !e.offline_only) ?? [],
    [s.detail],
  );
  const canSend =
    !!s.detail &&
    s.canRun &&
    (!!s.question.trim() || !!s.detail.capabilities?.supports_inputs);
  const needsConnection =
    s.requiresModel &&
    !(
      s.status?.config_ready &&
      (s.status.requires_api_key === false || s.status.api_key_configured)
    );
  const help = s.detail?.ui?.question_help;
  const langOf = useFallbackLang();
  return (
    <section className="lab-composer">
      <div className="pane-heading">
        <span>
          <FlaskConical size={17} />
          {t("title")}
        </span>
        <small>LIVE</small>
      </div>
      <div className="form-field">
        <label
          htmlFor="lab-question"
          lang={langOf(s.detail?.ui?.question_label)}
        >
          {s.detail?.ui?.question_label || t("question")}
        </label>
        <PromptBar
          className="lab-prompt-bar"
          minRows={2}
          value={s.question}
          onChange={s.setQuestion}
          disabled={s.running}
          busy={s.running}
          canSend={canSend}
          onSend={onRun}
          onStop={s.cancel}
          commands={exercises.map((e) => ({
            key: e.id,
            name: e.title,
            description: e.question,
            active: e.id === s.exerciseId,
          }))}
          onCommand={s.selectExercise}
          placeholder={t("placeholder")}
          labels={{
            send: t("run"),
            sendText: t("runShort"),
            stop: t("stop"),
            stopText: t("stopShort"),
            commands: t("commands"),
            openCommands: t("openCommands"),
            noMatch: t("noMatch"),
          }}
          hint={t("hint")}
          sendTestId="lab-run-button"
          stopTestId="lab-stop-button"
          textareaProps={{
            id: "lab-question",
            "data-testid": "lab-question-input",
            "aria-describedby": help ? "lab-question-help" : undefined,
          }}
        />
        {help && (
          <p
            id="lab-question-help"
            className="composer-note"
            lang={langOf(help)}
          >
            {help}
          </p>
        )}
        <RuntimeLanguageNote
          locale={s.detail?.runtime_locale}
          kind="runtime"
          testId="lab-runtime-locale"
        />
        {/* Closing the event stream is not a stop: the run goes on at the server. */}
        {s.running && s.runId && (
          <div className="composer-connection">
            {s.stopping ? (
              <p role="status" data-testid="lab-stopping">
                {t("stopping")}
              </p>
            ) : s.detached ? (
              <>
                <p role="status" data-testid="lab-detached-note">
                  {t("detachedNote")}
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={s.reattach}
                  data-testid="lab-reattach-button"
                >
                  {t("reattach")}
                </Button>
              </>
            ) : (
              <Button
                variant="ghost"
                size="sm"
                onClick={s.detach}
                data-testid="lab-detach-button"
              >
                {t("detach")}
              </Button>
            )}
          </div>
        )}
        {s.restored && (
          <p
            className="composer-restored"
            role="status"
            data-testid="lab-restored"
          >
            <History size={14} aria-hidden="true" />
            <span>
              {t("restored", {
                time: new Date(s.restored.at).toLocaleString(i18n.language, {
                  dateStyle: "short",
                  timeStyle: "short",
                }),
                model: s.restored.model,
              })}
            </span>
          </p>
        )}
      </div>
      {needsConnection && (
        <Button
          variant="outline"
          onClick={onConfigure}
          data-testid="lab-configure-button"
        >
          {t("configure")}
        </Button>
      )}
      <p className="composer-note">
        <span className="composer-mode" data-testid="lab-composer-mode">
          {s.requiresModel ? t("modeModel") : t("modeLocal")}
        </span>
        {s.requiresModel ? t("noteModel") : t("noteLocal")}
      </p>
    </section>
  );
}
