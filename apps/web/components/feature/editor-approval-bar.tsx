"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, Shield, XCircle } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { Candidate } from "@/lib/types";

export function EditorApprovalBar({ candidate }: { candidate: Candidate }) {
  const router = useRouter();
  const [busy, setBusy] = React.useState<"approve" | "reject" | null>(null);

  const isDecided = candidate.status === "approved" || candidate.status === "published";

  async function approve() {
    setBusy("approve");
    try {
      await api.approve(candidate.id, {
        reason: "approved from editor",
        platform: "telegram",
      });
      toast.success("Approved & scheduled", {
        description: "Кандидат поставлен в очередь публикации.",
      });
      router.refresh();
    } catch {
      toast.error("Approval failed", {
        description: "API недоступен. Если открыто в demo-режиме — это ожидаемо.",
      });
    } finally {
      setBusy(null);
    }
  }

  async function reject() {
    setBusy("reject");
    try {
      await api.reject(candidate.id, { reason: "rejected from editor" });
      toast.success("Rejected");
      router.refresh();
    } catch {
      toast.error("Reject failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="sticky bottom-3 z-20 mt-4 sm:mt-6">
      <div className="glass-strong flex flex-col gap-2 rounded-2xl p-3 sm:p-3.5 sm:flex-row sm:items-center sm:gap-3">
        <div className="flex items-center gap-2 sm:flex-1 min-w-0">
          <div className="grid h-8 w-8 place-items-center rounded-lg bg-accent-violet/15 ring-1 ring-accent-violet/30 shrink-0">
            <Shield className="h-3.5 w-3.5 text-accent-violet" strokeWidth={2.2} />
          </div>
          <div className="min-w-0">
            <div className="text-[12px] font-medium text-ink-50 leading-tight">
              Approval-gated publish
            </div>
            <div className="text-[11px] text-ink-400 leading-tight truncate">
              Decision is logged and required before the publisher dispatches.
            </div>
          </div>
        </div>
        <div className="flex gap-2 sm:shrink-0">
          <Button
            variant="outline"
            size="sm"
            disabled={busy !== null || candidate.status === "rejected"}
            onClick={reject}
            className="flex-1 text-state-danger hover:bg-state-danger/10 hover:border-state-danger/30 sm:flex-none"
          >
            <XCircle className="h-3.5 w-3.5" />
            Reject
          </Button>
          <Button
            size="sm"
            disabled={busy !== null || isDecided}
            onClick={approve}
            className="flex-1 sm:flex-none"
          >
            <CheckCircle2 className="h-3.5 w-3.5" />
            {isDecided ? "Already approved" : "Approve & schedule"}
          </Button>
        </div>
      </div>
    </div>
  );
}
