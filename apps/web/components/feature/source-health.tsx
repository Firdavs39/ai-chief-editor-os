import * as React from "react";
import { Radio, Rss, Globe2, MessageCircle, RefreshCw } from "lucide-react";
import type { Source } from "@/lib/types";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn, timeAgo } from "@/lib/utils";

const KIND_ICON: Record<Source["kind"], React.ComponentType<{ className?: string; strokeWidth?: number }>> = {
  telegram: MessageCircle,
  reddit: Radio,
  rss: Rss,
  manual: Globe2,
};

const KIND_TONE: Record<Source["kind"], string> = {
  telegram: "from-accent-violet/25 to-accent-violet/5",
  reddit: "from-accent-amber/25 to-accent-amber/5",
  rss: "from-accent-cyan/25 to-accent-cyan/5",
  manual: "from-white/[0.06] to-white/[0.01]",
};

export function SourceHealthCard({
  source,
  mode = "mock",
}: {
  source: Source;
  mode?: "mock" | "live";
}) {
  const Icon = KIND_ICON[source.kind];
  const ok = (source.health?.ok ?? true) === true;
  const disabled = !source.enabled;

  const stateColor = disabled
    ? "bg-ink-500"
    : !ok
    ? "bg-state-danger"
    : mode === "live"
    ? "bg-state-success"
    : "bg-accent-cyan";

  const stateLabel = disabled ? "выключен" : !ok ? "ошибка" : mode === "live" ? "вживую" : "демо";

  return (
    <Card
      interactive
      className="group flex items-center gap-3 p-3 sm:p-4 3xl:p-5"
    >
      <div
        className={cn(
          "grid h-9 w-9 sm:h-10 sm:w-10 3xl:h-12 3xl:w-12 place-items-center rounded-xl bg-gradient-to-br ring-1 ring-white/[0.06] shrink-0",
          KIND_TONE[source.kind],
        )}
      >
        <Icon className="h-4 w-4 3xl:h-5 3xl:w-5 text-ink-100" strokeWidth={1.8} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5 sm:gap-2 flex-wrap">
          <span className="truncate text-sm 3xl:text-[15px] font-medium text-ink-50">
            {source.title || source.handle}
          </span>
          <Badge
            variant={
              disabled ? "outline" : !ok ? "rose" : mode === "live" ? "mint" : "cyan"
            }
          >
            <span className={cn("h-1.5 w-1.5 rounded-full", stateColor)} />
            {stateLabel}
          </Badge>
          <Badge variant="outline" className="hidden sm:inline-flex uppercase">
            {source.kind}
          </Badge>
        </div>
        <div className="mt-0.5 truncate text-[11px] sm:text-xs text-ink-400 font-mono">
          {source.handle}
        </div>
        <div className="mt-1 flex items-center gap-3 text-[10px] sm:text-[11px] text-ink-500 flex-wrap">
          <span className="num">
            вес <span className="text-ink-300">{source.weight.toFixed(1)}</span>
          </span>
          <span>проверено {timeAgo(source.last_collected_at)}</span>
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <button
          type="button"
          className="hidden sm:flex h-8 w-8 items-center justify-center rounded-lg border border-white/[0.07] bg-white/[0.025] text-ink-300 transition-colors opacity-0 group-hover:opacity-100 hover:text-ink-100 hover:bg-white/[0.05] hover:border-white/[0.12]"
          aria-label="Обновить источник"
          title="Обновить (демо)"
        >
          <RefreshCw className="h-3.5 w-3.5" />
        </button>
        <div className="text-right">
          <div className="text-[10px] sm:text-[11px] uppercase tracking-[0.18em] text-ink-500">
            статус
          </div>
          <div
            className={
              "mt-1 text-[11px] sm:text-xs font-medium " +
              (source.enabled ? "text-state-success" : "text-ink-400")
            }
          >
            {source.enabled ? "ВКЛ" : "ВЫКЛ"}
          </div>
        </div>
      </div>
    </Card>
  );
}
