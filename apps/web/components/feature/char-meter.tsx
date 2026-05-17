import * as React from "react";
import { cn } from "@/lib/utils";

export function CharMeter({
  current,
  max,
  label,
}: {
  current: number;
  max: number;
  label?: string;
}) {
  const ratio = Math.min(1, current / max);
  const over = current > max;
  const pct = Math.round(ratio * 100);
  return (
    <div className="flex items-center gap-2 text-[11px]">
      {label && <span className="uppercase tracking-[0.15em] text-ink-500">{label}</span>}
      <div className="num text-ink-300">
        <span className={cn(over ? "text-state-danger font-medium" : pct > 85 ? "text-accent-amber" : "text-ink-100")}>
          {current}
        </span>
        <span className="text-ink-500"> / {max}</span>
      </div>
      <div className="relative h-1 w-24 overflow-hidden rounded-full bg-white/[0.06]">
        <span
          className={cn(
            "absolute inset-y-0 left-0",
            over
              ? "bg-state-danger"
              : pct > 85
              ? "bg-accent-amber"
              : "bg-gradient-to-r from-accent-violet to-accent-cyan",
          )}
          style={{ width: `${Math.min(100, pct)}%` }}
        />
      </div>
    </div>
  );
}
