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
    label: "Сервер подключён",
    icon: PlugZap,
    // Border + text color only — solid backdrop comes from the wrapper.
    klass: "border-state-success/40 text-state-success",
  },
  worker_stale: {
    label: "Процесс молчит",
    icon: AlertTriangle,
    klass: "border-accent-amber/40 text-accent-amber",
  },
  missing_integrations: {
    label: "Нет подключений",
    icon: Radio,
    klass: "border-accent-amber/40 text-accent-amber",
  },
  fallback: {
    label: "Демо без сервера",
    icon: Plug,
    klass: "border-accent-amber/40 text-accent-amber",
  },
};

export function ApiConnectionBadge({ connection }: { connection: ApiConnection }) {
  const style = STYLE_FOR[connection.state];
  const Icon = style.icon;
  const titleParts = [`Сервер: ${connection.base}`];
  if (connection.worker_overall) titleParts.push(`фоновый процесс: ${connection.worker_overall}`);
  if (connection.missing && connection.missing.length > 0) {
    titleParts.push(`не хватает: ${connection.missing.join(", ")}`);
  }
  return (
    <div
      className={cn(
        // Solid dark backdrop + blur so scrolled content underneath does
        // not bleed through the badge on mobile.
        "inline-flex items-center gap-1.5 rounded-full border bg-bg-base/90 px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] shadow-sm backdrop-blur-md sm:px-3 sm:py-1.5 sm:text-[11px]",
        style.klass,
      )}
      title={titleParts.join(" · ")}
    >
      <Icon className="h-3 w-3 sm:h-3.5 sm:w-3.5" strokeWidth={2.2} />
      {style.label}
    </div>
  );
}
