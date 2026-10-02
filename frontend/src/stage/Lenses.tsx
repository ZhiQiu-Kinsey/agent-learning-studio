import { useTranslation } from "react-i18next";
import type { Trace } from "../types";
import type { FilmRound } from "./derive";

/**
 * Lenses: generic views for the standard teaching event families. The lab picks
 * them from the events a run actually emitted (no per-lesson switches), and each
 * reads only events up to the replay cursor.
 */

type Record = { [key: string]: unknown };
const asRecord = (value: unknown): Record =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record)
    : {};

function TaskCardLens({ event }: { event: Trace }) {
  const { t } = useTranslation("stage", { keyPrefix: "lens.taskCard" });
  const fields = Object.entries(event.data).filter(
    ([, value]) => typeof value === "string",
  );
  const known = (key: string) =>
    t(`fields.${key}` as "fields.goal", { defaultValue: key });
  return (
    <section
      className="lens lens-task-card"
      data-testid="lens-task-card"
      aria-label={t("title")}
    >
      <h3>{t("title")}</h3>
      <dl>
        {fields.map(([key, value]) => (
          <div key={key}>
            <dt>{known(key)}</dt>
            <dd>{String(value)}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

const stringList = (value: unknown): string[] =>
  Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];

/** Scope recall details: which keys came back, which were filtered and why. */
function MemoryDetails({ data }: { data: Record }) {
  const { t, i18n } = useTranslation("stage", { keyPrefix: "lens.memory" });
  const list = new Intl.ListFormat(i18n.language, { type: "conjunction" });
  const included = stringList(data.included);
  const excluded = Array.isArray(data.excluded)
    ? data.excluded.map(asRecord).filter((item) => typeof item.key === "string")
    : [];
  const flagged = stringList(data.flagged);
  return (
    <>
      {typeof data.task_id === "string" && (
        <small>{t("task", { task: data.task_id })}</small>
      )}
      {Array.isArray(data.included) && (
        <span className="lens-memory-keys">
          {t("included", {
            keys: included.length ? list.format(included) : "—",
          })}
        </span>
      )}
      {excluded.map((item) => (
        <span key={String(item.key)} className="lens-memory-keys" data-excluded>
          {t("excluded", {
            key: String(item.key),
            reason: String(item.reason ?? ""),
          })}
        </span>
      ))}
      {flagged.length > 0 && (
        <span className="lens-memory-keys" data-flagged>
          {t("flagged", { keys: list.format(flagged) })}
        </span>
      )}
      {data.sent_to_model === false && <small>{t("notSent")}</small>}
      {typeof data.deleted === "number" && (
        <small>{t("deletedCount", { count: data.deleted })}</small>
      )}
    </>
  );
}

function MemoryLens({ events }: { events: Trace[] }) {
  const { t } = useTranslation("stage", { keyPrefix: "lens.memory" });
  return (
    <section
      className="lens lens-memory"
      data-testid="lens-memory"
      aria-label={t("title")}
    >
      <h3>{t("title")}</h3>
      {events.length ? (
        <ol>
          {events.map((event, index) => {
            const action = String(event.data.action ?? "");
            const record = asRecord(event.data.record);
            const storage =
              typeof event.data.storage === "string"
                ? event.data.storage
                : null;
            return (
              <li key={index} data-action={action}>
                <strong>
                  {t(`actions.${action}` as "actions.saved", {
                    defaultValue: action,
                  })}
                </strong>
                {typeof record.value === "string" && (
                  <span className="lens-memory-value">{record.value}</span>
                )}
                {record.version !== undefined && (
                  <small>v{String(record.version)}</small>
                )}
                {storage && (
                  <small>
                    {t(`storage.${storage}` as "storage.temporary", {
                      defaultValue: storage,
                    })}
                  </small>
                )}
                <MemoryDetails data={event.data} />
              </li>
            );
          })}
        </ol>
      ) : (
        <p>{t("empty")}</p>
      )}
    </section>
  );
}

function BudgetLens({ film, budget }: { film: FilmRound[]; budget: number }) {
  const { t, i18n } = useTranslation("stage", { keyPrefix: "lens.budget" });
  const number = new Intl.NumberFormat(i18n.language);
  const widest = Math.max(
    budget,
    ...film.map((round) =>
      round.messages.reduce((sum, item) => sum + item.chars, 0),
    ),
  );
  return (
    <section
      className="lens lens-budget"
      data-testid="lens-budget"
      aria-label={t("title")}
    >
      <h3>{t("title")}</h3>
      <p className="lens-note">{t("note")}</p>
      <ol>
        {film.map((round) => {
          const chars = round.messages.reduce(
            (sum, item) => sum + item.chars,
            0,
          );
          const over = chars > budget;
          return (
            <li key={round.requestIndex} data-over={over || undefined}>
              <span>{t("round", { round: round.round ?? "—" })}</span>
              <div className="lens-budget-track" aria-hidden="true">
                <i style={{ width: `${(chars / widest) * 100}%` }} />
                <b style={{ left: `${(budget / widest) * 100}%` }} />
              </div>
              <small>
                {t("chars", {
                  chars: number.format(chars),
                  budget: number.format(budget),
                })}{" "}
                · {over ? t("over") : t("within")}
              </small>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

type PlanItem = { id: string; content: string; status: string };

/** Accepts lesson.todo (model-written todos) and lesson.plan (versioned steps). */
const planItems = (data: Record): PlanItem[] => {
  const raw = Array.isArray(data.todos)
    ? data.todos
    : Array.isArray(data.steps)
      ? data.steps
      : [];
  return raw
    .map(asRecord)
    .filter((item) => typeof item.id === "string")
    .map((item) => ({
      id: String(item.id),
      content: String(item.content ?? item.title ?? ""),
      status: String(item.status ?? "pending"),
    }));
};

function PlanLens({ events, injected }: { events: Trace[]; injected: number }) {
  const { t } = useTranslation("stage", { keyPrefix: "lens.plan" });
  const latest = events[events.length - 1];
  const items = planItems(latest.data);
  const changed = new Set(
    (Array.isArray(asRecord(latest.data.diff).changed)
      ? (asRecord(latest.data.diff).changed as unknown[])
      : []
    ).map((item) => String(asRecord(item).id)),
  );
  const reason =
    typeof latest.data.reason === "string" ? latest.data.reason : null;
  return (
    <section
      className="lens lens-plan"
      data-testid="lens-plan"
      aria-label={t("title")}
    >
      <h3>{t("title")}</h3>
      <p className="lens-note">
        {t("version", {
          version: String(latest.data.version ?? events.length),
          count: events.length,
        })}
      </p>
      {reason && <p className="lens-note">{t("reason", { reason })}</p>}
      <ol>
        {items.map((item) => (
          <li
            key={item.id}
            data-status={item.status}
            data-changed={changed.has(item.id) || undefined}
          >
            <small className="lens-plan-status">
              {t(`status.${item.status}` as "status.pending", {
                defaultValue: item.status,
              })}
            </small>
            <span>{item.content}</span>
          </li>
        ))}
      </ol>
      {injected > 0 && (
        <p className="lens-note" data-injected>
          {t("injected", { count: injected })}
        </p>
      )}
    </section>
  );
}

export function Lenses({
  visible,
  film,
}: {
  visible: readonly Trace[];
  film: FilmRound[];
}) {
  const taskCard = visible.findLast(
    (event) => event.type === "lesson.task_card",
  );
  const memory = visible.filter((event) => event.type === "lesson.memory");
  const plan = visible.filter(
    (event) => event.type === "lesson.todo" || event.type === "lesson.plan",
  );
  const injected = visible.filter(
    (event) => event.type === "lesson.harness_injected",
  ).length;
  const hasVariants = visible.some(
    (event) => event.type === "lesson.context_variant",
  );
  const inputs = asRecord(
    visible.find((event) => event.type === "run_start")?.data.inputs,
  );
  const budget =
    typeof inputs.char_budget === "number" ? inputs.char_budget : null;
  const lenses = [
    taskCard && <TaskCardLens key="task" event={taskCard} />,
    memory.length > 0 && <MemoryLens key="memory" events={memory} />,
    plan.length > 0 && (
      <PlanLens key="plan" events={plan} injected={injected} />
    ),
    hasVariants && budget !== null && film.length > 0 && (
      <BudgetLens key="budget" film={film} budget={budget} />
    ),
  ].filter(Boolean);
  if (!lenses.length) return null;
  return <div className="lenses">{lenses}</div>;
}
