import * as React from "react";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";

type Trend = "up" | "down" | "flat";

export function StatCard({
  label,
  value,
  hint,
  trend,
  icon: Icon,
  tone = "default",
  spark,
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
  trend?: { direction: Trend; delta: string };
  icon?: React.ComponentType<{ className?: string; strokeWidth?: number }>;
  tone?: "default" | "violet" | "cyan";
  spark?: number[];
}) {
  return (
    <Card tone={tone} className="relative overflow-hidden p-3.5 sm:p-4 lg:p-5 3xl:p-6">
      <div className="absolute right-2.5 top-2.5 sm:right-3 sm:top-3 grid h-7 w-7 sm:h-8 sm:w-8 place-items-center rounded-lg bg-white/[0.05] ring-1 ring-white/[0.04]">
        {Icon && <Icon className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-ink-200" strokeWidth={1.8} />}
      </div>
      <div className="text-[10px] sm:text-[11px] font-medium uppercase tracking-[0.18em] text-ink-400 pr-9">
        {label}
      </div>
      <div className="mt-1.5 sm:mt-2 flex items-baseline gap-2 flex-wrap">
        <div className="display num text-[24px] sm:text-[28px] lg:text-[30px] 3xl:text-[36px] 4xl:text-[44px] font-semibold tracking-tight text-ink-50 leading-none">
          {value}
        </div>
        {trend && (
          <span
            className={cn(
              "num text-[11px] sm:text-xs font-medium",
              trend.direction === "up" && "text-state-success",
              trend.direction === "down" && "text-state-danger",
              trend.direction === "flat" && "text-ink-400",
            )}
          >
            {trend.direction === "up" && "↑ "}
            {trend.direction === "down" && "↓ "}
            {trend.delta}
          </span>
        )}
      </div>
      {hint && <div className="mt-1 text-[11px] sm:text-xs text-ink-400">{hint}</div>}
      {spark && spark.length > 1 && (
        <Sparkline values={spark} tone={tone} />
      )}
    </Card>
  );
}

function Sparkline({
  values,
  tone = "default",
}: {
  values: number[];
  tone?: "default" | "violet" | "cyan";
}) {
  const stroke =
    tone === "violet" ? "#a78bfa" : tone === "cyan" ? "#22d3ee" : "rgba(255,255,255,0.45)";
  const fill =
    tone === "violet"
      ? "rgba(139, 92, 246, 0.18)"
      : tone === "cyan"
      ? "rgba(34, 211, 238, 0.18)"
      : "rgba(255, 255, 255, 0.06)";
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const w = 100;
  const h = 28;
  const step = values.length > 1 ? w / (values.length - 1) : w;
  const points = values
    .map((v, i) => `${(i * step).toFixed(2)},${(h - ((v - min) / range) * h).toFixed(2)}`)
    .join(" ");
  const areaPoints = `0,${h} ${points} ${w},${h}`;
  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      className="mt-3 h-7 w-full"
      preserveAspectRatio="none"
      aria-hidden
    >
      <polygon points={areaPoints} fill={fill} />
      <polyline points={points} fill="none" stroke={stroke} strokeWidth="1.4" />
    </svg>
  );
}
