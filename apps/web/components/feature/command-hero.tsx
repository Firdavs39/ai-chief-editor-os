import * as React from "react";
import Link from "next/link";
import { ArrowUpRight, Sparkles } from "lucide-react";
import { Card } from "@/components/ui/card";

// Русское склонение по числу: (1, 2-4, 5+).
function plural(n: number, one: string, few: string, many: string): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return few;
  return many;
}
const pluralDrafts = (n: number) => plural(n, "черновик", "черновика", "черновиков");
const pluralTrends = (n: number) => plural(n, "тренд", "тренда", "трендов");
const pluralPosts = (n: number) => plural(n, "пост", "поста", "постов");

export function CommandHero({
  topScore,
  trendCount,
  pendingCount,
  scheduledCount,
  topTrendTitle,
}: {
  topScore: number;
  trendCount: number;
  pendingCount: number;
  scheduledCount: number;
  topTrendTitle?: string;
}) {
  return (
    <Card tone="violet" className="relative overflow-hidden p-5 sm:p-6 3xl:p-7">
      <div className="absolute -right-12 -top-12 h-48 w-48 rounded-full bg-accent-violet/20 blur-3xl" />
      <div className="absolute -right-24 top-1/2 h-40 w-40 rounded-full bg-accent-cyan/15 blur-3xl" />

      <div className="relative flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 flex-1 space-y-3">
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-accent-violet/90">
            <span className="dot-live shrink-0" />
            Сводка редакции · вживую
          </div>
          <h2 className="display text-[20px] sm:text-[24px] 3xl:text-[28px] font-semibold leading-tight tracking-tight text-ink-50">
            {pendingCount > 0 ? (
              <>
                <span className="text-ink-50">{pendingCount} {pluralDrafts(pendingCount)}</span>
                <span className="text-ink-300"> ждут вашей проверки,</span>{" "}
                <span className="text-ink-50">{trendCount} {pluralTrends(trendCount)}</span>
                <span className="text-ink-300"> на радаре.</span>
              </>
            ) : (
              <>
                <span className="text-ink-300">Спокойное утро. </span>
                <span className="text-ink-50">{trendCount} {pluralTrends(trendCount)}</span>
                <span className="text-ink-300"> отслеживаем, проверять нечего.</span>
              </>
            )}
          </h2>
          {topTrendTitle && (
            <p className="text-sm leading-relaxed text-ink-300 max-w-[60ch]">
              Главный сигнал —{" "}
              <span className="text-ink-100">«{topTrendTitle}»</span>{" "}
              <span className="text-accent-cyan num">· рейтинг {Math.round(topScore * 100)}</span>.
              {scheduledCount > 0 && (
                <>
                  {" "}
                  <span className="text-ink-400">
                    На сегодня в очереди {scheduledCount} {pluralPosts(scheduledCount)}.
                  </span>
                </>
              )}
            </p>
          )}
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <Link
              href="/trends"
              className="inline-flex items-center gap-1.5 rounded-lg border border-white/[0.10] bg-white/[0.04] px-3 py-1.5 text-[12px] font-medium text-ink-100 transition-colors hover:bg-white/[0.08] hover:border-white/[0.16]"
            >
              <Sparkles className="h-3.5 w-3.5 text-accent-violet" />
              Открыть тренды
              <ArrowUpRight className="h-3 w-3 text-ink-400" />
            </Link>
            <Link
              href="/approvals"
              className="inline-flex items-center gap-1.5 rounded-lg border border-accent-violet/30 bg-accent-violet/15 px-3 py-1.5 text-[12px] font-medium text-accent-violet transition-colors hover:bg-accent-violet/20"
            >
              Проверить посты
              <ArrowUpRight className="h-3 w-3" />
            </Link>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2 sm:flex sm:flex-col sm:items-end sm:gap-1.5 sm:text-right shrink-0">
          <Stat label="Тренды" value={trendCount} />
          <Stat label="На проверке" value={pendingCount} tone="violet" />
          <Stat label="В очереди" value={scheduledCount} tone="cyan" />
        </div>
      </div>
    </Card>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone?: "violet" | "cyan" }) {
  return (
    <div className="flex flex-col sm:items-end">
      <span className="text-[10px] uppercase tracking-[0.18em] text-ink-500">{label}</span>
      <span
        className={
          "display num text-2xl font-semibold leading-none mt-0.5 " +
          (tone === "violet"
            ? "text-accent-violet"
            : tone === "cyan"
            ? "text-accent-cyan"
            : "text-ink-50")
        }
      >
        {value}
      </span>
    </div>
  );
}
