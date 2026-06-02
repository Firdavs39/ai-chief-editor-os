import * as React from "react";
import Link from "next/link";
import {
  Activity,
  Calendar as CalendarIcon,
  CheckCircle2,
  Compass,
  Flame,
  Lightbulb,
  Radio,
  Zap,
} from "lucide-react";
import { Topbar } from "@/components/layout/topbar";
import { PageShell, PageSection } from "@/components/layout/page-shell";
import { StatCard } from "@/components/feature/stat-card";
import { TrendCard } from "@/components/feature/trend-card";
import { ApprovalCard } from "@/components/feature/approval-card";
import { CommandHero } from "@/components/feature/command-hero";
import { GenerateBriefButton } from "@/components/feature/generation/generate-brief-button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { data } from "@/lib/data";
import { formatDateTime } from "@/lib/utils";

const JOB_STATUS_RU: Record<string, string> = {
  pending: "в очереди",
  done: "готово",
  failed: "ошибка",
  blocked: "заблок.",
  dry_run: "проверка",
  pending_config: "нет настроек",
};

export default async function DashboardPage() {
  const [trends, candidates, jobs, status, analytics] = await Promise.all([
    data.trends(),
    data.candidates(),
    data.jobs(),
    data.status(),
    data.analytics(),
  ]);

  const topTrends = trends.slice(0, 4);
  const pendingApprovals = candidates.filter((c) => c.status === "draft").slice(0, 3);
  const upcomingJobs = jobs
    .filter((j) => j.status === "pending")
    .sort((a, b) => new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime())
    .slice(0, 5);
  const insights = analytics.best_patterns.slice(0, 3);

  // Tiny sparkline samples from analytics timeline (last 7 days).
  const timeline = analytics.learning_timeline.slice(-7).map((p) => p.avg_engagement);
  const styleSpark = analytics.learning_timeline.slice(-7).map((p) => 60 + (p.posts % 30));
  const pendingCount = candidates.filter((c) => c.status === "draft").length;
  const styleAvg = Math.round(
    (candidates.reduce((s, c) => s + c.style_match_score, 0) / Math.max(1, candidates.length)) *
      100,
  );

  return (
    <>
      <Topbar
        title="Главная"
        subtitle="Сегодняшние сигналы, идеи и работа редакции"
        pill={{
          label: status.mock_mode ? "Демо-режим" : status.app_env,
          tone: status.mock_mode ? "cyan" : "violet",
        }}
        actions={
          <>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/trends"><Compass className="h-4 w-4" /> Тренды →</Link>
            </Button>
            <GenerateBriefButton size="sm" label="Создать пост" />
          </>
        }
      />
      <PageShell>
        <CommandHero
          topScore={topTrends[0]?.total_score ?? 0}
          trendCount={trends.length}
          pendingCount={pendingCount}
          scheduledCount={analytics.totals.scheduled}
          topTrendTitle={topTrends[0]?.representative_text?.slice(0, 110)}
        />

        <PageSection title="Сегодня" description="Текущее состояние редакции">
          <div className="grid grid-cols-2 gap-2.5 sm:gap-3 md:grid-cols-4 3xl:gap-4">
            <StatCard
              tone="violet"
              icon={Radio}
              label="Трендов сегодня"
              value={trends.length}
              trend={{ direction: "up", delta: "+3 со вчера" }}
              hint={`${trends.filter((t) => t.total_score >= 0.7).length} с рейтингом 70+`}
              spark={timeline}
            />
            <StatCard
              icon={CheckCircle2}
              label="Ждут одобрения"
              value={pendingCount}
              hint="Нужно ваше решение"
            />
            <StatCard
              icon={CalendarIcon}
              label="Запланировано"
              value={analytics.totals.scheduled}
              hint={`${analytics.totals.published} опубликовано за неделю`}
            />
            <StatCard
              tone="cyan"
              icon={Activity}
              label="Совпадение со стилем"
              value={styleAvg}
              hint="В среднем по черновикам"
              trend={{ direction: "up", delta: "+4 за неделю" }}
              spark={styleSpark}
            />
          </div>
        </PageSection>

        <div className="grid gap-4 lg:gap-5 xl:gap-6 xl:grid-cols-[1.4fr_1fr] 3xl:grid-cols-[1.6fr_1fr]">
          <PageSection
            title="Идеи на сегодня"
            description="Темы с высоким рейтингом — из них стоит сделать посты"
            action={
              <Button variant="ghost" size="sm" asChild>
                <Link href="/trends">Все тренды →</Link>
              </Button>
            }
          >
            <div className="grid gap-3 sm:grid-cols-2 3xl:grid-cols-2 4xl:grid-cols-3">
              {topTrends.map((t, i) => (
                <TrendCard key={t.id} trend={t} rank={i + 1} />
              ))}
            </div>
          </PageSection>

          <PageSection
            title="Ждут одобрения"
            description="Черновики, которые ИИ предлагает проверить"
            action={
              <Button variant="ghost" size="sm" asChild>
                <Link href="/approvals">На доску →</Link>
              </Button>
            }
          >
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
              {pendingApprovals.map((c) => (
                <ApprovalCard key={c.id} candidate={c} />
              ))}
            </div>
          </PageSection>
        </div>

        <div className="grid gap-4 lg:gap-5 xl:gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <CalendarIcon className="h-4 w-4 text-accent-cyan" />
                  Ближайшие публикации
                </CardTitle>
                <Button variant="ghost" size="sm" asChild>
                  <Link href="/calendar">Календарь →</Link>
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-2">
              {upcomingJobs.length === 0 && (
                <p className="text-sm text-ink-400">Очередь публикаций пуста.</p>
              )}
              {upcomingJobs.map((j, idx) => {
                const cand = candidates.find((c) => c.id === j.candidate_id);
                return (
                  <Link
                    key={j.id}
                    href="/calendar"
                    className="group relative flex items-center gap-3 rounded-xl border border-white/[0.05] bg-white/[0.02] p-3 transition-all hover:bg-white/[0.04] hover:border-white/[0.10]"
                  >
                    {/* mini timeline rail */}
                    <div className="absolute left-[22px] top-full hidden h-3 w-px bg-white/[0.06] last:hidden sm:block" />
                    <div className="grid h-9 w-9 place-items-center rounded-lg bg-gradient-to-br from-accent-violet/30 to-accent-cyan/30 ring-1 ring-white/[0.06]">
                      <Zap className="h-4 w-4 text-ink-100" strokeWidth={1.8} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium text-ink-50">
                        {cand?.topic ?? "Запланированный пост"}
                      </div>
                      <div className="mt-0.5 flex items-center gap-2 text-[11px] text-ink-400">
                        <Badge variant="outline">{j.platform}</Badge>
                        <span>{formatDateTime(j.scheduled_at)}</span>
                      </div>
                    </div>
                    <span className="text-[10px] uppercase tracking-[0.18em] text-ink-500">
                      {JOB_STATUS_RU[j.status] ?? j.status}
                    </span>
                  </Link>
                );
              })}
            </CardContent>
          </Card>

          <Card tone="violet">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Lightbulb className="h-4 w-4 text-accent-violet" />
                Что заметил ИИ
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {insights.map((i, idx) => (
                <div
                  key={idx}
                  className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3 transition-colors hover:border-white/[0.10] hover:bg-white/[0.04]"
                >
                  <div className="flex items-center gap-2">
                    <Badge variant={idx === 0 ? "violet" : idx === 1 ? "cyan" : "mint"}>
                      {i.kind}
                    </Badge>
                    <span className="text-sm font-medium text-ink-50">{i.title}</span>
                  </div>
                  <div className="mt-1 text-xs text-ink-400">{i.detail}</div>
                </div>
              ))}
              <div className="mt-3 flex items-center gap-2 text-[11px] text-ink-500">
                <Flame className="h-3 w-3 text-accent-violet" />
                Выводы обновляются после каждого одобрения и новых метрик.
              </div>
            </CardContent>
          </Card>
        </div>
      </PageShell>
    </>
  );
}
