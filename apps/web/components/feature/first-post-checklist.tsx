import * as React from "react";
import { Check, Circle, ListChecks } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type {
  Candidate,
  ModeFlags,
  PublishJob,
  ReadinessReport,
  Source,
} from "@/lib/types";
import { cn } from "@/lib/utils";

type Step = { key: string; label: string; done: boolean; hint?: string };

export function FirstPostChecklist({
  report,
  candidates,
  sources,
  jobs,
}: {
  report: ReadinessReport | null;
  candidates: Candidate[];
  sources: Source[];
  jobs: PublishJob[];
}) {
  const mode: ModeFlags | undefined = report?.mode;
  const items = report?.sections.flatMap((s) => s.items) ?? [];
  const itemOk = (key: string) =>
    items.some(
      (i) =>
        i.key === key &&
        (i.status === "valid" || i.status === "mock" || i.status === "configured"),
    );

  const liveOn = mode?.live_mode ?? false;
  const dryRun = mode?.dry_run_publish ?? true;
  const publishing = mode?.publishing_enabled ?? false;

  const sourceReady = sources.some((s) => s.enabled);
  const hasCandidate = candidates.length > 0;
  const hasApproved = candidates.some(
    (c) => c.status === "approved" || c.status === "published",
  );
  const hasPublished = jobs.some((j) => j.status === "done");
  const hasDryRun = jobs.some((j) => j.status === "dry_run");

  const tgReady = itemOk("telegram.bot");
  const postizReady = itemOk("postiz.api");

  const steps: Step[] = [
    {
      key: "1",
      label: "Включён боевой режим",
      done: liveOn,
      hint: "Поставьте LIVE_MODE=true в .env, когда будете готовы выйти из демо.",
    },
    {
      key: "2",
      label: "Модель готова",
      done: itemOk("llm.provider"),
      hint: "Заглушка тоже считается. Для реальной — задайте ANTHROPIC_API_KEY или OPENAI_API_KEY.",
    },
    {
      key: "3",
      label: "Есть хотя бы один включённый источник",
      done: sourceReady,
      hint: "Добавьте источник в разделе Источники или запустите демо-данные.",
    },
    {
      key: "4",
      label: "Создан хотя бы один пост",
      done: hasCandidate,
      hint: "Нажмите «Создать пост» в Редакторе.",
    },
    {
      key: "5",
      label: "Настроена публикация (бот Telegram или Postiz)",
      done: tgReady || postizReady,
      hint: "Бот Telegram или Postiz для Threads/Reddit.",
    },
    {
      key: "6",
      label: "Просмотрена тестовая публикация",
      done: hasDryRun || dryRun,
      hint: "Кнопка «Проверить (без отправки)» в редакторе поста.",
    },
    {
      key: "7",
      label: "Есть хотя бы одно одобрение",
      done: hasApproved,
      hint: "Одобрите пост на доске.",
    },
    {
      key: "8",
      label: "PUBLISHING_ENABLED=true (осознанно)",
      done: publishing,
      hint: "Включайте в последнюю очередь. До этого одобренные посты ждут.",
    },
    {
      key: "9",
      label: "Первая реальная публикация отправлена",
      done: hasPublished && publishing && !dryRun,
      hint: "Отправляется, когда все проверки зелёные.",
    },
  ];

  const completed = steps.filter((s) => s.done).length;

  return (
    <Card tone="violet" className="p-4 sm:p-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ListChecks className="h-4 w-4 text-accent-violet" />
          <span className="text-sm font-medium text-ink-50">Чек-лист первой публикации</span>
        </div>
        <Badge variant={completed === steps.length ? "mint" : "violet"}>
          {completed}/{steps.length}
        </Badge>
      </div>
      <ol className="mt-3 space-y-2">
        {steps.map((step, idx) => (
          <li
            key={step.key}
            className="flex items-start gap-3 rounded-lg border border-white/[0.06] bg-white/[0.02] p-2.5"
          >
            <div
              className={cn(
                "mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full",
                step.done
                  ? "bg-state-success/20 text-state-success ring-1 ring-state-success/40"
                  : "bg-white/[0.04] text-ink-500 ring-1 ring-white/[0.06]",
              )}
            >
              {step.done ? <Check className="h-3 w-3" /> : <Circle className="h-2 w-2" />}
            </div>
            <div className="min-w-0">
              <div className="text-[13px] text-ink-100">
                <span className="num text-ink-500 mr-1.5">{String(idx + 1).padStart(2, "0")}</span>
                {step.label}
              </div>
              {step.hint && <div className="text-[11px] text-ink-400 mt-0.5">{step.hint}</div>}
            </div>
          </li>
        ))}
      </ol>
    </Card>
  );
}
