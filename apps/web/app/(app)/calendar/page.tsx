import * as React from "react";
import Link from "next/link";
import { CalendarDays, Clock, MessageCircle, Radio, Type, Zap } from "lucide-react";
import { Topbar } from "@/components/layout/topbar";
import { PageShell, PageSection } from "@/components/layout/page-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { data } from "@/lib/data";
import { cn, formatDateTime, formatNumber } from "@/lib/utils";

const PLATFORM_ICON = {
  telegram: MessageCircle,
  threads: Type,
  reddit: Radio,
  mock: Zap,
} as const;

const PLATFORM_TONE = {
  telegram: "violet",
  threads: "cyan",
  reddit: "amber",
  mock: "outline",
} as const;

function startOfMonth(d: Date) {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}

function addDays(d: Date, n: number) {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
}

export default async function CalendarPage() {
  const calendar = await data.calendar();
  const now = new Date();
  const monthStart = startOfMonth(now);
  const firstWeekday = (monthStart.getDay() + 6) % 7; // monday=0
  const gridStart = addDays(monthStart, -firstWeekday);

  const cells = Array.from({ length: 42 }).map((_, i) => addDays(gridStart, i));
  const byDay = new Map<string, typeof calendar>();
  for (const entry of calendar) {
    const key = entry.scheduled_at.slice(0, 10);
    const list = byDay.get(key) ?? [];
    list.push(entry);
    byDay.set(key, list);
  }

  const upcoming = calendar
    .filter((c) => c.status === "pending")
    .slice(0, 6);

  return (
    <>
      <Topbar
        title="Content Calendar"
        subtitle="Расписание публикаций по платформам"
        pill={{ label: `${calendar.length} entries`, tone: "violet" }}
      />
      <PageShell>
        <PageSection
          title={now.toLocaleDateString("en-GB", { month: "long", year: "numeric" })}
          description="Месячный обзор. Чипы — это PublishJob c учётом approval."
        >
          {/* Month grid: hidden on mobile, visible from md+ */}
          <Card className="hidden md:block p-3 sm:p-4 3xl:p-5">
            <div className="grid grid-cols-7 gap-2 text-[10px] uppercase tracking-[0.18em] text-ink-500">
              {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
                <div key={d} className="px-1.5">{d}</div>
              ))}
            </div>
            <div className="mt-2 grid grid-cols-7 gap-1.5 lg:gap-2">
              {cells.map((d, i) => {
                const key = d.toISOString().slice(0, 10);
                const items = byDay.get(key) ?? [];
                const inMonth = d.getMonth() === now.getMonth();
                const isToday = d.toDateString() === now.toDateString();
                return (
                  <div
                    key={i}
                    className={cn(
                      "relative min-h-[90px] lg:min-h-[110px] 3xl:min-h-[140px] rounded-xl border p-1.5 lg:p-2 text-[11px] transition-colors",
                      inMonth
                        ? "border-white/[0.05] bg-white/[0.015]"
                        : "border-white/[0.03] bg-transparent opacity-40",
                      isToday && "border-accent-violet/40 bg-accent-violet/[0.05] ring-1 ring-accent-violet/30 shadow-[0_0_24px_-8px_rgba(139,92,246,0.6)]",
                    )}
                  >
                    <div className={cn(
                      "flex items-center justify-between text-[10px]",
                      isToday ? "text-accent-violet font-medium" : "text-ink-500",
                    )}>
                      <span className="num display">
                        {d.getDate().toString().padStart(2, "0")}
                      </span>
                      {items.length > 0 && (
                        <span className="num inline-flex items-center gap-1">
                          <span className="h-1 w-1 rounded-full bg-accent-violet/70" />
                          {items.length}
                        </span>
                      )}
                    </div>
                    <div className="mt-1.5 space-y-1">
                      {items.slice(0, 3).map((e) => {
                        const Icon = PLATFORM_ICON[e.platform as keyof typeof PLATFORM_ICON] ?? Zap;
                        const tone = PLATFORM_TONE[e.platform as keyof typeof PLATFORM_TONE] ?? "outline";
                        return (
                          <div
                            key={e.job_id}
                            className={cn(
                              "flex items-center gap-1.5 rounded-md border px-1.5 py-1 text-[10px]",
                              tone === "violet" && "border-accent-violet/30 bg-accent-violet/10 text-accent-violet",
                              tone === "cyan" && "border-accent-cyan/30 bg-accent-cyan/10 text-accent-cyan",
                              tone === "amber" && "border-accent-amber/30 bg-accent-amber/10 text-accent-amber",
                              tone === "outline" && "border-white/[0.08] bg-white/[0.03] text-ink-300",
                            )}
                          >
                            <Icon className="h-2.5 w-2.5 shrink-0" />
                            <span className="truncate">{e.topic}</span>
                          </div>
                        );
                      })}
                      {items.length > 3 && (
                        <div className="text-[10px] text-ink-500">+{items.length - 3} more</div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>

          {/* Mobile-only: chronological list grouped by day */}
          <div className="md:hidden space-y-3">
            {Array.from(byDay.entries())
              .sort(([a], [b]) => a.localeCompare(b))
              .map(([day, items]) => (
                <Card key={day} className="p-3">
                  <div className="flex items-center justify-between text-[11px] uppercase tracking-[0.18em] text-ink-400 pb-2">
                    <span>
                      {new Date(day).toLocaleDateString("en-GB", {
                        weekday: "short",
                        day: "2-digit",
                        month: "short",
                      })}
                    </span>
                    <span className="num text-ink-300">{items.length}</span>
                  </div>
                  <div className="space-y-1.5">
                    {items.map((e) => {
                      const Icon = PLATFORM_ICON[e.platform as keyof typeof PLATFORM_ICON] ?? Zap;
                      const tone = PLATFORM_TONE[e.platform as keyof typeof PLATFORM_TONE] ?? "outline";
                      return (
                        <div
                          key={e.job_id}
                          className={cn(
                            "flex items-center gap-2 rounded-lg border px-2.5 py-2 text-xs",
                            tone === "violet" && "border-accent-violet/30 bg-accent-violet/10",
                            tone === "cyan" && "border-accent-cyan/30 bg-accent-cyan/10",
                            tone === "amber" && "border-accent-amber/30 bg-accent-amber/10",
                            tone === "outline" && "border-white/[0.08] bg-white/[0.03]",
                          )}
                        >
                          <Icon className="h-3.5 w-3.5 shrink-0" />
                          <span className="flex-1 truncate text-ink-100">{e.topic}</span>
                          <span className="text-[10px] text-ink-400 shrink-0">
                            {new Date(e.scheduled_at).toLocaleTimeString("en-GB", {
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </Card>
              ))}
            {byDay.size === 0 && (
              <Card className="p-6 text-center text-xs text-ink-400">
                Очередь публикаций пуста.
              </Card>
            )}
          </div>
        </PageSection>

        <PageSection
          title="Upcoming queue"
          description="Ближайшие job-ы по времени"
        >
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 3xl:grid-cols-3 4xl:grid-cols-4">
            {upcoming.map((e) => {
              const Icon = PLATFORM_ICON[e.platform as keyof typeof PLATFORM_ICON] ?? Zap;
              return (
                <Card key={e.job_id} className="p-4">
                  <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.18em] text-ink-500">
                    <Icon className="h-3 w-3" /> {e.platform}
                    <span className="ml-auto">{e.status}</span>
                  </div>
                  <Link
                    href={`/editor/${e.candidate_id}`}
                    className="mt-2 block text-sm font-medium text-ink-50 hover:text-white"
                  >
                    {e.topic}
                  </Link>
                  <p className="mt-2 line-clamp-2 text-xs text-ink-300">
                    {e.tg_preview || e.threads_preview}
                  </p>
                  <div className="mt-3 flex items-center gap-2 text-[11px] text-ink-400">
                    <Clock className="h-3 w-3" />
                    {formatDateTime(e.scheduled_at)}
                  </div>
                </Card>
              );
            })}
            {upcoming.length === 0 && (
              <Card className="p-6 text-center text-xs text-ink-400">
                Очередь пуста. Approve кандидата, чтобы запланировать публикацию.
              </Card>
            )}
          </div>
        </PageSection>
      </PageShell>
    </>
  );
}
