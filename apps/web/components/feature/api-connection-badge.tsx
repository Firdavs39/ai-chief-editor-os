"use client";

import * as React from "react";
import { AlertTriangle, Plug, PlugZap, Radio } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ApiConnection } from "@/lib/types";

const STYLE_FOR: Record<
  ApiConnection["state"],
  {
    label: string;
    icon: React.ComponentType<{ className?: string; strokeWidth?: number }>;
    klass: string;
  }
> = {
  connected: {
    label: "API connected",
    icon: PlugZap,
    klass: "border-state-success/30 bg-state-success/10 text-state-success",
  },
  worker_stale: {
    label: "Worker stale",
    icon: AlertTriangle,
    klass: "border-accent-amber/30 bg-accent-amber/10 text-accent-amber",
  },
  missing_integrations: {
    label: "Integrations missing",
    icon: Radio,
    klass: "border-accent-amber/30 bg-accent-amber/10 text-accent-amber",
  },
  fallback: {
    label: "Demo fallback",
    icon: Plug,
    klass: "border-accent-amber/30 bg-accent-amber/10 text-accent-amber",
  },
};

export function ApiConnectionBadge({ connection }: { connection: ApiConnection }) {
  const style = STYLE_FOR[connection.state];
  const Icon = style.icon;
  const titleParts = [`API: ${connection.base}`];
  if (connection.worker_overall) titleParts.push(`worker: ${connection.worker_overall}`);
  if (connection.missing && connection.missing.length > 0) {
    titleParts.push(`missing: ${connection.missing.join(", ")}`);
  }
  return (
    <div
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.18em]",
        style.klass,
      )}
      title={titleParts.join(" · ")}
    >
      <Icon className="h-3 w-3" strokeWidth={2.2} />
      {style.label}
    </div>
  );
}
