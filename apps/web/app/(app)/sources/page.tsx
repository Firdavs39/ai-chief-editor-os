import * as React from "react";
import Link from "next/link";
import { Plus, Radio } from "lucide-react";
import { Topbar } from "@/components/layout/topbar";
import { PageShell, PageSection } from "@/components/layout/page-shell";
import { SourceHealthCard } from "@/components/feature/source-health";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { data } from "@/lib/data";

function pluralSources(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return "источник";
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return "источника";
  return "источников";
}

export default async function SourcesPage() {
  const sources = await data.sources();
  const byKind = {
    telegram: sources.filter((s) => s.kind === "telegram"),
    reddit: sources.filter((s) => s.kind === "reddit"),
    rss: sources.filter((s) => s.kind === "rss"),
    manual: sources.filter((s) => s.kind === "manual"),
  };
  const healthy = sources.filter((s) => (s.health?.ok ?? true) === true).length;

  return (
    <>
      <Topbar
        title="Источники"
        subtitle="Telegram-каналы, сабреддиты, RSS — что мы отслеживаем"
        pill={{ label: `${sources.length} ${pluralSources(sources.length)}`, tone: "violet" }}
        actions={
          <Button size="sm" variant="outline" asChild>
            <Link href="/channels">
              <Plus className="h-4 w-4" /> Управление в Каналах →
            </Link>
          </Button>
        }
      />
      <PageShell>
        <div className="grid grid-cols-2 gap-2.5 sm:gap-3 md:grid-cols-4 3xl:gap-4">
          <Card className="p-3 sm:p-4 3xl:p-5">
            <div className="text-[10px] sm:text-[11px] uppercase tracking-[0.18em] text-ink-400">Всего</div>
            <div className="num mt-1 text-xl sm:text-2xl 3xl:text-[28px] font-semibold text-ink-50">{sources.length}</div>
          </Card>
          <Card className="p-3 sm:p-4 3xl:p-5">
            <div className="text-[10px] sm:text-[11px] uppercase tracking-[0.18em] text-ink-400">Работают</div>
            <div className="num mt-1 text-xl sm:text-2xl 3xl:text-[28px] font-semibold text-accent-mint">{healthy}</div>
          </Card>
          <Card className="p-3 sm:p-4 3xl:p-5">
            <div className="text-[10px] sm:text-[11px] uppercase tracking-[0.18em] text-ink-400">Telegram</div>
            <div className="num mt-1 text-xl sm:text-2xl 3xl:text-[28px] font-semibold text-ink-50">{byKind.telegram.length}</div>
          </Card>
          <Card className="p-3 sm:p-4 3xl:p-5">
            <div className="text-[10px] sm:text-[11px] uppercase tracking-[0.18em] text-ink-400">Reddit + RSS</div>
            <div className="num mt-1 text-xl sm:text-2xl 3xl:text-[28px] font-semibold text-ink-50">
              {byKind.reddit.length + byKind.rss.length}
            </div>
          </Card>
        </div>

        {(["telegram", "reddit", "rss"] as const).map((kind) => {
          const list = byKind[kind];
          if (list.length === 0) return null;
          return (
            <PageSection
              key={kind}
              title={kind === "rss" ? "RSS-ленты" : kind === "telegram" ? "Telegram-каналы" : "Сообщества Reddit"}
              action={
                <Badge variant="outline">{list.length}</Badge>
              }
            >
              <div className="space-y-2">
                {list.map((s) => (
                  <SourceHealthCard key={s.id} source={s} />
                ))}
              </div>
            </PageSection>
          );
        })}

        <Card className="p-4">
          <CardHeader className="p-0 pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Radio className="h-4 w-4 text-accent-cyan" />
              Как работают источники
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0 pt-1 text-xs leading-relaxed text-ink-300">
            Каждый источник проверяется по расписанию. В демо-режиме данные берутся
            из готовой подборки. Чтобы перейти на реальный сбор, подключите ключи
            Telegram и Reddit в Настройках. Threads публикуется только через Postiz
            или официальный API Threads — никакого несанкционированного парсинга.
          </CardContent>
        </Card>
      </PageShell>
    </>
  );
}
