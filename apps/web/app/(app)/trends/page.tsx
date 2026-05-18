import * as React from "react";
import Link from "next/link";
import { Radio, Sparkles, Filter, ArrowUpRight } from "lucide-react";
import { Topbar } from "@/components/layout/topbar";
import { PageShell, PageSection } from "@/components/layout/page-shell";
import { TrendCard } from "@/components/feature/trend-card";
import { ScoreBreakdown } from "@/components/feature/score-breakdown";
import { GenerateBriefButton } from "@/components/feature/generation/generate-brief-button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { data } from "@/lib/data";
import { timeAgo } from "@/lib/utils";

const FILTERS = [
  { label: "All", value: "all" },
  { label: "Russian", value: "ru" },
  { label: "English", value: "en" },
  { label: "Score 70+", value: "hot" },
];

type SearchParams = {
  focus?: string;
  filter?: string;
};

export default async function TrendsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const sp = await searchParams;
  const trends = await data.trends();
  const filterValue = sp.filter ?? "all";

  const filtered = trends.filter((t) => {
    if (filterValue === "hot") return t.total_score >= 0.7;
    if (filterValue === "ru" || filterValue === "en") return t.category === filterValue;
    return true;
  });

  const focusId = sp.focus ?? filtered[0]?.id;
  const focus = trends.find((t) => t.id === focusId) ?? trends[0];

  return (
    <>
      <Topbar
        title="Trend Radar"
        subtitle="Кластеры сигналов, рейтинг и причины ранжирования"
        pill={{ label: `${filtered.length} clusters`, tone: "violet" }}
        actions={
          <div className="flex items-center gap-2">
            <GenerateBriefButton size="sm" clusterId={focus?.id ?? null} />
            <Button size="sm" variant="outline" asChild>
              <Link href="/editor"><Sparkles className="h-4 w-4" /> Open editor</Link>
            </Button>
          </div>
        }
      />
      <PageShell>
        <div className="flex flex-wrap items-center gap-2">
          {FILTERS.map((f) => {
            const active = filterValue === f.value;
            return (
              <Link
                key={f.value}
                href={`/trends?filter=${f.value}${focusId ? `&focus=${focusId}` : ""}`}
                className={
                  active
                    ? "rounded-full bg-accent-violet/15 px-3 py-1.5 text-xs font-medium text-accent-violet ring-1 ring-accent-violet/30"
                    : "rounded-full border border-white/[0.08] bg-white/[0.02] px-3 py-1.5 text-xs text-ink-300 hover:bg-white/[0.04]"
                }
              >
                {f.label}
              </Link>
            );
          })}
          <div className="ml-auto flex items-center gap-2 text-xs text-ink-400">
            <Filter className="h-3.5 w-3.5" />
            sorted by total score
          </div>
        </div>

        <div className="grid gap-4 lg:gap-5 xl:gap-6 xl:grid-cols-[1.4fr_1fr] 3xl:grid-cols-[1.6fr_1fr]">
          <PageSection
            title="Clusters"
            description="Каждый кластер — это нормализованная группа сигналов из нескольких источников"
          >
            <div className="grid gap-3 sm:grid-cols-2 3xl:grid-cols-2 4xl:grid-cols-3">
              {filtered.map((t, i) => (
                <TrendCard key={t.id} trend={t} rank={i + 1} />
              ))}
            </div>
          </PageSection>

          <PageSection
            title="Score breakdown"
            description={focus ? "Прозрачное разложение по каждому фактору" : undefined}
          >
            {focus ? (
              <Card>
                <CardHeader>
                  <div className="flex items-start justify-between gap-3">
                    <CardTitle className="text-base">{focus.representative_text}</CardTitle>
                    <Badge variant="violet">{Math.round(focus.total_score * 100)}</Badge>
                  </div>
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {focus.keywords.slice(0, 6).map((k) => (
                      <span
                        key={k}
                        className="rounded-md border border-white/[0.06] bg-white/[0.02] px-1.5 py-0.5 text-[11px] text-ink-300"
                      >
                        {k}
                      </span>
                    ))}
                  </div>
                </CardHeader>
                <CardContent className="space-y-5">
                  <ScoreBreakdown
                    data={focus.score_breakdown}
                    total={focus.total_score}
                  />

                  <div className="space-y-2">
                    <div className="text-[11px] uppercase tracking-[0.18em] text-ink-500">
                      Sources mix
                    </div>
                    <div className="space-y-1.5">
                      {focus.sources_summary.map((s) => (
                        <div
                          key={s.handle}
                          className="flex items-center justify-between rounded-lg border border-white/[0.05] bg-white/[0.02] px-3 py-2 text-xs"
                        >
                          <span className="text-ink-200">{s.handle}</span>
                          <span className="num text-ink-100">{s.count}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-[11px]">
                    <div className="rounded-lg border border-white/[0.05] bg-white/[0.02] p-2.5">
                      <div className="text-ink-500">First seen</div>
                      <div className="text-ink-100 mt-0.5">{timeAgo(focus.first_seen_at)}</div>
                    </div>
                    <div className="rounded-lg border border-white/[0.05] bg-white/[0.02] p-2.5">
                      <div className="text-ink-500">Last signal</div>
                      <div className="text-ink-100 mt-0.5">{timeAgo(focus.last_seen_at)}</div>
                    </div>
                  </div>

                  <Link
                    href={`/editor?cluster=${focus.id}`}
                    className="inline-flex w-full items-center justify-center gap-1.5 rounded-xl border border-accent-violet/30 bg-accent-violet/10 px-3 py-2 text-sm font-medium text-accent-violet hover:bg-accent-violet/15"
                  >
                    <Sparkles className="h-4 w-4" /> Write a candidate from this cluster
                    <ArrowUpRight className="h-3.5 w-3.5" />
                  </Link>
                </CardContent>
              </Card>
            ) : (
              <Card className="p-8 text-center text-sm text-ink-400">
                Pick a cluster to see why it ranks high.
              </Card>
            )}
          </PageSection>
        </div>
      </PageShell>
    </>
  );
}
