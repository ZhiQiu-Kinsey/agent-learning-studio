import { AnimatePresence, motion } from "motion/react";
import {
  CheckCircle2,
  CircleHelp,
  ClipboardCheck,
  ExternalLink,
  XCircle,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { useReducedMotion } from "../../motion";
import type { InspectorExtensionProps } from "../types";
import { Button } from "../../components/ui/button";
import "./evidence-board.css";

const record = (value: unknown): value is Record<string, unknown> =>
  !!value && typeof value === "object" && !Array.isArray(value);
const text = (value: unknown, fallback = "") =>
  typeof value === "string"
    ? value
    : typeof value === "number" || typeof value === "boolean"
      ? String(value)
      : fallback;

/** One report contract serves validation, experiments, state, context and memory. */
export default function EvidenceBoard({
  studio,
  children,
}: InspectorExtensionProps) {
  const { t } = useTranslation("lab", { keyPrefix: "evidence" });
  const reduced = useReducedMotion();
  const reports = studio.visible
    .map((event, index) => ({ event, index }))
    .filter(({ event }) => event.type === "lesson.report");
  const selected =
    reports.find(({ event }) => event === studio.active) || reports.at(-1);
  const report = selected?.event.data;
  const checks = Array.isArray(report?.checks)
    ? report.checks.filter(record)
    : [];
  const metrics = Array.isArray(report?.metrics)
    ? report.metrics.filter(record)
    : [];
  const table = record(report?.table) ? report.table : null;
  const columns = Array.isArray(table?.columns)
    ? table.columns.filter(
        (column): column is string => typeof column === "string",
      )
    : [];
  const rows = Array.isArray(table?.rows)
    ? table.rows.filter(Array.isArray)
    : [];
  return (
    <>
      {children}
      <section
        className="evidence-board"
        aria-label={t("region")}
        data-evidence-board=""
      >
        <header className="evidence-board-heading">
          <span>
            <ClipboardCheck size={17} />
            {t("title")}
          </span>
          <small>{t("sync")}</small>
        </header>
        {!selected || !report ? (
          <p className="evidence-board-empty">{t("empty")}</p>
        ) : (
          <>
            {reports.length > 1 && (
              <nav className="evidence-report-tabs" aria-label={t("switch")}>
                {reports.map(({ event, index }, number) => (
                  <button
                    type="button"
                    key={index}
                    aria-pressed={selected.index === index}
                    onClick={() => studio.selectEvent(index)}
                  >
                    {text(event.data.title, t("reportN", { n: number + 1 }))}
                  </button>
                ))}
              </nav>
            )}
            <AnimatePresence mode="wait" initial={false}>
              <motion.div
                key={selected.index}
                className="evidence-report"
                data-testid="evidence-report"
                initial={reduced ? false : { opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={reduced ? {} : { opacity: 0 }}
                transition={{ duration: reduced ? 0 : 0.18 }}
              >
                <div className="evidence-report-title">
                  <h3>{text(report.title, t("defaultTitle"))}</h3>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => studio.selectEvent(selected.index)}
                    aria-label={t("rawLabel")}
                  >
                    <ExternalLink size={13} />
                    {t("raw")}
                  </Button>
                </div>
                {typeof report.summary === "string" && (
                  <p className="evidence-report-summary">{report.summary}</p>
                )}
                {!!metrics.length && (
                  <dl className="evidence-metrics">
                    {metrics.slice(0, 12).map((metric, index) => (
                      <div key={index}>
                        <dt>
                          {text(metric.label, t("metricN", { n: index + 1 }))}
                        </dt>
                        <dd>{text(metric.value, t("notProvided"))}</dd>
                      </div>
                    ))}
                  </dl>
                )}
                {!!checks.length && (
                  <ul className="evidence-checks" data-testid="evidence-checks">
                    {checks.slice(0, 24).map((check, index) => {
                      const passed =
                        typeof check.passed === "boolean"
                          ? check.passed
                          : undefined;
                      const Icon =
                        passed === true
                          ? CheckCircle2
                          : passed === false
                            ? XCircle
                            : CircleHelp;
                      return (
                        <li
                          key={index}
                          data-verdict={
                            passed === true
                              ? "passed"
                              : passed === false
                                ? "failed"
                                : "unknown"
                          }
                        >
                          <Icon size={16} aria-hidden="true" />
                          <div>
                            <strong>
                              {text(check.label, t("checkN", { n: index + 1 }))}
                            </strong>
                            {typeof check.detail === "string" && (
                              <p>{check.detail}</p>
                            )}
                          </div>
                          <span>
                            {passed === true
                              ? t("passed")
                              : passed === false
                                ? t("failed")
                                : t("undecided")}
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                )}
                {!!columns.length && (
                  <div className="evidence-table-wrap">
                    <table>
                      <thead>
                        <tr>
                          {columns.map((column, index) => (
                            <th key={index}>{column}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {rows.slice(0, 40).map((row, index) => (
                          <tr key={index}>
                            {columns.map((_, cell) => (
                              <td key={cell}>{text(row[cell], "—")}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                {(rows.length > 40 ||
                  metrics.length > 12 ||
                  checks.length > 24) && (
                  <p className="evidence-report-note">{t("truncated")}</p>
                )}
              </motion.div>
            </AnimatePresence>
          </>
        )}
      </section>
    </>
  );
}
