import * as React from "react";
import Link from "next/link";
import { CheckCircle2, ExternalLink, Shield, Sparkles } from "lucide-react";
import { Toaster } from "sonner";
import { Topbar } from "@/components/layout/topbar";
import { PageShell, PageSection } from "@/components/layout/page-shell";
import { ApprovalColumn } from "@/components/feature/approval-card";
import { ApprovalActions } from "@/components/feature/approval-actions";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { data } from "@/lib/data";
import { timeAgo } from "@/lib/utils";

export default async function ApprovalsPage() {
  const [candidates, jobs, status] = await Promise.all([
    data.candidates(),
    data.jobs(),
    data.status(),
  ]);
  const pending = candidates.filter((c) => c.status === "draft" || c.status === "revised");
  const approved = candidates.filter((c) => c.status === "approved");
  const published = candidates.filter((c) => c.status === "published");
  const rejected = candidates.filter((c) => c.status === "rejected");

  const candJob: Record<string, string> = {};
  for (const j of jobs) {
    // last job per candidate wins
    candJob[j.candidate_id] = j.status;
  }

  return (
    <>
      <Toaster theme="dark" position="top-right" />
      <Topbar
        title="Approval Board"
        subtitle="Каждый пост проходит явный approval. Никаких автопостов."
        pill={{ label: `${pending.length} pending`, tone: "violet" }}
        actions={
          <Button size="sm" asChild>
            <Link href="/editor">
              <Sparkles className="h-4 w-4" /> Open editor
            </Link>
          </Button>
        }
      />
      <PageShell>
        <Card tone="violet" className="overflow-hidden p-4 sm:p-5">
          <div className="flex items-center gap-3 sm:gap-4">
            <div className="grid h-10 w-10 sm:h-11 sm:w-11 place-items-center rounded-xl bg-accent-violet/15 ring-1 ring-accent-violet/40 shrink-0">
              <Shield className="h-4 w-4 sm:h-5 sm:w-5 text-accent-violet" strokeWidth={2.2} />
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-sm sm:text-[15px] font-medium text-ink-50">
                Safety rule — nothing publishes without an approve decision
              </div>
              <div className="text-xs text-ink-400 leading-snug mt-0.5">
                Approval создаёт PublishJob. Worker и Publisher re-validate перед каждой отправкой —
                три точки контроля.
              </div>
            </div>
            <Badge variant="violet" className="hidden sm:inline-flex">
              defense in depth
            </Badge>
          </div>
        </Card>

        <PageSection
          title="Pipeline"
          description="Kanban-доска: pending → approved → published, rejected отдельно"
          action={
            <div className="flex items-center gap-2 text-[11px] text-ink-400">
              <span className="num">{candidates.length}</span> candidates total
            </div>
          }
        >
          <div className="flex gap-3 sm:gap-4 overflow-x-auto pb-2 snap-x snap-mandatory lg:grid lg:grid-cols-4 lg:overflow-visible lg:snap-none">
            <ApprovalColumn title="Pending review" tone="amber" badge={pending.length}>
              {pending.map((c) => (
                <Card key={c.id} className="p-4">
                  <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.15em] text-ink-500">
                    <span>{timeAgo(c.created_at)}</span>
                    <span className="ml-auto">v{c.version}</span>
                  </div>
                  <Link
                    href={`/editor/${c.id}`}
                    className="mt-2 block text-sm font-medium text-ink-50 hover:text-white"
                  >
                    {c.topic}
                  </Link>
                  <p className="mt-2 line-clamp-3 text-xs text-ink-300">{c.tg_version}</p>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    <Badge variant="violet">viral {Math.round(c.viral_score * 100)}</Badge>
                    <Badge variant="cyan">style {Math.round(c.style_match_score * 100)}</Badge>
                    {Math.round(c.slop_risk * 100) >= 30 && (
                      <Badge variant="rose">slop {Math.round(c.slop_risk * 100)}</Badge>
                    )}
                  </div>
                  <div className="mt-3">
                    <ApprovalActions candidate={c} />
                  </div>
                </Card>
              ))}
              {pending.length === 0 && (
                <Card className="p-6 text-center text-xs text-ink-400">
                  Ничего на проверке. Сгенерируй кандидата.
                </Card>
              )}
            </ApprovalColumn>

            <ApprovalColumn title="Approved & scheduled" tone="cyan" badge={approved.length}>
              {approved.map((c) => {
                const jobStatus = candJob[c.id];
                const jobMeta = describeJob(jobStatus, status);
                return (
                  <Card key={c.id} className="p-4">
                    <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.15em] text-ink-500">
                      <Badge variant={jobMeta.variant}>{jobMeta.label}</Badge>
                      <span className="ml-auto">v{c.version}</span>
                    </div>
                    <Link
                      href={`/editor/${c.id}`}
                      className="mt-2 block text-sm font-medium text-ink-50 hover:text-white"
                    >
                      {c.topic}
                    </Link>
                    <p className="mt-2 line-clamp-2 text-xs text-ink-300">{c.tg_version}</p>
                    <div className="mt-3 flex items-center gap-2 text-[11px] text-ink-400">
                      <span className={"shrink-0 h-1.5 w-1.5 rounded-full " + jobMeta.dot} />
                      {jobMeta.hint}
                    </div>
                  </Card>
                );
              })}
              {approved.length === 0 && (
                <Card className="p-6 text-center text-xs text-ink-400">
                  No approved drafts in queue.
                </Card>
              )}
            </ApprovalColumn>

            <ApprovalColumn title="Published" tone="mint" badge={published.length}>
              {published.map((c) => (
                <Card key={c.id} className="p-4">
                  <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.15em] text-ink-500">
                    <Badge variant="mint">
                      <CheckCircle2 className="h-3 w-3" /> published
                    </Badge>
                    <span className="ml-auto">v{c.version}</span>
                  </div>
                  <Link
                    href={`/editor/${c.id}`}
                    className="mt-2 block text-sm font-medium text-ink-50 hover:text-white"
                  >
                    {c.topic}
                  </Link>
                  <p className="mt-2 line-clamp-2 text-xs text-ink-300">{c.tg_version}</p>
                  <div className="mt-3 flex items-center gap-2 text-[11px] text-ink-500">
                    <ExternalLink className="h-3 w-3" />
                    live on platform
                  </div>
                </Card>
              ))}
              {published.length === 0 && (
                <Card className="p-6 text-center text-xs text-ink-400">
                  Ничего ещё не опубликовано.
                </Card>
              )}
            </ApprovalColumn>

            <ApprovalColumn title="Rejected" tone="rose" badge={rejected.length}>
              {rejected.map((c) => (
                <Card key={c.id} className="p-4 opacity-75">
                  <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.15em] text-ink-500">
                    <Badge variant="rose">rejected</Badge>
                    <span className="ml-auto">{timeAgo(c.created_at)}</span>
                  </div>
                  <Link
                    href={`/editor/${c.id}`}
                    className="mt-2 block text-sm font-medium text-ink-200 hover:text-white"
                  >
                    {c.topic}
                  </Link>
                  <p className="mt-1.5 line-clamp-2 text-xs text-ink-400">{c.tg_version}</p>
                </Card>
              ))}
              {rejected.length === 0 && (
                <Card className="p-6 text-center text-xs text-ink-400">
                  Ничего не отклонено.
                </Card>
              )}
            </ApprovalColumn>
          </div>
        </PageSection>
      </PageShell>
    </>
  );
}

