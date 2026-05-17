import * as React from "react";
import {
  AlertTriangle,
  Beaker,
  CircleDot,
  KeyRound,
  Plug,
  PlugZap,
  Radio,
  Shield,
  ShieldAlert,
  Wifi,
} from "lucide-react";
import { Toaster } from "sonner";
import { Topbar } from "@/components/layout/topbar";
import { PageShell, PageSection } from "@/components/layout/page-shell";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ReadinessSectionCard } from "@/components/feature/readiness-section";
import { FirstPostChecklist } from "@/components/feature/first-post-checklist";
import { IntegrationsVault } from "@/components/feature/vault/integrations-vault";
import { data } from "@/lib/data";
import type { ApiConnection } from "@/lib/types";
import { cn } from "@/lib/utils";

export default async function SettingsPage() {
  const [status, readiness, candidates, sources, jobs, connection] = await Promise.all([
    data.status(),
    data.readiness(),
    data.candidates(),
    data.sources(),
    data.jobs(),
    data.connection(),
  ]);

  const live = status.live_mode;

  return (
    <>
      <Toaster theme="dark" position="top-right" />
      <Topbar
        title="Settings"
        subtitle="Live Mode control center — readiness, integrations, safety"
        pill={{ label: live ? "Live Mode" : "Demo Mode", tone: live ? "violet" : "cyan" }}
      />
      <PageShell>
        {/* Safety banner */}
        <Card tone="violet" className="overflow-hidden p-4 sm:p-5">
          <div className="flex items-start gap-3 sm:items-center">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-accent-violet/15 ring-1 ring-accent-violet/40 shrink-0">
              <Shield className="h-4 w-4 text-accent-violet" strokeWidth={2.2} />
            </div>
            <div className="min-w-0 flex-1 text-sm text-ink-100">
              <div className="font-medium text-ink-50">
                No real post can be sent without explicit approval.
              </div>
              <div className="text-xs text-ink-300 mt-0.5 leading-relaxed">
                Test buttons never publish. Dry-run previews never contact external services.
                Three independent layers enforce the approval gate.
              </div>
            </div>
            <Badge variant="violet" className="hidden sm:inline-flex">
              defense in depth
            </Badge>
          </div>
        </Card>

        {/* Mode overview */}
        <PageSection title="Mode overview" description="Five flags control how the system behaves">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
            <ModeCard
              label="Demo Mode"
              flag={status.demo_mode}
              tone="cyan"
              icon={Beaker}
              on="Dashboard shows demo content"
              off="Live data only"
              envVar="DEMO_MODE"
            />
            <ModeCard
              label="Mock Adapters"
              flag={status.mock_mode}
              tone="cyan"
              icon={CircleDot}
              on="Adapters degrade to mock"
              off="Missing creds error out"
              envVar="MOCK_MODE"
            />
            <ModeCard
              label="Live Mode"
              flag={status.live_mode}
              tone="violet"
              icon={Wifi}
              on="UI expects real config"
              off="Demo UX active"
              envVar="LIVE_MODE"
            />
            <ModeCard
              label="Dry Run Publish"
              flag={status.dry_run_publish}
              tone="violet"
              icon={Shield}
              on="Compute payload, do not send"
              off="Real publish path active"
              envVar="DRY_RUN_PUBLISH"
            />
            <ModeCard
              label="Publishing Enabled"
              flag={status.publishing_enabled}
              tone="rose"
              icon={ShieldAlert}
              on="MASTER GATE — real publish reachable"
              off="No real publish possible"
              envVar="PUBLISHING_ENABLED"
              dangerOn
            />
          </div>
        </PageSection>

        {/* Connection honesty — 4 distinct states */}
        <ConnectionCard connection={connection} />

        {/* Integrations vault */}
        <PageSection
          title="Integrations vault"
          description="Add API keys without editing .env. Encrypted at rest. Env vars keep priority."
        >
          <IntegrationsVault />
        </PageSection>

        {/* First post checklist */}
        <FirstPostChecklist
          report={readiness}
          candidates={candidates}
          sources={sources}
          jobs={jobs}
        />

        {/* Readiness sections */}
        {readiness ? (
          <PageSection
            title="Readiness checklist"
            description={`Overall ${readiness.overall_score}% — ${readiness.overall_label}`}
          >
            <div className="grid gap-3 lg:grid-cols-2 3xl:grid-cols-2">
              {readiness.sections.map((section) => (
                <ReadinessSectionCard key={section.key} section={section} />
              ))}
            </div>
          </PageSection>
        ) : (
          <Card className="p-6 text-center text-sm text-ink-400">
            Readiness report unavailable — backend is not reachable. Start the API to populate
            this section.
          </Card>
        )}

        {/* Runbook hint */}
        <Card className="p-4 sm:p-5">
          <div className="flex items-center gap-2 text-sm font-medium text-ink-50">
            <KeyRound className="h-4 w-4 text-accent-cyan" />
            Switching to Live Mode (safe path)
          </div>
          <ol className="mt-2 space-y-1 pl-4 text-xs text-ink-300 leading-relaxed list-decimal">
            <li>
              Fill <code className="text-ink-100">.env</code> values (see{" "}
              <code className="text-ink-100">.env.example</code> and{" "}
              <code className="text-ink-100">docs/INTEGRATIONS.md</code>).
            </li>
            <li>
              Set <code className="text-ink-100">LIVE_MODE=true</code> and{" "}
              <code className="text-ink-100">MOCK_MODE=false</code>.
            </li>
            <li>
              Keep <code className="text-ink-100">DRY_RUN_PUBLISH=true</code> for the first
              full pass.
            </li>
            <li>Run readiness tests for each integration from the buttons above.</li>
            <li>Approve one candidate → review dry-run preview in editor.</li>
            <li>
              Only when everything is green: set{" "}
              <code className="text-ink-100">DRY_RUN_PUBLISH=false</code> and{" "}
              <code className="text-ink-100">PUBLISHING_ENABLED=true</code>.
            </li>
          </ol>
        </Card>
      </PageShell>
    </>
  );
}

