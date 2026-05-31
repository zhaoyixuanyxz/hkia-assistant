export type Message = {
  id: number;
  role: string;
  content: string;
  created_at: string;
};

export type ConversationDetail = {
  id: number;
  title: string;
  status: string;
  is_pinned: boolean;
  pinned_at: string | null;
  created_at: string;
  updated_at: string;
  messages: Message[];
  profile_summary: string;
  profile_structured: Record<string, unknown> | null;
  key_memories: string[];
};

export type ConversationSummary = {
  id: number;
  title: string;
  status: string;
  is_pinned: boolean;
  pinned_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ChartType =
  | "radar"
  | "pie"
  | "donut"
  | "line"
  | "area"
  | "bar"
  | "bar_horizontal"
  | "scatter"
  | "radial_bar"
  | "funnel"
  | "composed"
  | "treemap";

export type ChartSpec = {
  type: ChartType;
  title: string;
  data: { name: string; value: number; value2?: number }[];
};

export type ReportBody = {
  title: string;
  user_background: string;
  insights: string;
  allocation_direction: string;
  product_category_suggestions: string;
  risk_notes: string;
  follow_up_questions: string[];
  charts: ChartSpec[];
  limited_data_notice: string;
  disclaimer: string;
  concrete_product_picks?: {
    product_id: string;
    name: string;
    rationale: string;
    source_url?: string;
  }[];
};

export type ReportResponse = {
  id: number;
  conversation_id: number;
  title: string;
  body: ReportBody;
  disclaimer_text: string;
  created_at: string;
};

export type ConversationSurveyResponse = {
  conversation_id: number;
  answers: Record<string, unknown>;
  template_version: string;
  status: string;
  report_depth: string | null;
  optional_filled_count: number;
  required_complete: boolean;
};

export type SurveyTemplateField = {
  id: string;
  input: string;
  options?: string[] | { value: string; label: string }[];
  placeholder?: string;
  max_len?: number;
};

export type ReportSurveyTemplate = {
  version: string;
  required: SurveyTemplateField[];
  optional: SurveyTemplateField[];
};

export type ProductStub = {
  id: string;
  name: string;
  category: string;
  summary: string;
  source_url: string;
  is_sample: boolean;
  updated_at: string;
  review_status?: string;
  match_score?: number | null;
  match_reason?: string | null;
};

export type ProductDetail = {
  id: string;
  name: string;
  category: string;
  highlights: string;
  coverage_summary: string;
  target_audience: string;
  clause_summary: string;
  source_note: string;
  official_url: string;
  is_sample: boolean;
  updated_at: string;
  review_status: string;
};

export type MarketRow = {
  id: string;
  name: string;
  value: string;
  explanation: string;
  source_url: string;
  updated_at: string;
  trend_note?: string;
};

export type DataUpdateJob = {
  id: number;
  job_type: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  error_message: string;
};
