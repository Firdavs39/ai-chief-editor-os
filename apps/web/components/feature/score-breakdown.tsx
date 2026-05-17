import * as React from "react";
import { cn } from "@/lib/utils";

type Entry = { label: string; value: number; tone?: "violet" | "cyan" | "neutral" };

export function ScoreBreakdown({
  data,
  total,
  className,
}: {
  data: Record<string, number>;
  total?: number;
  className?: string;
}) {
  const entries: Entry[] = [
    { label: "Recency", value: data.recency ?? 0, tone: "cyan" },
    { label: "Engagement", value: data.engagement ?? 0, tone: "violet" },
    { label: "Source weight", value: data.source_weight ?? 0, tone: "neutral" },
    { label: "Novelty", value: data.novelty ?? 0, tone: "cyan" },
    { label: "Usefulness", value: data.usefulness ?? 0, tone: "violet" },
    { label: "Style fit", value: data.style_fit ?? 0, tone: "violet" },
    { label: "Controversy", value: data.controversy ?? 0, tone: "neutral" },
  ];

  return (
    <div className={cn("space-y-2.5", className)}>
      {entries.map((e) => (
        <div key={e.label} className="grid grid-cols-[80px_1fr_32px] sm:grid-cols-[100px_1fr_36px] items-center gap-2.5 sm:gap-3">
          <span className="text-[10px] sm:text-[11px] uppercase tracking-wider text-ink-400 truncate">
            {e.label}
          </span>
          <div className="score-bar">
            <span
              style={{ width: `${Math.round((e.value ?? 0) * 100)}%` }}
              className={cn(
                e.tone === "cyan" && "!bg-gradient-to-r !from-accent-cyan-dim !to-accent-cyan",
                e.tone === "violet" && "!bg-gradient-to-r !from-accent-violet !to-accent-violet/60",
                e.tone === "neutral" && "!bg-gradient-to-r !from-white/30 !to-white/10",
              )}
            />
          </div>
          <span className="num text-right text-xs font-medium tabular-nums text-ink-200">
            {Math.round((e.value ?? 0) * 100)}
          </span>
        </div>
      ))}
      {total !== undefined && (
        <div className="mt-3 flex items-center justify-between border-t border-white/[0.06] pt-3">
          <span className="text-[11px] uppercase tracking-[0.18em] text-ink-400">
            Total score
          </span>
          <span className="num text-base font-semibold text-ink-50">
            {Math.round(total * 100)}
          </span>
        </div>
      )}
    </div>
  );
}