function ConnectionCard({ connection }: { connection: ApiConnection }) {
  const meta = (() => {
    switch (connection.state) {
      case "connected":
        return {
          icon: PlugZap,
          tone: "success" as const,
          label: "API connected",
          hint: "Frontend talks to the live API. Worker is fresh.",
        };
      case "worker_stale":
        return {
          icon: AlertTriangle,
          tone: "warning" as const,
          label: "Worker stale",
          hint: `API is reachable, but the worker hasn't reported a heartbeat (overall: ${
            connection.worker_overall ?? "unknown"
          }). Approvals will not dispatch until the worker is healthy again.`,
        };
      case "missing_integrations":
        return {
          icon: Radio,
          tone: "warning" as const,
          label: "Integrations missing",
          hint:
            "Live Mode is on but critical adapters are not configured: " +
            (connection.missing?.join(", ") ?? "—") +
            ". The system will fall back to mock/blocked safely.",
        };
      default:
        return {
          icon: Plug,
          tone: "warning" as const,
          label: "Demo fallback",
          hint:
            "Frontend cannot reach the API. All screens render from lib/demo-fallback. " +
            "Set NEXT_PUBLIC_API_URL in Vercel to a reachable backend (see docs/DEPLOY_BACKEND_RUNTIME.md).",
        };
    }
  })();
  const Icon = meta.icon;
  const dotClass = meta.tone === "success" ? "bg-state-success" : "bg-accent-amber";
  const badgeVariant = meta.tone === "success" ? "mint" : "amber";

  return (
    <Card className="p-4 sm:p-5">
      <div className="flex items-start gap-3">
        <div
          className={cn(
            "grid h-9 w-9 place-items-center rounded-xl ring-1 shrink-0",
            meta.tone === "success"
              ? "bg-state-success/10 ring-state-success/30"
              : "bg-accent-amber/10 ring-accent-amber/30",
          )}
        >
          <Icon
            className={cn(
              "h-4 w-4",
              meta.tone === "success" ? "text-state-success" : "text-accent-amber",
            )}
            strokeWidth={2.2}
          />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-ink-50">{meta.label}</span>
            <Badge variant={badgeVariant}>
              <span className={cn("h-1.5 w-1.5 rounded-full", dotClass)} />
              {connection.state.replace("_", " ")}
            </Badge>
          </div>
          <p className="mt-1 text-[12px] text-ink-300 leading-relaxed">{meta.hint}</p>
          <div className="mt-1.5 text-[11px] text-ink-500">
            backend URL <span className="font-mono text-ink-300">{connection.base}</span>
            {connection.worker_overall && (
              <>
                <span className="mx-1.5 text-ink-600">·</span>
                worker{" "}
                <span className="font-mono text-ink-300">{connection.worker_overall}</span>
              </>
            )}
          </div>
        </div>
      </div>
      {connection.state === "fallback" && (
        <>
          <Separator className="my-3" />
          <p className="text-[11px] text-ink-400 leading-relaxed">
            To leave fallback: deploy the backend (see{" "}
            <code className="text-ink-100">docs/DEPLOY_BACKEND_RUNTIME.md</code>) and set{" "}
            <code className="text-ink-100">NEXT_PUBLIC_API_URL</code> in your Vercel project.
          </p>
        </>
      )}
    </Card>
  );
}

function ModeCard({
  label,
  flag,
  tone,
  icon: Icon,
  on,
  off,
  envVar,
  dangerOn,
}: {
  label: string;
  flag: boolean;
  tone: "cyan" | "violet" | "rose";
  icon: React.ComponentType<{ className?: string; strokeWidth?: number }>;
  on: string;
  off: string;
  envVar: string;
  dangerOn?: boolean;
}) {
  const active = flag;
  const ringClass =
    active && tone === "violet"
      ? "ring-accent-violet/30 bg-accent-violet/[0.07]"
      : active && tone === "rose"
      ? "ring-state-danger/30 bg-state-danger/[0.07]"
      : active
      ? "ring-accent-cyan/30 bg-accent-cyan/[0.07]"
      : "";
  return (
    <Card className={cn("p-3.5 transition-colors", active && "ring-1", ringClass)}>
      <div className="flex items-center gap-2">
        <Icon className={cn("h-3.5 w-3.5", active ? "" : "text-ink-400")} strokeWidth={2} />
        <span className="text-[11px] uppercase tracking-[0.18em] text-ink-400">{label}</span>
        <Badge
          variant={
            active
              ? dangerOn
                ? "rose"
                : tone === "violet"
                ? "violet"
                : "cyan"
              : "outline"
          }
          className="ml-auto"
        >
          {active ? "ON" : "OFF"}
        </Badge>
      </div>
      <div className="mt-2 text-[12px] text-ink-100 leading-snug min-h-[32px]">
        {active ? on : off}
      </div>
      <div className="mt-1.5 text-[10px] font-mono text-ink-500">{envVar}</div>
    </Card>
  );
}
