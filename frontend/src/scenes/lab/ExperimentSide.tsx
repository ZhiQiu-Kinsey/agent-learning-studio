import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import {
  CircleCheck,
  CircleMinus,
  Compass,
  Lock,
  Play,
  RotateCcw,
} from "lucide-react";
import type { ObserveStatus } from "../../content/guide";
import type { Experiment } from "../../content/types.gen";
import { GlossaryText } from "../../content/glossary/Glossary";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "../../components/ui/accordion";
import { Button } from "../../components/ui/button";
import SparkBurst from "../../components/react-bits/SparkBurst";
import StarBorder from "../../components/react-bits/StarBorder";

/**
 * Beside the experiment card: how many observe points the learner's own run
 * has evidenced, the guided replay over that run, and the conclusion. The
 * conclusion folds (closed by default) and its statements appear only once
 * the run exists.
 */
export function ExperimentSide({
  experiment,
  statuses,
  finished,
  running,
  guiding,
  guidesDone,
  onStartGuide,
}: {
  experiment: Experiment;
  /** Observe points checked against the learner's current run. */
  statuses: ObserveStatus[];
  /** The learner's own run has reached its done event. */
  finished: boolean;
  running: boolean;
  guiding: boolean;
  /** Guides finished on the current run. */
  guidesDone: number;
  onStartGuide: () => void;
}) {
  const { t } = useTranslation("lesson", { keyPrefix: "lab" });
  const { conclusion } = experiment;
  // When a guide ends, keyboard focus comes back to its button (without
  // scrolling: the learner stays on the evidence the guide left them at).
  const startButton = useRef<HTMLButtonElement>(null);
  const wasGuiding = useRef(guiding);
  useEffect(() => {
    if (wasGuiding.current && !guiding)
      startButton.current?.focus({ preventScroll: true });
    wasGuiding.current = guiding;
  }, [guiding]);
  const checkable = statuses.filter((point) => point.status !== "manual");
  const found = checkable.filter((point) => point.status === "found").length;
  const ran = checkable.some((point) => point.status !== "no-run");
  return (
    <section className="experiment-side">
      {checkable.length > 0 && (
        <div className="experiment-evidence" data-ran={ran || undefined}>
          <div className="experiment-evidence-head">
            <span className="experiment-label">{t("evidence.title")}</span>
            <strong>
              {ran ? found : "–"}
              <small>/{checkable.length}</small>
            </strong>
          </div>
          <ol className="experiment-evidence-bar" aria-hidden="true">
            {checkable.map((point) => (
              <li key={point.id} data-status={point.status} />
            ))}
          </ol>
          <p>
            {ran
              ? t("evidence.summary", { found, total: checkable.length })
              : t("evidence.pending")}
          </p>
        </div>
      )}
      {experiment.guide.length > 0 && (
        <div
          className="experiment-guide-start"
          data-ready={(finished && !running) || undefined}
        >
          <span className="experiment-side-icon" aria-hidden="true">
            <Compass size={18} />
            {/* Celebrates a guide the learner just finished on this run. */}
            {guidesDone > 0 && <SparkBurst key={guidesDone} />}
          </span>
          <div>
            <h4>{t("guide.title")}</h4>
            <p>
              {!finished
                ? t("guide.needRun")
                : guidesDone > 0
                  ? t("guide.done")
                  : t("guide.ready", { count: experiment.guide.length })}
            </p>
          </div>
          {finished && !running && !guiding && guidesDone === 0 ? (
            // First guide on a fresh run: a slow star trail invites it.
            <StarBorder
              className="experiment-guide-invite"
              color="var(--role-runtime)"
              speed="6s"
            >
              <Button
                ref={startButton}
                size="sm"
                data-testid="guide-start"
                onClick={onStartGuide}
              >
                <Play size={14} aria-hidden="true" />
                {t("guide.start")}
              </Button>
            </StarBorder>
          ) : (
            <Button
              ref={startButton}
              size="sm"
              variant={guidesDone > 0 ? "outline" : "default"}
              disabled={!finished || running || guiding}
              data-testid="guide-start"
              onClick={onStartGuide}
            >
              {guidesDone > 0 ? (
                <RotateCcw size={14} aria-hidden="true" />
              ) : (
                <Play size={14} aria-hidden="true" />
              )}
              {guidesDone > 0 ? t("guide.again") : t("guide.start")}
            </Button>
          )}
        </div>
      )}
      {conclusion && (
        <Accordion
          type="single"
          collapsible
          className="experiment-conclusion"
          data-testid="experiment-conclusion"
          data-open={finished || undefined}
        >
          <AccordionItem value="conclusion" className="border-b-0">
            <AccordionTrigger
              className="experiment-conclusion-trigger py-0 hover:no-underline"
              data-testid="experiment-conclusion-toggle"
            >
              <span>
                <span className="experiment-conclusion-title">
                  {t("conclusion.title")}
                </span>
                <small>
                  {t("conclusion.summary", {
                    proves: conclusion.proves.length,
                    limits: conclusion.does_not_prove.length,
                  })}
                </small>
              </span>
            </AccordionTrigger>
            <AccordionContent className="experiment-conclusion-body pb-0">
              {finished ? (
                <>
                  {conclusion.proves.length > 0 && (
                    <div
                      className="experiment-conclusion-group"
                      data-kind="proves"
                    >
                      <strong>{t("conclusion.proves")}</strong>
                      <ul>
                        {conclusion.proves.map((item, index) => (
                          <li key={index}>
                            <CircleCheck size={15} aria-hidden="true" />
                            <span>
                              <GlossaryText text={item} />
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {conclusion.does_not_prove.length > 0 && (
                    <div
                      className="experiment-conclusion-group"
                      data-kind="limits"
                    >
                      <strong>{t("conclusion.doesNotProve")}</strong>
                      <ul>
                        {conclusion.does_not_prove.map((item, index) => (
                          <li key={index}>
                            <CircleMinus size={15} aria-hidden="true" />
                            <span>
                              <GlossaryText text={item} />
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </>
              ) : (
                <>
                  {/* Placeholder rows, one per authored statement; no text until the run exists. */}
                  <div
                    className="experiment-conclusion-preview"
                    aria-hidden="true"
                  >
                    {(
                      [
                        [
                          "proves",
                          conclusion.proves.length,
                          "conclusion.proves",
                        ],
                        [
                          "limits",
                          conclusion.does_not_prove.length,
                          "conclusion.doesNotProve",
                        ],
                      ] as const
                    ).map(([kind, count, label]) =>
                      count > 0 ? (
                        <div key={kind} data-kind={kind}>
                          <strong>{t(label)}</strong>
                          {Array.from({ length: count }, (_, index) => (
                            <i key={index} />
                          ))}
                        </div>
                      ) : null,
                    )}
                  </div>
                  <p className="experiment-conclusion-locked">
                    <Lock size={14} aria-hidden="true" />
                    <span>
                      {t("conclusion.needRun")}
                      <small>
                        {t("conclusion.waiting", {
                          proves: conclusion.proves.length,
                          limits: conclusion.does_not_prove.length,
                        })}
                      </small>
                    </span>
                  </p>
                </>
              )}
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      )}
    </section>
  );
}
