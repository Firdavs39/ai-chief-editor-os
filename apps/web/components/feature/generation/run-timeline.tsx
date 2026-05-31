"use client";

import * as React from "react";
import Link from "next/link";
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  Circle,
  Clock,
  Loader2,
  MinusCircle,
  Sparkles,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { runsApi } from "@/lib/api";
import { useOperatorToken } from "@/lib/operator-auth";
import type {
  GenerationArtifact,
  GenerationRun,
  GenerationRunStatus,
  GenerationStep,
  GenerationStepStatus,
} from "@/lib/types";
import { cn } from "@/lib/utils";
import { ArtifactCard } from "./artifact-card";
import { GenerateBriefButton } from "./generate-brief-button";

/**
 * Кнопка "Создать заново" для упавшей/остановленной задачи.
 *
 * Безопасность (по требованию): повтор НЕ публикует ничего автоматически — он
 * лишь ставит в очередь новую задачу генерации. Полученный пост всё равно
 * требует ручного одобрения. Поэтому переиспользуем GenerateBriefButton как
 * есть (он создаёт run и переходит на его прогресс).
 */
function RetryButton({ clusterId }: { clusterId: string | null }) {
  return <GenerateBriefButton clusterId={clusterId} label="Создать заново" size="sm" />;
}

/**
 * Polling timeline for a single GenerationRun.
 *
 * - Polls GET /generation-runs/{id} + /steps + /artifacts every 1500ms
 *   while the run is queued or running.
 * - Stops automatically when the run reaches a terminal status. No SSE,
 *   no WebSocket — poll-based design only.
 * - Uses the memory-only operator token (see lib/operator-auth.tsx) for
 *   the X-Admin-Token header on every call.
 * - Cancel button calls POST /generation-runs/{id}/cancel; the worker
 *   honors the flag before the next LLM call.
 */

const POLL_INTERVAL_MS = 1500;
const TERMINAL: ReadonlySet<GenerationRunStatus> = new Set([
  "succeeded",
  "failed",
  "cancelled",
]);

const STEP_LABELS_RU: Record<string, string> = {
  research_analyst: "Исследование источников",
  trend_strategist: "Стратегический угол",
  audience_psychology_analyst: "Психология аудитории",
  platform_writer_telegram: "Текст для Telegram",
  platform_writer_threads: "Текст для Threads",
  platform_writer_reddit: "Текст для Reddit",
  critic_red_team: "Критика и проверка на слабые места",
  editor_in_chief_draft: "Работа главного редактора",
  fact_checker: "Проверка фактов",
  quality_judge: "Оценка качества",
  finalizer: "Финальная сборка",
};

const RUN_STATUS_LABEL_RU: Record<GenerationRunStatus, string> = {
  queued: "В очереди",
  running: "В работе",
  succeeded: "Готово",
  failed: "Ошибка",
  cancelled: "Отменено",
};

const STEP_STATUS_LABEL_RU: Record<GenerationStepStatus, string> = {
  pending: "Ожидает",
  running: "В работе",
  succeeded: "Готово",
  failed: "Ошибка",
  skipped: "Пропущено",
  cancelled: "Отменено",
};

function runBadgeVariant(
  status: GenerationRunStatus,
): "mint" | "cyan" | "violet" | "amber" | "rose" | "outline" {
  if (status === "succeeded") return "mint";
  if (status === "running") return "cyan";
  if (status === "queued") return "violet";
  if (status === "cancelled") return "amber";
  if (status === "failed") return "rose";
  return "outline";
}

function stepIcon(status: GenerationStepStatus) {
  if (status === "succeeded") return CheckCircle2;
  if (status === "running") return Loader2;
  if (status === "failed") return XCircle;
  if (status === "cancelled") return Ban;
  if (status === "skipped") return MinusCircle;
  return Circle;
}

function stepIconClass(status: GenerationStepStatus) {
  if (status === "succeeded") return "text-state-success";
  if (status === "running") return "text-accent-cyan animate-spin";
  if (status === "failed") return "text-state-danger";
  if (status === "cancelled") return "text-accent-amber";
  return "text-ink-400";
}

