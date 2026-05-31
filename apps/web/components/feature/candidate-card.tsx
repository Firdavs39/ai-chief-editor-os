import * as React from "react";
import Link from "next/link";
import { AlertTriangle, ArrowUpRight, CheckCircle2, RefreshCcw, Sparkles, XCircle } from "lucide-react";
import type { Candidate } from "@/lib/types";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn, timeAgo } from "@/lib/utils";

const STATUS_STYLES: Record<Candidate["status"], { label: string; badge: "violet" | "cyan" | "amber" | "mint" | "rose" }> = {
  draft: { label: "Черновик", badge: "amber" },
  approved: { label: "Одобрено", badge: "mint" },
  rejected: { label: "Отклонено", badge: "rose" },
  revised: { label: "Доработано", badge: "cyan" },
  published: { label: "Опубликовано", badge: "violet" },
};

// Простое русское склонение для "замечание / замечания / замечаний".
function pluralNotes(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return "замечание";
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return "замечания";
  return "замечаний";
}

export function CandidateCard({
  candidate,
  variant = "default",
}: {
  candidate: Candidate;
  variant?: "default" | "compact";
}) {
  const status = STATUS_STYLES[candidate.status] ?? STATUS_STYLES.draft;
  const viral = Math.round(candidate.viral_score * 100);
  const slop = Math.round(candidate.slop_risk * 100);
  const styleFit = Math.round(candidate.style_match_score * 100);
  const recommend = candidate.recommendation;

  return (
    <Card className={cn(
      "group relative flex flex-col p-4 sm:p-5 3xl:p-6 transition-shadow hover:shadow-elev",
      variant === "compact" && "p-3.5 sm:p-4",
    )}>
      <div className="flex items-center gap-1.5 sm:gap-2 flex-wrap">
        <Badge variant={status.badge}>{status.label}</Badge>
        <Badge variant="outline">v{candidate.version}</Badge>
        {recommend === "approve" && (
          <Badge variant="mint" className="hidden sm:inline-flex">
            <CheckCircle2 className="h-3 w-3" /> ИИ: одобрить
          </Badge>
        )}
        {recommend === "revise" && (
          <Badge variant="amber" className="hidden sm:inline-flex">
            <RefreshCcw className="h-3 w-3" /> ИИ: доработать
          </Badge>
        )}
        {recommend === "reject" && (
          <Badge variant="rose" className="hidden sm:inline-flex">
            <XCircle className="h-3 w-3" /> ИИ: отклонить
          </Badge>
        )}
        <span className="ml-auto text-[10px] text-ink-500">{timeAgo(candidate.created_at)}</span>
      </div>

      <Link
        href={`/editor/${candidate.id}`}
        className="mt-2.5 sm:mt-3 text-[14px] sm:text-[15px] 3xl:text-[16px] font-medium leading-snug text-ink-50 hover:text-white"
      >
        {candidate.topic}
      </Link>

      <p className={cn(
        "mt-1.5 sm:mt-2 text-[13px] sm:text-sm leading-relaxed text-ink-300",
        variant === "compact" ? "line-clamp-2" : "line-clamp-3",
      )}>
        {candidate.tg_version}
      </p>

      <div className="mt-3 sm:mt-4 grid grid-cols-3 gap-2 sm:gap-3 text-[10px] uppercase tracking-[0.15em] text-ink-500">
        <Metric label="Виральность" value={viral} tone="violet" />
        <Metric label="Стиль" value={styleFit} tone="cyan" />
        <Metric label="ИИ-штампы" value={slop} tone="rose" inverse />
      </div>

      {candidate.critic_notes.length > 0 && (
        <div className="mt-3 sm:mt-4 flex items-start gap-2 rounded-lg border border-accent-amber/20 bg-accent-amber/[0.06] p-2 sm:p-2.5">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent-amber" />
          <div className="text-[11px] sm:text-xs leading-relaxed text-ink-200">
            <span className="font-medium text-accent-amber">{candidate.critic_notes.length}</span>{" "}
            {pluralNotes(candidate.critic_notes.length)}:{" "}
            <span className="text-ink-300">{candidate.critic_notes[0].note}</span>
          </div>
        </div>
      )}

      <div className="mt-3 sm:mt-4 flex items-center justify-between border-t border-white/[0.06] pt-2.5 sm:pt-3">
        <Link
          href={`/editor/${candidate.id}`}
          className="link inline-flex items-center gap-1.5 text-xs font-medium text-accent-cyan"
        >
          <Sparkles className="h-3 w-3" />
          Открыть и редактировать
        </Link>
        <Link
          href={`/approvals?candidate=${candidate.id}`}
          className="inline-flex items-center gap-1 text-xs text-ink-300 hover:text-ink-50"
        >
          На доску <ArrowUpRight className="h-3 w-3" />
        </Link>
      </div>
    </Card>
  );
}

function Metric({
  label,
  value,
  tone,
  inverse,
}: {
  label: string;
  value: number;
  tone: "violet" | "cyan" | "rose";
  inverse?: boolean;
}) {
  const colorClass =
    tone === "violet"
      ? "text-accent-violet"
      : tone === "cyan"
      ? "text-accent-cyan"
      : "text-accent-rose";
  return (
    <div className="rounded-lg bg-white/[0.02] px-2 py-1.5">
      <div className={cn("text-[10px] tracking-[0.18em]", "text-ink-500")}>
        {label}
      </div>
      <div className={cn("num mt-0.5 text-sm font-semibold", colorClass)}>
        {value}
        <span className="text-[10px] text-ink-500 ml-0.5">{inverse ? " риск" : ""}</span>
      </div>
    </div>
  );
}
