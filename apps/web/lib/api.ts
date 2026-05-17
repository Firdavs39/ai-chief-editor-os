import type {
  AnalyticsResponse,
  CalendarEntry,
  Candidate,
  DryRunPreview,
  PublishJob,
  ReadinessItem,
  ReadinessReport,
  Source,
  StatusPayload,
  StyleProfile,
  Trend,
  VaultListResponse,
  VaultProviderSummary,
  WorkerStatus,
} from "./types";

const API_BASE =
  (typeof window === "undefined"
    ? process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_URL
    : process.env.NEXT_PUBLIC_API_URL) || "http://localhost:8000";

async function request<T>(
  path: string,
  init: RequestInit = {},
  fallback?: T,
): Promise<T> {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init.headers || {}),
      },
      cache: "no-store",
    });
    if (!res.ok) {
      throw new Error(`${res.status} ${res.statusText}`);
    }
    if (res.status === 204) {
      return undefined as unknown as T;
    }
    return (await res.json()) as T;
  } catch (err) {
    if (fallback !== undefined) {
      return fallback;
    }
    throw err;
  }
}

export const api = {
  base: API_BASE,
  status: () =>
    request<StatusPayload>("/status", {}, {
      ok: true,
      app_env: "dev",
      mock_mode: true,
      demo_mode: true,
      live_mode: false,
      dry_run_publish: true,
      publishing_enabled: false,
      llm_provider: "mock",
      timezone: "Asia/Tashkent",
      adapters: {
        anthropic: false,
        openai: false,
        telethon: false,
        reddit: false,
        telegram_publish: false,
        postiz: false,
      },
    }),
  sources: () => request<Source[]>("/sources", {}, []),
  createSource: (body: Partial<Source>) =>
    request<Source>("/sources", { method: "POST", body: JSON.stringify(body) }),
  deleteSource: (id: string) =>
    request<void>(`/sources/${id}`, { method: "DELETE" }),
  trends: (params: { limit?: number; min_score?: number; category?: string } = {}) => {
    const q = new URLSearchParams();
    if (params.limit) q.set("limit", String(params.limit));
    if (params.min_score !== undefined) q.set("min_score", String(params.min_score));
    if (params.category) q.set("category", params.category);
    return request<Trend[]>(`/trends${q.size ? `?${q.toString()}` : ""}`, {}, []);
  },
  trend: (id: string) => request<Trend>(`/trends/${id}`),
  candidates: (status?: Candidate["status"]) => {
    const q = status ? `?status=${status}` : "";
    return request<Candidate[]>(`/candidates${q}`, {}, []);
  },
  candidate: (id: string) => request<Candidate>(`/candidates/${id}`),
  rewrite: (id: string, mode: string, target: string) =>
    request<Candidate>(`/candidates/${id}/rewrite`, {
      method: "POST",
      body: JSON.stringify({ mode, target }),
    }),
  approve: (id: string, body: { reason?: string; scheduled_at?: string; platform?: string }) =>
    request<{ approval_id: string; job: PublishJob; candidate: Candidate }>(
      `/approvals/${id}/approve`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  reject: (id: string, body: { reason?: string }) =>
    request<Candidate>(`/approvals/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ ...body, platform: "mock" }),
    }),
  jobs: (status?: PublishJob["status"]) => {
    const q = status ? `?status=${status}` : "";
    return request<PublishJob[]>(`/publishing/jobs${q}`, {}, []);
  },
  createJob: (body: { candidate_id: string; platform?: string; scheduled_at?: string }) =>
    request<PublishJob>("/publishing/jobs", { method: "POST", body: JSON.stringify(body) }),
  calendar: (since?: string, until?: string) => {
    const q = new URLSearchParams();
    if (since) q.set("since", since);
    if (until) q.set("until", until);
    return request<CalendarEntry[]>(
      `/calendar${q.size ? `?${q.toString()}` : ""}`,
      {},
      [],
    );
  },
  analytics: () =>
    request<AnalyticsResponse>("/analytics", {}, {
      by_hook_type: [],
      by_source: [],
      best_patterns: [],
      learning_timeline: [],
      totals: {
        candidates: 0,
        approved: 0,
        rejected: 0,
        scheduled: 0,
        published: 0,
        sources: 0,
      },
    }),
  styleProfile: () =>
    request<StyleProfile>("/style-profile", {}, {
      id: "",
      name: "default",
      tone: "",
      audience: "",
      banned_phrases: [],
      example_posts: [],
      writing_rules: "",
      target_topics: [],
      voice_sliders: {},
      lang_primary: "ru",
      updated_at: new Date().toISOString(),
    }),
  saveStyleProfile: (body: Omit<StyleProfile, "id" | "name" | "updated_at">) =>
    request<StyleProfile>("/style-profile", {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  collectRun: () => request<{ triggered: boolean; sources: number; queued: number; note: string }>(
    "/collect/run",
    { method: "POST", body: JSON.stringify({}) },
  ),
  briefGenerate: (top_n = 3) =>
    request<Candidate[]>("/brief/generate", {
      method: "POST",
      body: JSON.stringify({ top_n }),
    }),
  demoSeed: () => request<{ ok: boolean; summary: Record<string, number> }>(
    "/demo/seed",
    { method: "POST", body: "{}" },
  ),

  // ---- Live Mode Readiness ---------------------------------------------------
  readiness: () => request<ReadinessReport>("/readiness"),
  testLlm: () =>
    request<ReadinessItem>("/readiness/test-llm", { method: "POST", body: "{}" }),
  testTelegramBot: () =>
    request<ReadinessItem>("/readiness/test-telegram-bot", {
      method: "POST",
      body: "{}",
    }),
  testTelethon: () =>
    request<ReadinessItem>("/readiness/test-telethon", { method: "POST", body: "{}" }),
  testReddit: () =>
    request<ReadinessItem>("/readiness/test-reddit", { method: "POST", body: "{}" }),
  testPostiz: () =>
    request<ReadinessItem>("/readiness/test-postiz", { method: "POST", body: "{}" }),
  testSource: (id: string) =>
    request<ReadinessItem>(`/readiness/test-source/${id}`, {
      method: "POST",
      body: "{}",
    }),
  dryRunPublish: (candidateId: string, platform = "telegram") =>
    request<DryRunPreview>(
      `/readiness/dry-run-publish/${candidateId}?platform=${platform}`,
      { method: "POST", body: "{}" },
    ),
  workerStatus: () => request<WorkerStatus>("/worker/status"),

  // Connection honesty — used by Vercel-hosted UI to know if it's hitting
  // a real API or falling back to demo data.
  probe: async () => {
    try {
      const res = await fetch(`${API_BASE}/health`, { cache: "no-store" });
      return res.ok;
    } catch {
      return false;
    }
  },
};

// ---- Integration Secrets Vault ---------------------------------------------
// Admin token is passed in by the caller from React state. It is NEVER stored
// in localStorage/sessionStorage/cookies/URL — refresh clears it intentionally.

async function vaultRequest<T>(
  path: string,
  adminToken: string,
  init: RequestInit = {},
): Promise<T> {
  if (!adminToken) {
    throw new Error("admin_token_required");
  }
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Admin-Token": adminToken,
      ...(init.headers || {}),
    },
    cache: "no-store",
  });
  if (res.status === 401) {
    throw new Error("admin_token_invalid");
  }
  if (res.status === 409) {
    const body = await res.json().catch(() => ({}));
    const detail = body?.detail ?? {};
    const err = new Error(detail?.reason || "vault_disabled");
    (err as Error & { code?: string; detail?: unknown }).code = "vault_disabled";
    (err as Error & { code?: string; detail?: unknown }).detail = detail;
    throw err;
  }
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${body.slice(0, 200)}`);
  }
  if (res.status === 204) {
    return undefined as unknown as T;
  }
  return (await res.json()) as T;
}

export const vaultApi = {
  list: (adminToken: string) =>
    vaultRequest<VaultListResponse>("/secrets/integrations", adminToken),
  get: (provider: string, adminToken: string) =>
    vaultRequest<VaultProviderSummary>(`/secrets/${provider}`, adminToken),
  save: (
    provider: string,
    values: Record<string, string>,
    adminToken: string,
  ) =>
    vaultRequest<VaultProviderSummary>(`/secrets/${provider}`, adminToken, {
      method: "POST",
      body: JSON.stringify({ values }),
    }),
  delete: (provider: string, keyName: string, adminToken: string) =>
    vaultRequest<VaultProviderSummary>(
      `/secrets/${provider}/${keyName}`,
      adminToken,
      { method: "DELETE" },
    ),
  test: (provider: string, adminToken: string) =>
    vaultRequest<ReadinessItem>(`/secrets/${provider}/test`, adminToken, {
      method: "POST",
      body: "{}",
    }),
};
