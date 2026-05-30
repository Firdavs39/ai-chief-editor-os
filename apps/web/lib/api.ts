import type {
  AnalyticsResponse,
  CalendarEntry,
  Candidate,
  Channel,
  ChannelCreate,
  ChannelUpdate,
  DryRunPreview,
  GenerationArtifact,
  GenerationRun,
  GenerationRunsCreateResponse,
  GenerationStep,
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

// ---- Quality Editorial Workflow (/generation-runs) -------------------------
// All endpoints require X-Admin-Token. The token lives only in React memory
// (see lib/operator-auth.tsx) and is passed explicitly by the caller. We
// never read it from localStorage / sessionStorage / cookies / URL.

async function runsRequest<T>(
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
    const detail = (body as { detail?: string }).detail ?? "conflict";
    const err = new Error(detail) as Error & { code?: string };
    err.code = "conflict";
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

export const runsApi = {
  create: (
    body: { cluster_id?: string | null; top_n?: number; requested_by?: string },
    adminToken: string,
  ) =>
    runsRequest<GenerationRunsCreateResponse>("/generation-runs", adminToken, {
      method: "POST",
      body: JSON.stringify({ requested_by: "api", ...body }),
    }),
  list: (adminToken: string, status?: string, limit = 50) => {
    const q = new URLSearchParams();
    if (status) q.set("status", status);
    if (limit) q.set("limit", String(limit));
    const qs = q.size ? `?${q.toString()}` : "";
    return runsRequest<GenerationRun[]>(`/generation-runs${qs}`, adminToken);
  },
  get: (id: string, adminToken: string) =>
    runsRequest<GenerationRun>(`/generation-runs/${id}`, adminToken),
  getSteps: (id: string, adminToken: string) =>
    runsRequest<GenerationStep[]>(
      `/generation-runs/${id}/steps`,
      adminToken,
    ),
  getArtifacts: (id: string, adminToken: string) =>
    runsRequest<GenerationArtifact[]>(
      `/generation-runs/${id}/artifacts`,
      adminToken,
    ),
  cancel: (id: string, adminToken: string) =>
    runsRequest<GenerationRun>(`/generation-runs/${id}/cancel`, adminToken, {
      method: "POST",
      body: "{}",
    }),
};

// ---- Channels (multi-channel publishing) -----------------------------------
// Reads (`list`, `get`) are open — consistent with /sources and /trends.
// Mutations carry X-Admin-Token, which the caller pulls from React memory
// (lib/operator-auth.tsx) and passes explicitly. The token is NEVER read from
// localStorage / sessionStorage / cookies / URL.
//
// `target_chat_id` is a PUBLIC channel identifier; a bot token is never sent
// or returned here — it stays in the Vault, resolved via `bot_provider`.

export type ChannelApiError = Error & {
  code?: "admin_token_required" | "admin_token_invalid" | "conflict" | "not_found";
  detail?: string;
};

async function channelsMutate<T>(
  path: string,
  adminToken: string,
  init: RequestInit = {},
): Promise<T> {
  if (!adminToken) {
    const err = new Error("admin_token_required") as ChannelApiError;
    err.code = "admin_token_required";
    throw err;
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
    const err = new Error("admin_token_invalid") as ChannelApiError;
    err.code = "admin_token_invalid";
    throw err;
  }
  if (res.status === 404) {
    const err = new Error("not_found") as ChannelApiError;
    err.code = "not_found";
    throw err;
  }
  if (res.status === 409) {
    const body = await res.json().catch(() => ({}));
    const detail = (body as { detail?: string }).detail ?? "conflict";
    const err = new Error(detail) as ChannelApiError;
    err.code = "conflict";
    err.detail = detail;
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

export const channelsApi = {
  // Open reads.
  list: () => request<Channel[]>("/channels", {}, []),
  get: (id: string) => request<Channel>(`/channels/${id}`),
  // Admin-gated mutations.
  create: (body: ChannelCreate, adminToken: string) =>
    channelsMutate<Channel>("/channels", adminToken, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  update: (id: string, body: ChannelUpdate, adminToken: string) =>
    channelsMutate<Channel>(`/channels/${id}`, adminToken, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  attachSource: (id: string, sourceId: string, adminToken: string) =>
    channelsMutate<Channel>(`/channels/${id}/sources`, adminToken, {
      method: "POST",
      body: JSON.stringify({ source_id: sourceId }),
    }),
  detachSource: (id: string, sourceId: string, adminToken: string) =>
    channelsMutate<void>(`/channels/${id}/sources/${sourceId}`, adminToken, {
      method: "DELETE",
    }),
};
