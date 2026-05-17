import * as React from "react";
import { Activity, Flame, LineChart, Layers, Lightbulb, Trophy } from "lucide-react";
import { Topbar } from "@/components/layout/topbar";
import { PageShell, PageSection } from "@/components/layout/page-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  HookTypeChart,
  LearningTimelineChart,
  SourcePerformanceChart,
} from "@/components/feature/analytics-charts";
import { StatCard } from "@/components/feature/stat-card";
import { data } from "@/lib/data";

export default async function AnalyticsPage() {
  const a = await data.analytics();
  const ratio = a.totals.approved + a.totals.rejected;
  const approvalRate = ratio === 0 ? 0 : Math.round((a.totals.approved / ratio) * 100);

  const timelineSpark = a.learning_timeline.slice(-7).map((p) => p.avg_engagement);
  const topHook = a.by_hook_type[0];
  const topSource = a.by_source[0];

  return (
    <>
      <Topbar
        title="Analytics"
        subtitle="Что зашло, какие источники работают, какие крючки сильнее"
        pill={{ label: "demo metrics", tone: "cyan" }}
      />
      <PageShell>
        <div className="grid grid-cols-2 gap-2.5 sm:gap-3 md:grid-cols-4 3xl:gap-4">
          <StatCard
            tone="violet"
            icon={Flame}
            label="Published"
            value={a.totals.published}
            hint="last 14 days"
          />
          <StatCard
            icon={Activity}
            label="Approval rate"
            value={`${approvalRate}%`}
            hint={`${a.totals.approved}/${a.totals.approved + a.totals.rejected} approve`}
            trend={{ direction: "up", delta: "+6 vs prev" }}
          />
          <StatCard
            icon={Layers}
            label="Avg engagement"
            value={(topSource?.avg_engagement ?? 0).toLocaleString()}
            hint="top source last 14d"
            spark={timelineSpark}
          />
          <StatCard
            tone="cyan"
            icon={LineChart}
            label="Posts in queue"
            value={a.totals.scheduled}
            hint="scheduled future"
          />
        </div>

        {/* Leader card */}
        {topHook && topSource && (
          <Card tone="violet" className="overflow-hidden p-4 sm:p-5">
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="sm:col-span-2 space-y-2">
                <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-accent-violet">
                  <Trophy className="h-3.5 w-3.5" />
                  This week's best pattern
                </div>
                <h2 className="display text-[18px] sm:text-[20px] 3xl:text-[24px] font-semibold leading-tight tracking-tight text-ink-50">
                  <span className="text-ink-300">Hooks of type</span>{" "}
                  <span className="text-ink-50">«{topHook.hook_type}»</span>{" "}
                  <span className="text-ink-300">drove</span>{" "}
                  <span className="num text-accent-cyan">
                    {Math.round(topHook.viral_avg * 100)}
                  </span>{" "}
                  <span className="text-ink-300">avg viral score</span>
                </h2>
                <p className="text-sm text-ink-300 leading-relaxed">
                  Источник{" "}
                  <span className="text-ink-100 font-mono">{topSource.source}</span> привёл{" "}
                  <span className="num text-ink-100">
                    {topSource.avg_engagement.toLocaleString()}
                  </span>{" "}
                  среднего вовлечения. Используй этот формат как baseline на следующей неделе.
                </p>
              </div>
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
                <div className="text-[10px] uppercase tracking-[0.18em] text-ink-500">
                  Top hook
                </div>
                <div className="num display text-2xl font-semibold text-ink-50 mt-1">
                  {Math.round(topHook.viral_avg * 100)}
                </div>
                <div className="text-[11px] text-ink-400 mt-0.5">{topHook.hook_type}</div>
                <div className="mt-3 h-px bg-hairline" />
                <div className="mt-3 text-[10px] uppercase tracking-[0.18em] text-ink-500">
                  Top source
                </div>
                <div className="num display text-xl font-semibold text-ink-50 mt-1">
                  {topSource.avg_engagement.toLocaleString()}
                </div>
                <div className="text-[11px] text-ink-400 mt-0.5 truncate">{topSource.source}</div>
              </div>
            </div>
          </Card>
        )}

        <div className="grid gap-4 lg:gap-5 xl:gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm flex items-center gap-2">
                <Flame className="h-4 w-4 text-accent-violet" /> Performance by hook type
              </CardTitle>
            </CardHeader>
            <CardContent>
              <HookTypeChart data={a.by_hook_type} />
              <div className="mt-3 flex flex-wrap gap-1.5">
                {a.by_hook_type.map((h) => (
                  <Badge key={h.hook_type} variant="outline">
                    {h.hook_type} · {h.posts}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm flex items-center gap-2">
                <LineChart className="h-4 w-4 text-accent-cyan" /> Learning timeline · 14 days
              </CardTitle>
            </CardHeader>
            <CardContent>
              <LearningTimelineChart data={a.learning_timeline} />
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm flex items-center gap-2">
              <Layers className="h-4 w-4 text-accent-violet" /> Source → performance
            </CardTitle>
          </CardHeader>
          <CardContent>
            <SourcePerformanceChart data={a.by_source} />
          </CardContent>
        </Card>

        <PageSection
          title="Patterns the AI noticed"
          description="Эти инсайты обновляются после каждого approve / metric snapshot"
        >
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {a.best_patterns.map((p, i) => (
              <Card
                key={i}
                tone={i === 0 ? "violet" : i === 1 ? "cyan" : "default"}
                className="p-4"
              >
                <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.18em] text-ink-400">
                  <Lightbulb className="h-3 w-3" /> {p.kind}
                </div>
                <div className="mt-2 text-sm font-medium text-ink-50">{p.title}</div>
                <div className="mt-1 text-xs text-ink-300">{p.detail}</div>
              </Card>
            ))}
          </div>
        </PageSection>
      </PageShell>
    </>
  );
}
