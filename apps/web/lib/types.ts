// Mirrors backend Pydantic schemas (apps/api/app/schemas/common.py).

export type CapabilityFlags = {
  anthropic: boolean;
  openai: boolean;
  telethon: boolean;
  reddit: boolean;
  telegram_publish: boolean;
  postiz: boolean;
};

export type StatusPayload = {
  ok: boolean;
  app_env: string;
  mock_mode: boolean;
  demo_mode: boolean;
  live_mode: boolean;
  dry_run_publish: boolean;
  publishing_enabled: boolean;
  llm_provider: string;
  timezone: string;
  adapters: CapabilityFlags;
};

export type ReadinessStatus =
  | "mock"
  | "missing_config"
  | "configured"
  | "valid"
  | "invalid"
  | "error"
  | "disabled"
  | "unavailable";

export type ReadinessSeverity = "info" | "success" | "warning" | "danger";

export type ReadinessItem = {
  key: string;
  label: string;
  status: ReadinessStatus;
  severity: ReadinessSeverity;
  message: string;
  missing_env_vars: string[];
  safe_details: Record<string, unknown>;
  last_checked_at: string | null;
  can_test: boolean;
  docs_hint: string;
  next_action: string;
};

export type ReadinessSection = {
  key: string;
  label: string;
  items: ReadinessItem[];
};

export type ModeFlags = {
  app_env: string;
  mock_mode: boolean;
  demo_mode: boolean;
  live_mode: boolean;
  dry_run_publish: boolean;
  publishing_enabled: boolean;
};

export type ReadinessReport = {
  generated_at: string;
  mode: ModeFlags;
  sections: ReadinessSection[];
  overall_score: number;
  overall_label: "ready" | "close" | "partial" | "demo";
};

export type WorkerLoopStatus = {
  last_at: string | null;
  last_event: string;
  age_seconds: number;
  fresh: boolean;
  counter: number;
};

export type WorkerStatus = {
  ok: boolean;
  overall: "running" | "partial" | "stale" | "unknown";
  ttl_seconds: number;
  loops: Record<string, WorkerLoopStatus>;
  last_events: {
    collector_tick: string | null;
    generator_tick: string | null;
    publisher_dispatch: string | null;
  };
  intervals: { collect: number; generate: number; publish: number };
  checked_at: string;
};

/**
 * Composite connection state surfaced in the UI.
 *
 * `fallback`           — API not reachable; lib/demo-fallback drives the screens.
 * `connected`          — API reachable, worker fresh, integrations enough for Live.
 * `worker_stale`       — API reachable, worker heartbeat older than TTL.
 * `missing_integrations` — API reachable, worker fresh, but Live Mode is on and
 *                        critical integrations (LLM / publisher) are missing.
 */
export type ApiConnectionState =
  | "fallback"
  | "connected"
  | "worker_stale"
  | "missing_integrations";

export type ApiConnection = {
  state: ApiConnectionState;
  base: string;
  worker_overall?: WorkerStatus["overall"];
  missing?: string[];
};

export type DryRunPreview = {
  ok: boolean;
  preview: {
    platform: string;
    scheduled_at: string | null;
    candidate_id: string;
    candidate_version: number;
    candidate_status: string;
    body: string;
    body_length: number;
    cta: string;
    topic: string;
    limits: { max_length: number };
    safety: { publishing_enabled: boolean; dry_run_publish: boolean; mock_mode: boolean };
    dry_run: boolean;
    would_send: boolean;
    [k: string]: unknown;
  };
  safety_note: string;
};

export type Source = {
  id: string;
  kind: "telegram" | "reddit" | "rss" | "manual";
  handle: string;
  url: string;
  title: string;
  weight: number;
  enabled: boolean;
  last_collected_at: string | null;
  health: Record<string, unknown>;
  created_at: string;
};

export type Trend = {
  id: string;
  representative_text: string;
  keywords: string[];
  category: string;
  signal_count: number;
  first_seen_at: string | null;
  last_seen_at: string | null;
  score_breakdown: Record<string, number>;
  total_score: number;
  sources_summary: { handle: string; count: number }[];
};

export type CriticNote = {
  check: string;
  severity: "low" | "medium" | "high";
  note: string;
};

export type Candidate = {
  id: string;
  cluster_id: string | null;
  topic: string;
  source_summary: string;
  why_it_matters: string;
  psychology_hook: string;
  tg_version: string;
  threads_version: string;
  reddit_version: string;
  cta: string;
  style_match_score: number;
  viral_score: number;
  slop_risk: number;
  controversy_risk: number;
  recommendation: "approve" | "revise" | "reject";
  critic_notes: CriticNote[];
  status: "draft" | "approved" | "rejected" | "revised" | "published";
  version: number;
  created_at: string;
};

export type PublishJob = {
  id: string;
  candidate_id: string;
  approval_id: string;
  platform: "telegram" | "threads" | "reddit" | "mock";
  scheduled_at: string;
  status:
    | "pending"
    | "running"
    | "done"
    | "failed"
    | "blocked"
    | "dry_run"
    | "pending_config";
  idempotency_key: string;
  created_at: string;
};

export type CalendarEntry = {
  job_id: string;
  candidate_id: string;
  topic: string;
  platform: string;
  scheduled_at: string;
  status: string;
  cta: string;
  tg_preview: string;
  threads_preview: string;
};

export type StyleProfile = {
  id: string;
  name: string;
  tone: string;
  audience: string;
  banned_phrases: string[];
  example_posts: string[];
  writing_rules: string;
  target_topics: string[];
  voice_sliders: Record<string, number>;
  lang_primary: string;
  updated_at: string;
};

// --- Integration Secrets Vault ----------------------------------------------

export type VaultSource = "env" | "vault" | "missing" | "env+vault";

export type VaultFieldStatus = {
  key_name: string;
  label: string;
  is_secret: boolean;
  required: boolean;
  env_var: string;
  placeholder: string;
  source: "env" | "vault" | "missing";
  advanced: boolean;
  safe_metadata: Record<string, unknown>;
};

export type VaultProviderSummary = {
  provider: string;
  label: string;
  docs_anchor: string;
  status: string;
  last_tested_at: string | null;
  last_test_message: string;
  fields: VaultFieldStatus[];
  can_test: boolean;
  source: VaultSource;
};

export type VaultListResponse = {
  vault_enabled: boolean;
  admin_token_required: boolean;
  providers: VaultProviderSummary[];
};

export type AnalyticsResponse = {
  by_hook_type: { hook_type: string; posts: number; viral_avg: number; reach_avg: number }[];
  by_source: { source: string; posts: number; avg_engagement: number; avg_style_match: number }[];
  best_patterns: { title: string; detail: string; kind: string }[];
  learning_timeline: { date: string; posts: number; avg_engagement: number }[];
  totals: {
    candidates: number;
    approved: number;
    rejected: number;
    scheduled: number;
    published: number;
    sources: number;
  };
};
