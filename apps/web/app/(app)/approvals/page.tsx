import * as React from "react";
import Link from "next/link";
import { CheckCircle2, ExternalLink, Shield, Sparkles } from "lucide-react";
import { Topbar } from "@/components/layout/topbar";
import { PageShell, PageSection } from "@/components/layout/page-shell";
import { ApprovalColumn } from "@/components/feature/approval-card";
import { ApprovalActions } from "@/components/feature/approval-actions";
import { UnlockBanner } from "@/components/feature/unlock-banner";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { data } from "@/lib/data";
import { timeAgo } from "@/lib/utils";

export default async function ApprovalsPage() {
  const [candidates, jobs, status] = await Promise.all([
    data.candidates(),
    data.jobs(),
    data.status(),
  ]);
  const pending = candidates.filter((c) => c.status === "draft" || c.status === "revised");
  const approved = candidates.filter((c) => c.status === "approved");
  const published = candidates.filter((c) => c.status === "published");
  const rejected = candidates.filter((c) => c.status === "rejected");

  const candJob: Record<string, string> = {};
  for (const j of jobs) {
    // last job per candidate wins
    candJob[j.candidate_id] = j.status;
  }

  return (
    <>
      <Topbar
        title="На одобрение"
        subtitle="Каждый пост публикуется только после вашего одобрения. Автопостинга нет."
        pill={{ label: `${pending.length} на проверке`, tone: "violet" }}
        actions={
          <Button size="sm" variant="outline" asChild>
            <Link href="/editor">
              <Sparkles className="h-4 w-4" /> Открыть редактор
            </Link>
          </Button>
        }
      />
      <PageShell>
        {/* Плашка разблокировки — Одобрить / Отклонить требуют админ-токен. */}
        <UnlockBanner description="Введите админ-токен (из .env, поле ADMIN_TOKEN), чтобы одобрять и отклонять посты. Просмотр доски работает и без токена." />

        <Card tone="violet" className="overflow-hidden p-4 sm:p-5">
          <div className="flex items-center gap-3 sm:gap-4">
            <div className="grid h-10 w-10 sm:h-11 sm:w-11 place-items-center rounded-xl bg-accent-violet/15 ring-1 ring-accent-violet/40 shrink-0">
              <Shield className="h-4 w-4 sm:h-5 sm:w-5 text-accent-violet" strokeWidth={2.2} />
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-sm sm:text-[15px] font-medium text-ink-50">
                Правило безопасности — без одобрения ничего не публикуется
              </div>
              <div className="text-xs text-ink-400 leading-snug mt-0.5">
                Одобрение ставит пост в очередь публикации. Перед каждой отправкой
                проверка повторяется ещё дважды — три уровня контроля.
              </div>
            </div>
            <Badge variant="violet" className="hidden sm:inline-flex">
              тройная защита
            </Badge>
          </div>
        </Card>

        <PageSection
          title="Поток постов"
          description="Доска: на проверке → одобрено → опубликовано, отклонённые отдельно"
          action={
            <div className="flex items-center gap-2 text-[11px] text-ink-400">
              всего постов <span className="num">{candidates.length}</span>
            </div>
          }
        >
          <div className="flex gap-3 sm:gap-4 overflow-x-auto pb-2 snap-x snap-mandatory lg:grid lg:grid-cols-4 lg:overflow-visible lg:snap-none">
            <ApprovalColumn title="На проверке" tone="amber" badge={pending.length}>
              {pending.map((c) => (
                <Card key={c.id} className="p-4">
                  <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.15em] text-ink-500">
                    <span>{timeAgo(c.created_at)}</span>
                    <span className="ml-auto">v{c.version}</span>
                  </div>
                  <Link
                    href={`/editor/${c.id}`}
                    className="mt-2 block text-sm font-medium text-ink-50 hover:text-white"
                  >
                    {c.topic}
                  </Link>
                  <p className="mt-2 line-clamp-3 text-xs text-ink-300">{c.tg_version}</p>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    <Badge variant="violet">viral {Math.round(c.viral_score * 100)}</Badge>
                    <Badge variant="cyan">style {Math.round(c.style_match_score * 100)}</Badge>
                    {Math.round(c.slop_risk * 100) >= 30 && (
                      <Badge variant="rose">slop {Math.round(c.slop_risk * 100)}</Badge>
                    )}
                  </div>
                  <div className="mt-3">
                    <ApprovalActions candidate={c} />
                  </div>
                </Card>
              ))}
              {pending.length === 0 && (
                <Card className="p-6 text-center text-xs text-ink-400">
                  Нет постов на проверке. Создайте пост в разделе Редактор.
                </Card>
              )}
            </ApprovalColumn>

            <ApprovalColumn title="Одобрено и в очереди" tone="cyan" badge={approved.length}>
              {approved.map((c) => {
                const jobStatus = candJob[c.id];
                const jobMeta = describeJob(jobStatus, status);
                return (
                  <Card key={c.id} className="p-4">
                    <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.15em] text-ink-500">
                      <Badge variant={jobMeta.variant}>{jobMeta.label}</Badge>
                      <span className="ml-auto">v{c.version}</span>
                    </div>
                    <Link
                      href={`/editor/${c.id}`}
                      className="mt-2 block text-sm font-medium text-ink-50 hover:text-white"
                    >
                      {c.topic}
                    </Link>
                    <p className="mt-2 line-clamp-2 text-xs text-ink-300">{c.tg_version}</p>
                    <div className="mt-3 flex items-center gap-2 text-[11px] text-ink-400">
                      <span className={"shrink-0 h-1.5 w-1.5 rounded-full " + jobMeta.dot} />
                      {jobMeta.hint}
                    </div>
                  </Card>
                );
              })}
              {approved.length === 0 && (
                <Card className="p-6 text-center text-xs text-ink-400">
                  В очереди нет одобренных постов.
                </Card>
              )}
            </ApprovalColumn>

            <ApprovalColumn title="Опубликовано" tone="mint" badge={published.length}>
              {published.map((c) => (
                <Card key={c.id} className="p-4">
                  <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.15em] text-ink-500">
                    <Badge variant="mint">
                      <CheckCircle2 className="h-3 w-3" /> published
                    </Badge>
                    <span className="ml-auto">v{c.version}</span>
                  </div>
                  <Link
                    href={`/editor/${c.id}`}
                    className="mt-2 block text-sm font-medium text-ink-50 hover:text-white"
                  >
                    {c.topic}
                  </Link>
                  <p className="mt-2 line-clamp-2 text-xs text-ink-300">{c.tg_version}</p>
                  <div className="mt-3 flex items-center gap-2 text-[11px] text-ink-500">
                    <ExternalLink className="h-3 w-3" />
                    опубликовано в канале
                  </div>
                </Card>
              ))}
              {published.length === 0 && (
                <Card className="p-6 text-center text-xs text-ink-400">
                  Пока ничего не опубликовано.
                </Card>
              )}
            </ApprovalColumn>

            <ApprovalColumn title="Отклонено" tone="rose" badge={rejected.length}>
              {rejected.map((c) => (
                <Card key={c.id} className="p-4 opacity-75">
                  <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.15em] text-ink-500">
                    <Badge variant="rose">отклонён</Badge>
                    <span className="ml-auto">{timeAgo(c.created_at)}</span>
                  </div>
                  <Link
                    href={`/editor/${c.id}`}
                    className="mt-2 block text-sm font-medium text-ink-200 hover:text-white"
                  >
                    {c.topic}
                  </Link>
                  <p className="mt-1.5 line-clamp-2 text-xs text-ink-400">{c.tg_version}</p>
                </Card>
              ))}
              {rejected.length === 0 && (
                <Card className="p-6 text-center text-xs text-ink-400">
                  Отклонённых постов нет.
                </Card>
              )}
            </ApprovalColumn>
          </div>
        </PageSection>
      </PageShell>
    </>
  );
}

