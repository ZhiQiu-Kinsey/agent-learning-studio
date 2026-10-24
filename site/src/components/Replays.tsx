import { lazy, Suspense, useState } from "react";
import { BadgeCheck, Download } from "lucide-react";
import { useTranslation } from "react-i18next";
import FadeContent from "@studio/components/react-bits/FadeContent";
import recordings from "../generated/recordings.json";
import curriculum from "../generated/curriculum.json";
import type { Curriculum, RecordingEntry, ReplayGroup, SiteLocale } from "../data/types";
import { asset } from "../links";
import { Section } from "./Section";
import { Text } from "./Text";
import { useSiteLocale } from "./useSiteLocale";

// The replay views (stage, timeline, inspector) load with the first replay, not with the page.
const ReplayViewer = lazy(() =>
  import("../replay/ReplayViewer").then((module) => ({ default: module.ReplayViewer })),
);
const groups = recordings as ReplayGroup[];
const lessonTitles = new Map(
  (curriculum as Curriculum).categories.flatMap((category) =>
    category.modules.flatMap((module) =>
      module.lessons.map((lesson) => [lesson.id, lesson.title] as const),
    ),
  ),
);
const RUN_LOCALES: SiteLocale[] = ["zh-CN", "en"];

/** One line of facts read from the recording's metadata and events. */
function Facts({ entry }: { entry: RecordingEntry }) {
  const { t, i18n } = useTranslation("site", { keyPrefix: "replays" });
  const number = new Intl.NumberFormat(i18n.language);
  const { stats } = entry;
  const tokens =
    stats.totalTokens === null
      ? t("facts.notReported")
      : stats.unreported
        ? t("facts.partlyReported", { value: number.format(stats.totalTokens), count: stats.unreported })
        : number.format(stats.totalTokens);
  const rows = [
    ["requests", number.format(stats.requests)],
    ["toolCalls", number.format(stats.toolCalls)],
    ...(stats.approvals ? [["approvals", number.format(stats.approvals)] as const] : []),
    ["tokens", tokens],
  ] as const;
  return (
    <dl className="replay-facts" data-testid="replay-facts" title={t("tokensNote")}>
      {rows.map(([key, value]) => (
        <div key={key}>
          <dt>{t(`facts.${key}`)}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Real run recordings, replayed read-only with the platform's own views. */
export function Replays() {
  const { t, i18n } = useTranslation("site", { keyPrefix: "replays" });
  const locale = useSiteLocale();
  const [groupId, setGroupId] = useState(groups[0]?.id ?? "");
  const [runLocale, setRunLocale] = useState<SiteLocale | null>(null);
  const group = groups.find((item) => item.id === groupId) ?? groups[0];
  if (!group) return null;
  // The run language follows the UI language until the visitor picks one.
  const entry =
    group.recordings[runLocale ?? locale] ??
    RUN_LOCALES.map((code) => group.recordings[code]).find(Boolean)!;
  const { metadata } = entry;
  const shownLocale = metadata.locale as SiteLocale;
  const date = new Intl.DateTimeFormat(i18n.language, {
    dateStyle: "medium",
    timeZone: "UTC",
  }).format(new Date(metadata.recorded_at));
  return (
    <Section id="replays" eyebrow={t("eyebrow")} title={t("title")} lead={t("lead")} wide>
      <div className="replay-picker" role="tablist" aria-label={t("pick")}>
        {groups.map((item) => {
          const title = lessonTitles.get(item.lesson);
          return (
            <button
              key={item.id}
              type="button"
              role="tab"
              id={`replay-tab-${item.id}`}
              aria-selected={item.id === group.id}
              aria-controls="replay-panel"
              data-testid="replay-tab"
              data-replay={item.id}
              onClick={() => setGroupId(item.id)}
            >
              {title && <Text value={title} className="replay-tab-title" />}
              <Text value={item.exerciseTitle} className="replay-tab-exercise" />
            </button>
          );
        })}
      </div>
      <FadeContent
        className="replay-window"
        id="replay-panel"
        role="tabpanel"
        aria-labelledby={`replay-tab-${group.id}`}
        distance={30}
      >
        <div className="replay-window-bar">
          <span className="site-window-dots" aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
          <p className="replay-badge" data-testid="replay-badge">
            <BadgeCheck size={15} aria-hidden="true" />
            {t("badge")}
          </p>
          <p className="replay-meta" data-testid="replay-meta">
            <code>{metadata.model}</code>
            <span>
              {metadata.sdk
                ? t("provider", {
                    provider: metadata.provider_label,
                    name: metadata.sdk.name,
                    version: metadata.sdk.version,
                  })
                : t("providerHttp", { provider: metadata.provider_label })}
            </span>
            <span>{date}</span>
          </p>
          <div className="replay-locale" role="group" aria-label={t("runLanguage")}>
            {RUN_LOCALES.filter((code) => group.recordings[code]).map((code) => (
              <button
                key={code}
                type="button"
                aria-pressed={shownLocale === code}
                data-testid={`replay-locale-${code}`}
                onClick={() => setRunLocale(code)}
              >
                {t(`localeName.${code}`)}
              </button>
            ))}
          </div>
        </div>
        <div className="replay-window-body">
          <div className="replay-summary">
            <Facts entry={entry} />
            <a className="replay-download" href={asset(entry.path)} data-testid="replay-source">
              <Download size={15} aria-hidden="true" />
              {t("source")}
            </a>
          </div>
          {(entry.stats.approvals > 0 || shownLocale !== locale) && (
            <ul className="replay-notes">
              {entry.stats.approvals > 0 && <li>{t("approvals")}</li>}
              {shownLocale !== locale && (
                <li data-testid="replay-locale-note">
                  {t("localeNote", { run: t(`localeName.${shownLocale}`) })}
                </li>
              )}
            </ul>
          )}
          <Suspense
            fallback={
              <p className="replay-status" role="status">
                {t("loading")}
              </p>
            }
          >
            <ReplayViewer entry={entry} inspector={group.inspector} />
          </Suspense>
        </div>
      </FadeContent>
    </Section>
  );
}
