import type { InputSchema } from "./components/lab/SchemaInputs";
import type { LessonContent } from "./content/types.gen";
import type { TRACE_CONTRACT } from "./generated/trace-contract";

export type Exercise = {
  id: string;
  title: string;
  question: string;
  offline_only?: boolean;
  inputs?: Record<string, unknown>;
};
export type Lesson = {
  /** Stable slug, e.g. "tool-selection". */
  id: string;
  /** Display number computed by the server from catalog order. */
  number: number;
  /** Legacy ids (old numeric ids) that the server still resolves. */
  aliases: string[];
  title: string;
  subtitle?: string;
  description: string;
  objectives: string[];
  exercises: Exercise[];
  available: boolean;
  /** Keys resolve only to components included in the frontend build. */
  ui?: {
    guide?: string;
    lab?: string;
    inspector?: string;
    question_label?: string;
    question_help?: string;
  };
  capabilities?: {
    requires_model: boolean;
    custom_runtime: boolean;
    supports_inputs: boolean;
  };
  input_defaults?: Record<string, unknown>;
  /** JSON Schema of a custom runtime's INPUT_MODEL; null for standard lessons. */
  input_schema?: InputSchema | null;
};
export type Detail = Lesson & {
  sources: { path: string; language: string; content: string }[];
  system_prompt: string;
  tools: unknown;
  learning?: LessonContent;
};
export type { LessonContent, QuizQuestion } from "./content/types.gen";
export type Status = {
  model: string;
  api_key_configured: boolean;
  config_ready: boolean;
  requires_api_key?: boolean;
  provider_id?: string;
  provider_label?: string;
  trace_representation?: "http_body" | "sdk_standardized";
};
export type ProviderProfile = {
  id: string;
  label: string;
  model: string;
  api_key_configured: boolean;
  config_ready: boolean;
  requires_api_key?: boolean;
  base_url_configured: boolean;
  supports_custom_base_url: boolean;
};
export type ProviderCatalog = {
  active_provider: string;
  providers: ProviderProfile[];
};
type TraceContract = typeof TRACE_CONTRACT;
export type Provenance = TraceContract["provenances"][number];
export type Representation = TraceContract["representations"][number];
export type SpanKind = TraceContract["span_kinds"][number];
/** v1 信封：旧记录与部分测试夹具只有这些字段。 */
export type TraceV1 = {
  schema_version?: 1;
  type: string;
  round: number | null;
  timestamp: string;
  data: Record<string, unknown>;
};
/** v2 信封：字段由服务端填写，含义见 docs/architecture/event-envelope-v2.md。 */
export type TraceV2 = Omit<TraceV1, "schema_version"> & {
  schema_version: 2;
  run_id: string;
  seq: number;
  span_id: string;
  parent_span_id: string | null;
  span_kind: SpanKind;
  actor: string;
  role: string | null;
  provenance: Provenance;
  /** 只在承载模型请求/响应的事件上有值。 */
  representation: Representation | null;
  /** 只在 sdk_standardized 时有值；测试适配器的 version 为 null。 */
  sdk: { name: string; version: string | null } | null;
};
/** 界面同时接受 v1 与 v2；v2 字段一律按可选读取。 */
export type Trace = Omit<TraceV1, "schema_version"> & {
  schema_version?: number;
} & Partial<Omit<TraceV2, keyof TraceV1>>;
export type RunRecord = {
  run_id: string;
  lesson_id: string;
  exercise_id: string;
  mode: string;
  model: string;
  provider_id: string;
  representation: Representation | null;
  provenance: Provenance;
  schema_version: number;
  status: "running" | "completed" | "error" | "cancelled" | "interrupted";
  created_at: string;
  finished_at: string | null;
  event_count: number;
  last_seq: number;
};
export type Roadmap = {
  id: string;
  title: string;
  description: string;
  available: false;
};
export type CurriculumLesson = {
  id: string;
  number: number;
  aliases: string[];
  title: string;
  category_id: string;
  module_id: string;
  level: string;
  status: "available" | "planned";
  prerequisites: string[];
  summary: string;
  objectives: string[];
  topics: string[];
  experiments: { title: string; steps: string[]; deliverable: string }[];
  acceptance: string[];
  references: { source: string; locator: string }[];
};
export type CurriculumData = {
  title: string;
  version: string;
  categories: {
    id: string;
    title: string;
    description: string;
    modules: {
      id: string;
      title: string;
      description: string;
      lesson_ids: string[];
    }[];
  }[];
  lessons: CurriculumLesson[];
  sources: {
    id: string;
    title: string;
    url: string;
    local_path: string;
    commit: string;
    role: string;
    adaptation: string;
  }[];
  electives: {
    id: string;
    title: string;
    description: string;
    prerequisites: string[];
    topics: string[];
  }[];
  principles: string[];
};
