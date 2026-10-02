import { useTranslation } from "react-i18next";
import { Play } from "lucide-react";
import type { Experiment } from "../../content/types.gen";
import { Button } from "../../components/ui/button";

/**
 * Beside the experiment card: start the guided replay over the learner's own
 * finished run, and the conclusion, which only opens once that run exists.
 */
export function ExperimentSide({
  experiment,
  finished,
  running,
  guiding,
  onStartGuide,
}: {
  experiment: Experiment;
  /** The learner's own run has reached its done event. */
  finished: boolean;
  running: boolean;
  guiding: boolean;
  onStartGuide: () => void;
}) {
  const { t } = useTranslation("lesson", { keyPrefix: "lab" });
  const { conclusion } = experiment;
  return (
    <section className="experiment-side">
      {experiment.guide.length > 0 && (
        <div className="experiment-guide-start">
          <Button
            size="sm"
            disabled={!finished || running || guiding}
            data-testid="guide-start"
            onClick={onStartGuide}
          >
            <Play size={14} aria-hidden="true" />
            {t("guide.start")}
          </Button>
          {!finished && <small>{t("guide.needRun")}</small>}
        </div>
      )}
      {conclusion && (
        <div
          className="experiment-conclusion"
          data-testid="experiment-conclusion"
        >
          <h4>{t("conclusion.title")}</h4>
          {finished ? (
            <>
              {conclusion.proves.length > 0 && (
                <>
                  <strong>{t("conclusion.proves")}</strong>
                  <ul>
                    {conclusion.proves.map((item, index) => (
                      <li key={index}>{item}</li>
                    ))}
                  </ul>
                </>
              )}
              {conclusion.does_not_prove.length > 0 && (
                <>
                  <strong>{t("conclusion.doesNotProve")}</strong>
                  <ul>
                    {conclusion.does_not_prove.map((item, index) => (
                      <li key={index}>{item}</li>
                    ))}
                  </ul>
                </>
              )}
            </>
          ) : (
            <p>{t("conclusion.needRun")}</p>
          )}
        </div>
      )}
    </section>
  );
}
