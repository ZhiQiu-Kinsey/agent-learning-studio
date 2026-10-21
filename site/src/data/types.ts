/** Shapes of the build-time data written by scripts/build-data.mjs. */
export type SiteLocale = "zh-CN" | "en";

/** A text in the source language plus its translation; null when missing or stale. */
export type Localized = { "zh-CN": string } & Partial<Record<SiteLocale, string | null>>;

export interface LessonEntry {
  id: string;
  number: number;
  title: Localized;
  summary: Localized;
  status: string;
  level: "core" | "advanced" | "elective" | null;
  difficulty: "beginner" | "intermediate" | "challenge" | null;
  minutes: number | null;
  prerequisites: string[];
}

export interface ModuleEntry {
  id: string;
  title: Localized;
  description: Localized;
  lessons: LessonEntry[];
}

export interface CategoryEntry {
  id: string;
  title: Localized;
  description: Localized;
  modules: ModuleEntry[];
}

export interface Curriculum {
  version: string;
  lessonCount: number;
  availableCount: number;
  categories: CategoryEntry[];
}

export interface RecordingStats {
  events: number;
  requests: number;
  toolCalls: number;
  approvals: number;
  /** Sum of the provider-reported total_tokens; null when no response reported usage. */
  totalTokens: number | null;
  /** Responses that reported no usage. */
  unreported: number;
}

export interface RecordingEntry {
  lesson: string;
  number: number;
  exercise: string;
  name: string;
  /** Path of the recording file relative to the site's base URL. */
  path: string;
  metadata: {
    model: string;
    provider_label: string;
    representation: "http_body" | "sdk_standardized";
    sdk: { name: string; version: string } | null;
    recorded_at: string;
    locale: string;
    status: string;
    platform_version: string;
    run_id: string;
  };
  stats: RecordingStats;
}

export interface ReplayGroup {
  id: string;
  lesson: string;
  number: number;
  exercise: string;
  exerciseTitle: Localized;
  inspector: string | null;
  recordings: Partial<Record<SiteLocale, RecordingEntry>>;
}
