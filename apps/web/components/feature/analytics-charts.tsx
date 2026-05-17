"use client";

import * as React from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const VIOLET = "#8b5cf6";
const CYAN = "#22d3ee";

const tooltipStyles = {
  contentStyle: {
    background: "rgba(12, 14, 20, 0.92)",
    border: "1px solid rgba(255,255,255,0.08)",
    borderRadius: 12,
    fontSize: 11,
    color: "#e7e9ee",
    padding: "8px 10px",
  },
  itemStyle: { color: "#e7e9ee" },
  labelStyle: { color: "#a5abb8" },
};

export function HookTypeChart({
  data,
}: {
  data: { hook_type: string; viral_avg: number; posts: number }[];
}) {
  return (
    <div className="h-[180px] sm:h-[220px] 3xl:h-[280px] 4xl:h-[340px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <defs>
            <linearGradient id="barGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={VIOLET} stopOpacity={0.95} />
              <stop offset="100%" stopColor={VIOLET} stopOpacity={0.45} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="rgba(255,255,255,0.04)" vertical={false} />
          <XAxis
            dataKey="hook_type"
            stroke="rgba(255,255,255,0.4)"
            fontSize={11}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            stroke="rgba(255,255,255,0.4)"
            fontSize={11}
            tickLine={false}
            axisLine={false}
            domain={[0, 1]}
            tickFormatter={(v) => Math.round(v * 100).toString()}
          />
          <Tooltip
            {...tooltipStyles}
            formatter={(v: number) => [`${Math.round(v * 100)}`, "viral score"]}
          />
          <Bar
            dataKey="viral_avg"
            fill="url(#barGrad)"
            radius={[8, 8, 4, 4]}
            maxBarSize={48}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function LearningTimelineChart({
  data,
}: {
  data: { date: string; avg_engagement: number }[];
}) {
  return (
    <div className="h-[180px] sm:h-[220px] 3xl:h-[280px] 4xl:h-[340px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data}>
          <defs>
            <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={CYAN} stopOpacity={0.6} />
              <stop offset="100%" stopColor={CYAN} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="rgba(255,255,255,0.04)" vertical={false} />
          <XAxis
            dataKey="date"
            stroke="rgba(255,255,255,0.4)"
            fontSize={11}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => v.slice(5)}
          />
          <YAxis
            stroke="rgba(255,255,255,0.4)"
            fontSize={11}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => (v >= 1000 ? `${(v / 1000).toFixed(1)}K` : String(v))}
          />
          <Tooltip
            {...tooltipStyles}
            formatter={(v: number) => [v.toLocaleString(), "engagement"]}
          />
          <Area
            type="monotone"
            dataKey="avg_engagement"
            stroke={CYAN}
            strokeWidth={2}
            fill="url(#areaGrad)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function SourcePerformanceChart({
  data,
}: {
  data: { source: string; avg_engagement: number; posts: number }[];
}) {
  return (
    <div className="h-[180px] sm:h-[220px] 3xl:h-[280px] 4xl:h-[340px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical">
          <CartesianGrid stroke="rgba(255,255,255,0.04)" horizontal={false} />
          <XAxis
            type="number"
            stroke="rgba(255,255,255,0.4)"
            fontSize={11}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            type="category"
            dataKey="source"
            stroke="rgba(255,255,255,0.4)"
            fontSize={11}
            tickLine={false}
            axisLine={false}
            width={120}
          />
          <Tooltip
            {...tooltipStyles}
            formatter={(v: number) => [v.toLocaleString(), "avg engagement"]}
          />
          <Bar dataKey="avg_engagement" radius={[0, 8, 8, 0]} maxBarSize={20}>
            {data.map((_, i) => (
              <Cell key={i} fill={i % 2 === 0 ? VIOLET : CYAN} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
