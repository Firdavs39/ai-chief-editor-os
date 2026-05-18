"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { Toaster } from "sonner";
import { PageShell, PageSection } from "@/components/layout/page-shell";
import { Topbar } from "@/components/layout/topbar";
import { Button } from "@/components/ui/button";
import { OperatorUnlock } from "@/components/feature/generation/operator-unlock";
import { RunTimeline } from "@/components/feature/generation/run-timeline";
import { useOperatorToken } from "@/lib/operator-auth";

/**
 * Run viewer page for the Quality Editorial Workflow.
 *
 * - Client component. Uses the memory-only operator token via the context
 *   provider mounted in (app)/layout.tsx.
 * - Polling, status rendering, artifact display, and cancel button all
 *   live inside `<RunTimeline>`. The page itself only handles unlock
 *   gating and layout.
 */
export default function RunPage() {
  const params = useParams<{ id: string }>();
  const id = String(params?.id ?? "");
  const { unlocked } = useOperatorToken();

  return (
    <>
      <Toaster theme="dark" position="top-right" />
      <Topbar
        title="Quality Brief"
        subtitle={`Run id: ${id || "—"}`}
        pill={{
          label: unlocked ? "unlocked" : "locked",
          tone: unlocked ? "violet" : "cyan",
        }}
        actions={
          <Button asChild variant="ghost" size="sm">
            <Link href="/editor">
              <ArrowLeft className="h-4 w-4" /> К списку драфтов
            </Link>
          </Button>
        }
      />
      <PageShell>
        {!unlocked ? (
          <PageSection
            title="Operator unlock"
            description="Token живёт только в памяти этой вкладки — refresh сотрёт его."
          >
            <OperatorUnlock
              title="Operator unlock — Quality Brief viewer"
              description="Чтобы посмотреть прогресс этого run, введи admin token. Он не пишется в localStorage, sessionStorage, cookies или URL."
            />
          </PageSection>
        ) : id ? (
          <PageSection title="Прогресс">
            <RunTimeline runId={id} />
          </PageSection>
        ) : (
          <PageSection title="Run id отсутствует">
            <div className="text-[12px] text-ink-400">
              URL не содержит run id — проверь ссылку.
            </div>
          </PageSection>
        )}
      </PageShell>
    </>
  );
}