type JobMeta = {
  label: string;
  hint: string;
  variant: "cyan" | "violet" | "amber" | "rose" | "mint" | "outline";
  dot: string;
};

function describeJob(jobStatus: string | undefined, status: { publishing_enabled: boolean; dry_run_publish: boolean }): JobMeta {
  if (jobStatus === "blocked") {
    return {
      label: "заблокировано",
      hint: "Публикация выключена (PUBLISHING_ENABLED). Включите её в настройках сервера.",
      variant: "rose",
      dot: "bg-state-danger",
    };
  }
  if (jobStatus === "pending_config") {
    return {
      label: "нет настроек",
      hint: "Для выбранной площадки не настроена публикация.",
      variant: "amber",
      dot: "bg-accent-amber",
    };
  }
  if (jobStatus === "dry_run") {
    return {
      label: "только проверка",
      hint: "Текст подготовлен, но никуда не отправлен (тестовый прогон).",
      variant: "cyan",
      dot: "bg-accent-cyan",
    };
  }
  if (jobStatus === "done") {
    return {
      label: "опубликовано",
      hint: "Опубликовано в канале.",
      variant: "mint",
      dot: "bg-state-success",
    };
  }
  if (jobStatus === "failed") {
    return {
      label: "ошибка",
      hint: "Публикация вернула ошибку — смотрите журнал системы.",
      variant: "rose",
      dot: "bg-state-danger",
    };
  }
  if (!status.publishing_enabled) {
    return {
      label: "в очереди (заблок.)",
      hint: "Главный переключатель выключен — отправки не будет.",
      variant: "amber",
      dot: "bg-accent-amber",
    };
  }
  if (status.dry_run_publish) {
    return {
      label: "в очереди (проверка)",
      hint: "Будет обработано как тестовый прогон — без реальной отправки.",
      variant: "cyan",
      dot: "bg-accent-cyan",
    };
  }
  return {
    label: "в очереди",
    hint: "Сервис опубликует по расписанию.",
    variant: "cyan",
    dot: "bg-accent-cyan",
  };
}
