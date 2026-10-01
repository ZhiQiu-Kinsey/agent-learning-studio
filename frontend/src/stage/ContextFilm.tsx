import { useTranslation } from "react-i18next";
import type { FilmRound } from "./derive";

const knownRoles = new Set(["system", "user", "assistant", "tool"]);

/** Usage is shown only as reported by the response, key by key, never estimated. */
function UsageLine({ usage }: { usage: Record<string, unknown> }) {
  const entries = Object.entries(usage).filter(
    ([, value]) => typeof value === "number" || typeof value === "string",
  );
  return (
    <dl className="film-usage">
      {entries.map(([key, value]) => (
        <div key={key}>
          <dt>{key}</dt>
          <dd>{String(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

export function ContextFilm({
  film,
  onSelect,
}: {
  film: FilmRound[];
  onSelect?: (eventIndex: number) => void;
}) {
  const { t, i18n } = useTranslation("stage", { keyPrefix: "film" });
  const number = new Intl.NumberFormat(i18n.language);
  if (!film.length)
    return (
      <section
        className="context-film is-empty"
        aria-label={t("region")}
        data-testid="context-film"
      >
        <p>{t("empty")}</p>
      </section>
    );
  const widest = Math.max(
    1,
    ...film.map((round) =>
      round.messages.reduce((sum, item) => sum + item.chars, 0),
    ),
  );
  return (
    <section
      className="context-film"
      aria-label={t("region")}
      data-testid="context-film"
    >
      <ol>
        {film.map((round) => {
          const total = round.messages.reduce(
            (sum, item) => sum + item.chars,
            0,
          );
          const added = round.messages.filter((item) => item.isNew).length;
          return (
            <li key={round.requestIndex} data-testid="film-round">
              <button
                type="button"
                className="film-heading"
                onClick={() => onSelect?.(round.requestIndex)}
              >
                <strong>{t("round", { round: round.round ?? "—" })}</strong>
                <span>{t("messages", { count: round.messages.length })}</span>
                {added > 0 && (
                  <span className="film-added">
                    {t("new", { count: added })}
                  </span>
                )}
                <span>{t("chars", { value: number.format(total) })}</span>
              </button>
              <div
                className="film-strip"
                style={{ width: `${Math.max(8, (total / widest) * 100)}%` }}
              >
                {round.messages.map((message, index) => (
                  <span
                    key={index}
                    className="film-cell"
                    data-role={
                      knownRoles.has(message.role) ? message.role : "unknown"
                    }
                    data-new={message.isNew || undefined}
                    style={{ flexGrow: Math.max(message.chars, 1) }}
                    title={`${t(`role.${knownRoles.has(message.role) ? message.role : "unknown"}` as "role.unknown")} · ${number.format(message.chars)}`}
                  />
                ))}
              </div>
              {round.usage ? (
                <div className="film-usage-wrap">
                  <small>{t("usage")}</small>
                  <UsageLine usage={round.usage} />
                </div>
              ) : (
                <small className="film-note">{t("charsNote")}</small>
              )}
            </li>
          );
        })}
      </ol>
      <ul className="film-legend" aria-hidden="true">
        {[...knownRoles].map((role) => (
          <li key={role} data-role={role}>
            {t(`role.${role}` as "role.unknown")}
          </li>
        ))}
      </ul>
    </section>
  );
}
