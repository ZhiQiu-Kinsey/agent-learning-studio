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
};
export type Detail = Lesson & {
  sources: { path: string; language: string; content: string }[];
  system_prompt: string;
  tools: unknown;
  learning?: LearningContent;
};
export type QuizQuestion = {
  id: string;
  prompt: string;
  options: { id: string; text: string }[];
  correct_option: string;
  explanation: string;
};
export type LearningContent = {
  sections: { title: string; body: string }[];
  observe: string[];
  quiz: QuizQuestion[];
  presentation?: LearningPresentation;
};
export type LearningPresentation = {
  eyebrow: string;
  headline: string;
  highlight: string;
  takeaway: string;
  concepts: {
    label: string;
    title: string;
    description: string;
    token: string;
  }[];
  flow: {
    title: string;
    description: string;
    steps: {
      label: string;
      actor: string;
      title: string;
      body: string;
      code: string;
      language: string;
      evidence: string;
    }[];
  };
};
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
export type Trace = {
  schema_version?: number;
  type: string;
  round: number | null;
  timestamp: string;
  data: Record<string, unknown>;
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
