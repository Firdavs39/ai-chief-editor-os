"use client";

import * as React from "react";
import Link from "next/link";
import { CheckCircle2, Pencil, XCircle, Sparkles, Clock } from "lucide-react";
import type { Candidate } from "@/lib/types";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { timeAgo } from "@/lib/utils";

const RECOMMENDATION_RU: Record<string, string> = {
  approve: "ИИ советует: одобрить",
  revise: "ИИ советует: доработать",
  reject: "ИИ советует: отклонить",
};

export function ApprovalCard({
  candidate,
  onApprove,
  onReject,
}: {
  candidate: Candidate;
  onApprove?: (c: Candidate) => void;
  onReject?: (c: Candidate) => void;
}) {
  const viral = Math.round(candidate.viral_score * 100);
  const styleFit = Math.round(candidate.style_match_score * 100);
  const slop = Math.round(candidate.slop_risk * 100);

  return (
    <Card className="group p-4">
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.15em] text-ink-500">
        <Clock className="h-3 w-3" />
        {timeAgo(candidate.created_at)}
        <span className="ml-auto normal-case tracking-normal">
          {RECOMMENDATION_RU[candidate.recommendation] ?? candidate.recommendation}
        </span>
      </div>

      <Link
        href={`/editor/${candidate.id}`}
        className="mt-2 block text-[14px] font-medium leading-snug text-ink-50 hover:text-white"
      >
        {candidate.topic}
      </Link>

      <p className="mt-2 line-clamp-3 text-xs leading-relaxed text-ink-300">
        {candidate.tg_version}
      </p>

      <div className="mt-3 flex flex-wrap gap-1.5">
        <Badge variant="violet">виральность {viral}</Badge>
        <Badge variant="cyan">стиль {styleFit}</Badge>
        <Badge variant={slop >= 30 ? "rose" : "outline"}>ИИ-штампы {slop}</Badge>
      </div>

      {candidate.critic_notes.length > 0 && (
        <div className="mt-3 space-y-1.5">
          {candidate.critic_notes.slice(0, 2).map((n, i) => (
            <div
              key={i}
              className="rounded-md border border-white/[0.06] bg-white/[0.02] px-2 py-1.5 text-[11px] text-ink-300"
            >
              <span
                className={
                  n.severity === "high"
                    ? "text-accent-rose"
                    : n.severity === "medium"
                    ? "text-accent-amber"
                    : "text-ink-400"
                }
              >
                ● {n.check}
              </span>{" "}
              — {n.note}
            </div>
          ))}
        </div>
      )}

      <div className="mt-4 grid grid-cols-3 gap-1.5">
        {/* Если обработчики не переданы (например, на Главной — это серверный
           компонент), кнопки ведут на доску одобрения, где действие реально
           выполняется. Так клик всегда даёт видимый результат, а не "тишину". */}
        {onApprove ? (
          <Button
            size="sm"
            variant="outline"
            className="text-accent-mint hover:bg-accent-mint/10 hover:text-accent-mint"
            onClick={() => onApprove(candidate)}
          >
            <CheckCircle2 className="h-3.5 w-3.5" /> Одобрить
          </Button>
        ) : (
          <Button
            size="sm"
            variant="outline"
            asChild
            className="text-accent-mint hover:bg-accent-mint/10 hover:text-accent-mint"
          >
            <Link href={`/approvals?candidate=${candidate.id}`}>
              <CheckCircle2 className="h-3.5 w-3.5" /> Одобрить →
            </Link>
          </Button>
        )}
        <Button
          size="sm"
          variant="outline"
          asChild
        >
          <Link href={`/editor/${candidate.id}`}>
            <Pencil className="h-3.5 w-3.5" /> Открыть
          </Link>
        </Button>
        {onReject ? (
          <Button
            size="sm"
            variant="outline"
            className="text-accent-rose hover:bg-accent-rose/10 hover:text-accent-rose"
            onClick={() => onReject(candidate)}
          >
            <XCircle className="h-3.5 w-3.5" /> Отклонить
          </Button>
        ) : (
          <Button
            size="sm"
            variant="outline"
            asChild
            className="text-accent-rose hover:bg-accent-rose/10 hover:text-accent-rose"
          >
            <Link href={`/approvals?candidate=${candidate.id}`}>
              <XCircle className="h-3.5 w-3.5" /> Отклонить →
            </Link>
          </Button>
        )}
      </div>
    </Card>
  );
}

type ColumnTone = "amber" | "mint" | "rose" | "cyan";

const COLUMN_DOT: Record<ColumnTone, string> = {
  amber: "bg-accent-amber",
  mint: "bg-accent-mint",
  rose: "bg-accent-rose",
  cyan: "bg-accent-cyan",
};

export function ApprovalColumn({
  title,
  badge,
  tone,
  children,
}: {
  title: string;
  badge?: number;
  tone: ColumnTone;
  children: React.ReactNode;
}) {
  return (
    <div className="flex w-[280px] sm:w-[320px] lg:w-auto lg:min-w-0 shrink-0 flex-col snap-start">
      <div className="mb-3 flex items-center justify-between rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2">
        <div className="flex items-center gap-2 text-sm font-medium text-ink-100">
          <span className={"h-1.5 w-1.5 rounded-full " + COLUMN_DOT[tone]} />
          {title}
        </div>
        {badge !== undefined && <Badge variant={tone}>{badge}</Badge>}
      </div>
      <div className="kanban-col flex flex-col gap-3 pr-1">{children}</div>
    </div>
  );
}
