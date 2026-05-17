"use client";

import * as React from "react";
import { Zap, GraduationCap, Scissors, Heart, Eraser } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useRouter } from "next/navigation";
import type { Candidate } from "@/lib/types";

const MODES = [
  { mode: "sharper", label: "Sharper", icon: Zap },
  { mode: "expert", label: "More expert", icon: GraduationCap },
  { mode: "shorter", label: "Shorter", icon: Scissors },
  { mode: "human", label: "More human", icon: Heart },
  { mode: "deslop", label: "Reduce AI-slop", icon: Eraser },
] as const;

export function RewriteToolbar({
  candidateId,
  target,
}: {
  candidateId: string;
  target: "tg" | "threads" | "reddit";
}) {
  const router = useRouter();
  const [pending, setPending] = React.useState<string | null>(null);

  async function run(mode: string) {
    setPending(mode);
    try {
      const updated: Candidate = await api.rewrite(candidateId, mode, target);
      toast.success("Rewrite applied", {
        description: `Now version v${updated.version}.`,
      });
      router.refresh();
    } catch {
      toast.error("Rewrite failed", {
        description: "API недоступен — попробуй позже. (mock-режим всё равно сохраняет правку локально)",
      });
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="flex flex-wrap gap-2">
      {MODES.map((m) => {
        const Icon = m.icon;
        return (
          <Button
            key={m.mode}
            size="sm"
            variant="outline"
            disabled={pending !== null}
            onClick={() => run(m.mode)}
            className="border-white/[0.08] hover:border-accent-violet/40 hover:bg-accent-violet/10 hover:text-accent-violet"
          >
            <Icon className="h-3.5 w-3.5" />
            {pending === m.mode ? "Rewriting…" : m.label}
          </Button>
        );
      })}
    </div>
  );
}
