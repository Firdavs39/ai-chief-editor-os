"use client";

import * as React from "react";
import { Zap, GraduationCap, Scissors, Heart, Eraser } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useRouter } from "next/navigation";
import type { Candidate } from "@/lib/types";

const MODES = [
  { mode: "sharper", label: "Острее", icon: Zap },
  { mode: "expert", label: "Экспертнее", icon: GraduationCap },
  { mode: "shorter", label: "Короче", icon: Scissors },
  { mode: "human", label: "Живее", icon: Heart },
  { mode: "deslop", label: "Убрать ИИ-штампы", icon: Eraser },
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
      toast.success("Готово: текст переписан", {
        description: `Теперь версия ${updated.version}.`,
      });
      router.refresh();
    } catch {
      toast.error("Ошибка: не удалось переписать", {
        description: "Сервер недоступен. Попробуйте ещё раз чуть позже.",
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
            {pending === m.mode ? "Переписываю…" : m.label}
          </Button>
        );
      })}
    </div>
  );
}
