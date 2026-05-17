import * as React from "react";
import Link from "next/link";
import { ArrowUpRight, Flame, Sparkles } from "lucide-react";
import type { Trend } from "@/lib/types";
import { timeAgo } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { RadialScore } from "./radial-score";

export function TrendCard({ trend, rank }: { trend: Trend; rank?: number }) {
  const score = Math.round(trend.total_score * 100);
  const isHot = score >= 75;
  const sourcesShown = trend.sources_summary.slice(0, 3);
  return (
    <Card
      interactive
      className="group relative overflow-hidden p-4 sm:p-5 3xl:p-6 transition-shadow hover:shadow-card-hover"
    >
      <div className="hairline-top" />

      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5 sm:gap-2 flex-wrap">
            {rank !== undefined && (
              <span className="num display inline-flex h-5 sm:h-6 min-w-5 sm:min-w-6 items-center justify-center rounded-md border border-white/[0.08] bg-white/[0.03] px-1.5 text-[10px] sm:text-[11px] font-medium text-ink-300">
                {String(rank).padStart(2, "0")}
              </span>
            )}
            <Badge variant={isHot ? "violet" : "outline"}>
              {isHot ? (
                <>
                  <Flame className="h-3 w-3" /> Hot
                </>
              ) : (
                <>{trend.category.toUpperCase()}</>
              )}
            </Badge>
            <Badge variant="outline" className="hidden xs:inline-flex sm:inline-flex">
              {trend.signal_count} signals
            </Badge>
          </div>

          <Link
            href={`/trends?focus=${trend.id}`}
            className="mt-3 block text-[14px] sm:text-[15px] 3xl:text-[16px] font-medium leading-snug text-ink-50 hover:text-white"
          >
            {trend.representative_text}
          </Link>
        </div>
        <div className="shrink-0">
          <RadialScore value={trend.total_score} size={56} label="score" />
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {trend.keywords.slice(0, 5).map((k) => (
          <span
            key={k}
            className="rounded-md border border-white/[0.06] bg-white/[0.02] px-1.5 py-0.5 text-[10px] sm:text-[11px] text-ink-300"
          >
            {k}
          </span>
        ))}
      </div>

      <div className="mt-3 sm:mt-4 flex items-center justify-between gap-2 text-xs text-ink-400">
        <div className="flex items-center gap-1.5 flex-wrap min-w-0">
          {sourcesShown.map((s) => (
            <span
              key={s.handle}
              className="truncate rounded-full border border-white/[0.07] bg-white/[0.03] px-2 py-0.5 text-[10px] text-ink-300"
            >
              {s.handle} <span className="text-ink-500">·</span> <span className="num">{s.count}</span>
            </span>
          ))}
          {trend.sources_summary.length > 3 && (
            <span className="text-[10px] text-ink-500">+{trend.sources_summary.length - 3}</span>
          )}
        </div>
        <span className="text-[10px] text-ink-500 shrink-0">{timeAgo(trend.last_seen_at)}</span>
      </div>

      <div className="mt-3 sm:mt-4 flex items-center justify-between gap-3 border-t border-white/[0.05] pt-2.5 sm:pt-3">
        <Link
          href={`/editor?cluster=${trend.id}`}
          className="link inline-flex items-center gap-1.5 text-xs font-medium text-accent-cyan"
        >
          <Sparkles className="h-3 w-3" />
          Generate brief
        </Link>
        <Link
          href={`/trends?focus=${trend.id}`}
          className="inline-flex items-center gap-1 text-xs text-ink-300 transition-colors hover:text-ink-50"
        >
          Open <ArrowUpRight className="h-3 w-3" />
        </Link>
      </div>
    </Card>
  );
}