function formatDuration(ms: number | null) {
  if (ms == null) return "—";
  if (ms < 1000) return `${ms} ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)} с`;
  return `${(ms / 60_000).toFixed(1)} мин`;
}

export function RunTimeline({
  runId,
  initialRun,
}: {
  runId: string;
  initialRun?: GenerationRun | null;
}) {
  const { unlocked, token } = useOperatorToken();

  const [run, setRun] = React.useState<GenerationRun | null>(initialRun ?? null);
  const [steps, setSteps] = React.useState<GenerationStep[]>([]);
  const [artifacts, setArtifacts] = React.useState<GenerationArtifact[]>([]);
  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [cancelling, setCancelling] = React.useState(false);

  const isTerminal = run ? TERMINAL.has(run.status) : false;
  const shouldPoll = unlocked && !!run && !isTerminal;

  const refresh = React.useCallback(async () => {
    if (!token) return;
    try {
      const [r, s, a] = await Promise.all([
        runsApi.get(runId, token),
        runsApi.getSteps(runId, token),
        runsApi.getArtifacts(runId, token),
      ]);
      setRun(r);
      setSteps(s);
      setArtifacts(a);
      setError(null);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
    }
  }, [runId, token]);

  // Initial fetch once unlocked.
  React.useEffect(() => {
    if (!unlocked) return;
    setLoading(true);
    void refresh().finally(() => setLoading(false));
  }, [unlocked, refresh]);

  // Poll while non-terminal. Cleans up on unmount or status change.
  React.useEffect(() => {
    if (!shouldPoll) return;
    const id = window.setInterval(() => {
      void refresh();
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, [shouldPoll, refresh]);

  async function handleCancel() {
    if (!run || !token) return;
    const sure = window.confirm(
      "Остановить создание поста? Текущий шаг завершится, дальше работа не пойдёт.",
    );
    if (!sure) return;
    setCancelling(true);
    try {
      await runsApi.cancel(run.id, token);
      toast.success("Запрос на остановку отправлен");
      await refresh();
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      toast.error("Не удалось остановить", { description: msg.slice(0, 200) });
    } finally {
      setCancelling(false);
    }
  }

  if (!unlocked) {
    return (
      <Card className="p-4 sm:p-5">
        <div className="text-sm text-ink-200">
          Чтобы видеть эту задачу, введите админ-токен.
        </div>
      </Card>
    );
  }

  if (error && !run) {
    return (
      <Card className="p-4 sm:p-5">
        <div className="flex items-center gap-2 text-state-danger">
          <AlertTriangle className="h-4 w-4" />
          <span className="text-sm">{error}</span>
        </div>
      </Card>
    );
  }

  if (loading && !run) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-12 w-full" />
      </div>
    );
  }

  if (!run) return null;

  const candidateHref = run.candidate_id ? `/editor/${run.candidate_id}` : null;
  const progressLabel = `${run.step_index} / ${run.total_steps}`;
  const stepsByIndex = new Map<number, GenerationStep>();
  for (const s of steps) stepsByIndex.set(s.step_index, s);

  return (
    <div className="space-y-4">
      <Card className="p-4 sm:p-5">
        <div className="flex flex-wrap items-start gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-xl bg-accent-violet/15 ring-1 ring-accent-violet/40 shrink-0">
            <Sparkles className="h-4 w-4 text-accent-violet" strokeWidth={2.2} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm font-medium text-ink-50">Создание поста</span>
              <Badge variant={runBadgeVariant(run.status)}>
                {RUN_STATUS_LABEL_RU[run.status]}
              </Badge>
              {run.provider && (
                <Badge variant="outline">
                  модель · {run.provider}
                  {run.model ? ` / ${run.model}` : ""}
                </Badge>
              )}
              <Badge variant="outline">
                <Clock className="h-3 w-3" /> шаг {progressLabel}
              </Badge>
            </div>
            {run.current_step && (
              <div className="mt-1 text-[12px] text-ink-300">
                Сейчас:{" "}
                <span className="text-ink-100">
                  {STEP_LABELS_RU[run.current_step] ?? run.current_step}
                </span>
              </div>
            )}
            {!isTerminal && (
              <div className="mt-1.5 text-[11px] text-ink-500 leading-relaxed">
                Создание занимает ~15–40 минут. Вкладку можно закрыть — прогресс
                не потеряется, готовый пост появится в разделе Редактор.
              </div>
            )}
            {run.status === "failed" && (
              <div className="mt-2 rounded-xl border border-state-danger/30 bg-state-danger/10 p-2.5 text-[12px] text-state-danger">
                <div className="font-medium">
                  Ошибка{run.error_class ? `: ${run.error_class}` : ""}
                </div>
                {run.error_message && (
                  <div className="mt-0.5 text-ink-200 whitespace-pre-wrap break-words">
                    {run.error_message}
                  </div>
                )}
                <div className="mt-1.5 text-ink-300">
                  Можно попробовать создать пост заново — кнопка ниже.
                </div>
              </div>
            )}
            {run.status === "cancelled" && (
              <div className="mt-2 rounded-xl border border-accent-amber/30 bg-accent-amber/10 p-2.5 text-[12px] text-accent-amber">
                Создание остановлено вручную.
              </div>
            )}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {!isTerminal && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleCancel}
                disabled={cancelling}
              >
                {cancelling ? "…" : "Остановить"}
              </Button>
            )}
            {(run.status === "failed" || run.status === "cancelled") && (
              <RetryButton clusterId={run.cluster_id ?? null} />
            )}
            {candidateHref && (
              <Button asChild variant="cyan" size="sm">
                <Link href={candidateHref}>Открыть готовый пост →</Link>
              </Button>
            )}
          </div>
        </div>
      </Card>

      <Card className="p-4 sm:p-5">
        <div className="text-[11px] uppercase tracking-[0.18em] text-ink-400 mb-2">
          Шаги
        </div>
        <div className="space-y-2">
          {Array.from({ length: run.total_steps }).map((_, idx) => {
            const step = stepsByIndex.get(idx);
            const status: GenerationStepStatus = step
              ? step.status
              : idx < run.step_index
              ? "succeeded"
              : "pending";
            const Icon = stepIcon(status);
            const stepName =
              step?.name ??
              [
                "research_analyst",
                "trend_strategist",
                "audience_psychology_analyst",
                "platform_writer_telegram",
                "platform_writer_threads",
                "platform_writer_reddit",
                "critic_red_team",
                "editor_in_chief_draft",
                "fact_checker",
                "quality_judge",
                "finalizer",
              ][idx] ?? `step ${idx}`;
            return (
              <div
                key={idx}
                className="flex items-start gap-3 rounded-xl border border-white/[0.05] bg-white/[0.015] p-3"
              >
                <div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg ring-1 ring-white/[0.05] bg-white/[0.04]">
                  <Icon
                    className={cn("h-4 w-4", stepIconClass(status))}
                    strokeWidth={2.2}
                  />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[13px] font-medium text-ink-50">
                      {idx + 1}. {STEP_LABELS_RU[stepName] ?? stepName}
                    </span>
                    <Badge
                      variant={
                        status === "succeeded"
                          ? "mint"
                          : status === "running"
                          ? "cyan"
                          : status === "failed"
                          ? "rose"
                          : status === "cancelled"
                          ? "amber"
                          : "outline"
                      }
                    >
                      {STEP_STATUS_LABEL_RU[status]}
                    </Badge>
                    {step?.duration_ms != null && (
                      <span className="text-[11px] text-ink-500">
                        {formatDuration(step.duration_ms)}
                      </span>
                    )}
                  </div>
                  {step?.error_message && (
                    <div className="mt-1 text-[11px] text-state-danger break-words">
                      {step.error_class}: {step.error_message}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      {artifacts.length > 0 && (
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-ink-400 mb-2 px-1">
            Артефакты
          </div>
          <div className="grid gap-3 lg:grid-cols-2">
            {artifacts.map((a) => (
              <ArtifactCard key={a.id} artifact={a} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
