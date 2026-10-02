import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { FlaskConical } from "lucide-react";
import type { StudioState } from "../../../hooks/useStudio";
import GlideSelect from "../../react-bits/GlideSelect";
import PromptBar from "../../react-bits/PromptBar";
import { pickerColors } from "../../lab/controlColors";
import { Button } from "../../ui/button";

/** Exercise picker, question bar (run / stop) and how this run is executed. */
export function Composer({
  studio: s,
  onConfigure,
  onRun,
}: {
  studio: StudioState;
  onConfigure: () => void;
  onRun: () => void;
}) {
  const { t } = useTranslation("lab", { keyPrefix: "bench.composer" });
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
  return (
    <section className="lab-composer">
      <div className="pane-heading">
        <span>
          <FlaskConical size={17} />
          {t("title")}
        </span>
        <small>LIVE</small>
      </div>
      <p className="pane-description">
        {s.requiresModel
          ? s.detail?.capabilities?.custom_runtime
            ? t("descCustom")
            : t("descModel")
          : t("descLocal")}
      </p>
      <div className="form-field" data-testid="lab-exercise-field">
        <label>{t("exercise")}</label>
        <GlideSelect
          {...pickerColors}
          size="lg"
          className="full-picker"
          ariaLabel={t("exercise")}
          value={s.exerciseId}
          onChange={s.selectExercise}
          disabled={s.running || !s.detail}
          options={exercises.map((e) => ({ value: e.id, label: e.title }))}
        />
      </div>
      <div className="form-field">
        <label htmlFor="lab-question">
          {s.detail?.ui?.question_label || t("question")}
        </label>
        <PromptBar
          className="lab-prompt-bar"
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
          <p id="lab-question-help" className="composer-note">
            {help}
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
        <span className="composer-mode">
          {s.requiresModel ? t("modeModel") : t("modeLocal")}
        </span>
        {s.requiresModel ? t("noteModel") : t("noteLocal")}
      </p>
    </section>
  );
}