type JobMeta = {
  label: string;
  hint: string;
  variant: "cyan" | "violet" | "amber" | "rose" | "mint" | "outline";
  dot: string;
};

function describeJob(jobStatus: string | undefined, status: { publishing_enabled: boolean; dry_run_publish: boolean }): JobMeta {
  if (jobStatus === "blocked") {
    return {
      label: "blocked",
      hint: "PUBLISHING_ENABLED is OFF — admin must enable publishing.",
      variant: "rose",
      dot: "bg-state-danger",
    };
  }
  if (jobStatus === "pending_config") {
    return {
      label: "pending config",
      hint: "Publisher not configured for the chosen platform.",
      variant: "amber",
      dot: "bg-accent-amber",
    };
  }
  if (jobStatus === "dry_run") {
    return {
      label: "dry-run only",
      hint: "Payload was computed but nothing was sent.",
      variant: "cyan",
      dot: "bg-accent-cyan",
    };
  }
  if (jobStatus === "done") {
    return {
      label: "published",
      hint: "Live on the platform.",
      variant: "mint",
      dot: "bg-state-success",
    };
  }
  if (jobStatus === "failed") {
    return {
      label: "failed",
      hint: "Publisher returned an error — see SystemLog.",
      variant: "rose",
      dot: "bg-state-danger",
    };
  }
  if (!status.publishing_enabled) {
    return {
      label: "queued (blocked)",
      hint: "Master switch off — job will not dispatch.",
      variant: "amber",
      dot: "bg-accent-amber",
    };
  }
  if (status.dry_run_publish) {
    return {
      label: "queued (dry-run)",
      hint: "Will be processed as dry-run — no external send.",
      variant: "cyan",
      dot: "bg-accent-cyan",
    };
  }
  return {
    label: "queued",
    hint: "Worker will dispatch on schedule.",
    variant: "cyan",
    dot: "bg-accent-cyan",
  };
}
