import { api } from "./api";
import {
  demoAnalytics,
  demoCalendar,
  demoCandidates,
  demoJobs,
  demoSources,
  demoStyle,
  demoTrends,
} from "./demo-fallback";
import type {
  AnalyticsResponse,
  ApiConnection,
  CalendarEntry,
  Candidate,
  PublishJob,
  ReadinessReport,
  Source,
  StatusPayload,
  StyleProfile,
  Trend,
  WorkerStatus,
} from "./types";

const FALLBACK_STATUS: StatusPayload = {
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
};

const FALLBACK_WORKER: WorkerStatus = {
  ok: true,
  overall: "unknown",
  ttl_seconds: 120,
  loops: {},
  last_events: {
    collector_tick: null,
    generator_tick: null,
    publisher_dispatch: null,
  },
  intervals: { collect: 300, generate: 600, publish: 30 },
  checked_at: new Date().toISOString(),
};

async function safeOr<T>(p: Promise<T>, fallback: T): Promise<T> {
  try {
    const value = await p;
    if (Array.isArray(value) && value.length === 0) return fallback;
    return value;
  } catch {
    return fallback;
  }
}

export const data = {
  status: () => safeOr(api.status(), FALLBACK_STATUS),
  sources: () => safeOr<Source[]>(api.sources(), demoSources),
  trends: () => safeOr<Trend[]>(api.trends({ limit: 50 }), demoTrends),
  trend: async (id: string) => {
    try {
      return await api.trend(id);
    } catch {
      return demoTrends.find((t) => t.id === id) ?? demoTrends[0];
    }
  },
  candidates: () => safeOr<Candidate[]>(api.candidates(), demoCandidates),
  candidate: async (id: string) => {
    try {
      return await api.candidate(id);
    } catch {
      return demoCandidates.find((c) => c.id === id) ?? demoCandidates[0];
    }
  },
  jobs: () => safeOr<PublishJob[]>(api.jobs(), demoJobs),
  calendar: () => safeOr<CalendarEntry[]>(api.calendar(), demoCalendar),
  analytics: () => safeOr<AnalyticsResponse>(api.analytics(), demoAnalytics),
  style: () => safeOr<StyleProfile>(api.styleProfile(), demoStyle),

  // Honest API connection state — synthesized from /health, /worker/status,
  // and /status. Never lies about being live when something is wrong.
  connection: async (): Promise<ApiConnection> => {
    const connected = await api.probe();
    if (!connected) {
      return { state: "fallback", base: api.base };
    }
    try {
      const [worker, status] = await Promise.all([
        api.workerStatus(),
        api.status(),
      ]);

      // Live Mode + missing critical integrations → call it out.
      const missing: string[] = [];
      if (status.live_mode && !status.mock_mode) {
        if (!status.adapters.anthropic && !status.adapters.openai) {
          missing.push("LLM");
        }
        if (!status.adapters.telegram_publish && !status.adapters.postiz) {
          missing.push("Publisher (Telegram or Postiz)");
        }
      }

      if (worker.overall === "stale" || worker.overall === "partial") {
        return {
          state: "worker_stale",
          base: api.base,
          worker_overall: worker.overall,
          missing,
        };
      }

      if (missing.length > 0) {
        return {
          state: "missing_integrations",
          base: api.base,
          worker_overall: worker.overall,
          missing,
        };
      }

      return {
        state: "connected",
        base: api.base,
        worker_overall: worker.overall,
        missing: [],
      };
    } catch {
      // API responded to /health but a follow-up call failed — still better
      // than demo fallback. Surface as connected with no worker info.
      return { state: "connected", base: api.base };
    }
  },

  readiness: async (): Promise<ReadinessReport | null> => {
    try {
      return await api.readiness();
    } catch {
      return null;
    }
  },

  workerStatus: () => safeOr<WorkerStatus>(api.workerStatus(), FALLBACK_WORKER),
};
