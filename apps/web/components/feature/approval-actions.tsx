"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, XCircle } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { Candidate } from "@/lib/types";

export function ApprovalActions({ candidate }: { candidate: Candidate }) {
  const router = useRouter();
  const [busy, setBusy] = React.useState(false);

  async function approve() {
    setBusy(true);
    try {
      await api.approve(candidate.id, { reason: "approved from board", platform: "telegram" });
      toast.success("Approved & scheduled", {
        description: "Кандидат поставлен в очередь публикации.",
      });
      router.refresh();
    } catch {
      toast.error("Approval failed", { description: "API недоступен. Проверь, что бэкенд запущен." });
    } finally {
      setBusy(false);
    }
  }

  async function reject() {
    setBusy(true);
    try {
      await api.reject(candidate.id, { reason: "rejected from board" });
      toast.success("Rejected");
      router.refresh();
    } catch {
      toast.error("Reject failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex gap-2">
      <Button
        size="sm"
        variant="outline"
        disabled={busy}
        onClick={approve}
        className="flex-1 text-accent-mint hover:bg-accent-mint/10"
      >
        <CheckCircle2 className="h-3.5 w-3.5" /> Approve
      </Button>
      <Button
        size="sm"
        variant="outline"
        disabled={busy}
        onClick={reject}
        className="flex-1 text-accent-rose hover:bg-accent-rose/10"
      >
        <XCircle className="h-3.5 w-3.5" /> Reject
      </Button>
    </div>
  );
}
