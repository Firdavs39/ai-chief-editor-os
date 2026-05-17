import * as React from "react";
import Link from "next/link";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  MessageCircle,
  Radio,
  Shield,
  Sparkles,
  Type,
  XCircle,
} from "lucide-react";
import { Toaster } from "sonner";
import { Topbar } from "@/components/layout/topbar";
import { PageShell } from "@/components/layout/page-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { RewriteToolbar } from "@/components/feature/rewrite-toolbar";
import { EditorApprovalBar } from "@/components/feature/editor-approval-bar";
import { CharMeter } from "@/components/feature/char-meter";
import { DryRunButton } from "@/components/feature/dry-run-button";
import { data } from "@/lib/data";
import { cn, timeAgo } from "@/lib/utils";

export default async function EditorDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const [candidate, status] = await Promise.all([data.candidate(id), data.status()]);

  const score = (n: number) => Math.round(n * 100);

  // Platform readiness (computed from /status adapters)
  const tgReady = status.adapters.telegram_publish || status.mock_mode;
  const threadsReady = status.adapters.postiz || status.mock_mode;
  const redditReady = status.adapters.postiz || status.mock_mode;
  const publishingOff = !status.publishing_enabled;
  const dryRunOn = status.dry_run_publish;

  return (
    <>
      <Toaster theme="dark" position="top-right" />
      <Topbar
        title={candidate.topic || "Candidate"}
        subtitle={`v${candidate.version} · ${timeAgo(candidate.created_at)}`}
        pill={{
          label: candidate.status,
          tone:
            candidate.status === "approved" || candidate.status === "published" ? "cyan" : "violet",
        }}
        actions={
          <>
            <Button variant="outline" size="sm" asChild>
              <Link href="/editor">Back</Link>
            </Button>
            <DryRunButton candidateId={candidate.id} />
            <Button variant="secondary" size="sm" asChild>
              <Link href={`/approvals?candidate=${candidate.id}`}>
                <CheckCircle2 className="h-4 w-4" /> Board
              </Link>
            </Button>
          </>
        }
      />
      <PageShell className="pt-3 sm:pt-4">
        {/* Platform readiness + safety badges */}
        <Card className="overflow-hidden p-3 sm:p-3.5">
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-[0.18em] text-ink-500 mr-1">
              <Shield className="h-3 w-3" />
              Publish readiness
            </div>
            <PlatformReadiness label="Telegram" ready={tgReady} mock={status.mock_mode} />
            <PlatformReadiness label="Threads via Postiz" ready={threadsReady} mock={status.mock_mode} />
            <PlatformReadiness label="Reddit via Postiz" ready={redditReady} mock={status.mock_mode} />
            <div className="ml-auto flex flex-wrap items-center gap-1.5">
              {publishingOff && (
                <Badge variant="amber">
                  <span className="h-1.5 w-1.5 rounded-full bg-accent-amber" />
                  publishing disabled
                </Badge>
              )}
              {dryRunOn && (
                <Badge variant="cyan">
                  <span className="h-1.5 w-1.5 rounded-full bg-accent-cyan" />
                  dry-run mode
                </Badge>
              )}
              <Badge variant="violet">
                <Shield className="h-3 w-3" />
                approval required
              </Badge>
            </div>
          </div>
        </Card>

        {/* Score header strip — traffic-light scores visible at first glance */}
        <Card className="overflow-hidden p-3 sm:p-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <ScoreChip label="Style match" value={score(candidate.style_match_score)} tone="cyan" />
            <ScoreChip label="Viral potential" value={score(candidate.viral_score)} tone="violet" />
            <ScoreChip
              label="AI-slop risk"
              value={score(candidate.slop_risk)}
              tone="rose"
              invert
            />
            <ScoreChip
              label="Controversy"
              value={score(candidate.controversy_risk)}
              tone="amber"
              invert
            />
          </div>
        </Card>

        <div className="grid gap-4 lg:gap-5 xl:gap-6 xl:grid-cols-[1fr_1.6fr_1fr] 3xl:grid-cols-[1fr_1.8fr_1fr]">
          {/* Left rail: source brief + scores */}
          <div className="space-y-3 sm:space-y-4 xl:order-1 order-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Source brief</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm leading-relaxed text-ink-200">
                <div>
                  <div className="text-[10px] uppercase tracking-[0.18em] text-ink-500">
                    What we saw
                  </div>
                  <p className="mt-1">{candidate.source_summary}</p>
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-[0.18em] text-ink-500">
                    Why it matters
                  </div>
                  <p className="mt-1">{candidate.why_it_matters}</p>
                </div>
                <div className="rounded-xl border border-accent-violet/20 bg-accent-violet/[0.06] p-3">
                  <div className="text-[10px] uppercase tracking-[0.18em] text-accent-violet/80">
                    Psychology hook
                  </div>
                  <p className="mt-1.5 text-[14px] italic text-ink-50 leading-snug">
                    «{candidate.psychology_hook}»
                  </p>
                </div>
              </CardContent>
            </Card>

            <Card tone="violet">
              <CardHeader>
                <CardTitle className="text-sm">Risk scores</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <ScoreRow
                  label="Style match"
                  value={score(candidate.style_match_score)}
                  tone="cyan"
                />
                <ScoreRow
                  label="Viral potential"
                  value={score(candidate.viral_score)}
                  tone="violet"
                />
                <ScoreRow label="AI-slop risk" value={score(candidate.slop_risk)} tone="rose" />
                <ScoreRow
                  label="Controversy"
                  value={score(candidate.controversy_risk)}
                  tone="amber"
                />
                <Separator className="my-2" />
                <div className="flex items-center justify-between">
                  <span className="text-[11px] uppercase tracking-[0.18em] text-ink-500">
                    AI recommends
                  </span>
                  {candidate.recommendation === "approve" && (
                    <Badge variant="mint">
                      <CheckCircle2 className="h-3 w-3" /> Approve
                    </Badge>
                  )}
                  {candidate.recommendation === "revise" && (
                    <Badge variant="amber">Revise</Badge>
                  )}
                  {candidate.recommendation === "reject" && (
                    <Badge variant="rose">
                      <XCircle className="h-3 w-3" /> Reject
                    </Badge>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Center: editor */}
          <div className="space-y-3 xl:order-2 order-1">
            <Tabs defaultValue="tg" className="w-full">
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <TabsList className="overflow-x-auto">
                  <TabsTrigger value="tg">
                    <MessageCircle className="h-3 w-3" /> Telegram
                  </TabsTrigger>
                  <TabsTrigger value="threads">
                    <Type className="h-3 w-3" /> Threads
                  </TabsTrigger>
                  <TabsTrigger value="reddit">
                    <Radio className="h-3 w-3" /> Reddit
                  </TabsTrigger>
                </TabsList>
              </div>

              <TabsContent value="tg">
                <Card>
                  <CardContent className="space-y-3 p-3 sm:p-4">
                    <Textarea
                      defaultValue={candidate.tg_version}
                      className="min-h-[200px] sm:min-h-[260px] xl:min-h-[280px] 3xl:min-h-[360px] resize-y font-sans text-[13px] sm:text-[14px] leading-relaxed"
                    />
                    <div className="flex items-center justify-between gap-3 flex-wrap">
                      <CharMeter
                        current={candidate.tg_version.length}
                        max={1024}
                        label="Telegram"
                      />
                      <RewriteToolbar candidateId={candidate.id} target="tg" />
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="threads">
                <Card>
                  <CardContent className="space-y-3 p-3 sm:p-4">
                    <Textarea
                      defaultValue={candidate.threads_version}
                      className="min-h-[180px] sm:min-h-[220px] xl:min-h-[240px] 3xl:min-h-[320px] resize-y font-sans text-[13px] sm:text-[14px] leading-relaxed"
                    />
                    <div className="flex items-center justify-between gap-3 flex-wrap">
                      <CharMeter
                        current={candidate.threads_version.length}
                        max={500}
                        label="Threads"
                      />
                      <RewriteToolbar candidateId={candidate.id} target="threads" />
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="reddit">
                <Card>
                  <CardContent className="space-y-3 p-3 sm:p-4">
                    <Textarea
                      defaultValue={candidate.reddit_version}
                      className="min-h-[200px] sm:min-h-[240px] xl:min-h-[260px] 3xl:min-h-[340px] resize-y font-sans text-[13px] sm:text-[14px] leading-relaxed"
                    />
                    <div className="flex items-center justify-between gap-3 flex-wrap">
                      <CharMeter
                        current={candidate.reddit_version.length}
                        max={1500}
                        label="Reddit"
                      />
                      <RewriteToolbar candidateId={candidate.id} target="reddit" />
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-accent-violet" /> Call to action
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-ink-100">
                <Textarea
                  defaultValue={candidate.cta}
                  className="min-h-[72px] resize-y"
                />
              </CardContent>
            </Card>
          </div>

          {/* Right: critic */}
          <div className="space-y-3 sm:space-y-4 xl:order-3 order-3">
            <Card tone="cyan">
              <CardHeader>
                <CardTitle className="text-sm flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-accent-amber" /> Critic notes
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {candidate.critic_notes.length === 0 && (
                  <div className="flex items-center gap-2 rounded-lg border border-state-success/20 bg-state-success/[0.05] p-2.5 text-[13px] text-state-success">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    Clean. No major issues — ready for approval.
                  </div>
                )}
                {candidate.critic_notes.map((n, i) => (
                  <div
                    key={i}
                    className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-3"
                  >
                    <div className="flex items-center gap-2 flex-wrap">
                      <span
                        className={cn(
                          "h-1.5 w-1.5 rounded-full",
                          n.severity === "high" && "bg-state-danger",
                          n.severity === "medium" && "bg-accent-amber",
                          n.severity === "low" && "bg-ink-400",
                        )}
                      />
                      <span className="text-[11px] uppercase tracking-wider text-ink-300">
                        {n.check}
                      </span>
                      <Badge
                        variant={
                          n.severity === "high"
                            ? "rose"
                            : n.severity === "medium"
                            ? "amber"
                            : "outline"
                        }
                      >
                        {n.severity}
                      </Badge>
                    </div>
                    <p className="mt-1.5 text-xs leading-relaxed text-ink-200">{n.note}</p>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm flex items-center gap-2">
                  <Clock className="h-4 w-4 text-accent-cyan" /> Versions
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-1.5 text-xs text-ink-300">
                <div className="flex items-center justify-between rounded-md bg-white/[0.02] px-2.5 py-1.5 ring-1 ring-accent-violet/20">
                  <span className="flex items-center gap-1.5">
                    <span className="dot-live" />
                    v{candidate.version} · current
                  </span>
                  <span className="text-ink-500">{timeAgo(candidate.created_at)}</span>
                </div>
                {candidate.version > 1 && (
                  <div className="flex items-center justify-between rounded-md bg-white/[0.02] px-2.5 py-1.5">
                    <span>v{Math.max(1, candidate.version - 1)} · initial</span>
                    <span className="text-ink-500">{timeAgo(candidate.created_at)}</span>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>

        <EditorApprovalBar candidate={candidate} />
      </PageShell>
    </>
  );
}

function PlatformReadiness({
  label,
  ready,
  mock,
}: {
  label: string;
  ready: boolean;
  mock: boolean;
}) {
  const variant: "mint" | "cyan" | "amber" = ready
    ? mock
      ? "cyan"
      : "mint"
    : "amber";
  const dotClass = ready
    ? mock
      ? "bg-accent-cyan"
      : "bg-state-success"
    : "bg-accent-amber";
  const state = ready ? (mock ? "mock" : "ready") : "missing";
  return (
    <Badge variant={variant}>
      <span className={cn("h-1.5 w-1.5 rounded-full", dotClass)} />
      {label} · {state}
    </Badge>
  );
}

function ScoreChip({
  label,
  value,
  tone,
  invert,
}: {
  label: string;
  value: number;
  tone: "violet" | "cyan" | "rose" | "amber";
  invert?: boolean;
}) {
  // For invert (risk metrics), low = good. Map color accordingly.
  const isGood = invert ? value < 20 : value > 65;
  const isWarn = invert ? value >= 20 && value < 50 : value >= 40 && value <= 65;
  const dotColor = isGood
    ? "bg-state-success"
    : isWarn
    ? "bg-accent-amber"
    : invert
    ? "bg-state-danger"
    : tone === "violet"
    ? "bg-accent-violet"
    : "bg-accent-cyan";

  return (
    <div className="flex items-center gap-2.5 rounded-xl bg-white/[0.025] px-3 py-2.5 ring-1 ring-white/[0.05]">
      <span className={cn("h-2 w-2 rounded-full shrink-0", dotColor)} />
      <div className="min-w-0 flex-1">
        <div className="text-[10px] uppercase tracking-[0.18em] text-ink-500 truncate">
          {label}
        </div>
        <div className="num display text-base font-semibold leading-none text-ink-50 mt-0.5">
          {value}
          <span className="text-[11px] text-ink-500 ml-0.5 font-normal">
            {invert ? " risk" : ""}
          </span>
        </div>
      </div>
    </div>
  );
}

function ScoreRow({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "violet" | "cyan" | "rose" | "amber";
}) {
  const cls =
    tone === "violet"
      ? "from-accent-violet to-accent-violet/40"
      : tone === "cyan"
      ? "from-accent-cyan to-accent-cyan/40"
      : tone === "rose"
      ? "from-accent-rose to-accent-rose/40"
      : "from-accent-amber to-accent-amber/40";
  return (
    <div className="grid grid-cols-[96px_1fr_32px] sm:grid-cols-[120px_1fr_36px] items-center gap-2.5 sm:gap-3">
      <span className="text-[10px] sm:text-[11px] uppercase tracking-wider text-ink-400 truncate">
        {label}
      </span>
      <div className="score-bar">
        <span style={{ width: `${value}%` }} className={cn("!bg-gradient-to-r", cls)} />
      </div>
      <span className="num text-right text-xs font-medium text-ink-100">{value}</span>
    </div>
  );
}
