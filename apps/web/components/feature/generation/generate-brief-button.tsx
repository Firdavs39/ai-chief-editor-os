"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { runsApi } from "@/lib/api";
import { useOperatorToken } from "@/lib/operator-auth";

type Props = {
  clusterId?: string | null;
  label?: string;
  size?: "default" | "sm";
};

/**
 * "Запустить Quality Brief" button.
 *
 * Behaviour:
 * - If not unlocked: opens an inline operator-token prompt. The token is
 *   stored only in React memory via `useOperatorToken`.
 * - If unlocked: POSTs /generation-runs with the optional cluster_id,
 *   then routes to /editor/runs/{run_id}.
 * - On 401 (admin_token_invalid): locks the context and re-shows the
 *   prompt. The token is never written to localStorage / sessionStorage
 *   / cookies / URL.
 */
export function GenerateBriefButton({
  clusterId,
  label = "Запустить Quality Brief",
  size = "sm",
}: Props) {
  const router = useRouter();
  const { unlocked, token, unlock, lock } = useOperatorToken();
  const [open, setOpen] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const tokenInputRef = React.useRef<HTMLInputElement | null>(null);

  async function createRun(activeToken: string) {
    setBusy(true);
    try {
      const res = await runsApi.create(
        { cluster_id: clusterId ?? null, top_n: 1, requested_by: "api" },
        activeToken,
      );
      const newRun = res.runs[0];
      if (!newRun) {
        toast.error("Не удалось создать run", {
          description: "Сервер не вернул ни одного run_id.",
        });
        return;
      }
      toast.success("Run в очереди", {
        description: "Открываю timeline…",
      });
      router.push(`/editor/runs/${newRun.id}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg === "admin_token_invalid" || msg === "admin_token_required") {
        lock();
        setOpen(true);
        toast.error("Operator unlock required", {
          description: "Admin token отклонён сервером — введи новый.",
        });
        return;
      }
      toast.error("Не удалось запустить run", {
        description: msg.slice(0, 200),
      });
    } finally {
      setBusy(false);
    }
  }

  async function handleClick() {
    if (unlocked) {
      await createRun(token);
      return;
    }
    setOpen(true);
  }

  async function handleUnlockAndRun() {
    const t = tokenInputRef.current?.value?.trim() ?? "";
    if (!t) {
      toast.error("Введи admin token");
      return;
    }
    unlock(t);
    if (tokenInputRef.current) tokenInputRef.current.value = "";
    setOpen(false);
    await createRun(t);
  }

  return (
    <>
      <Button
        size={size}
        variant="default"
        onClick={handleClick}
        disabled={busy}
      >
        <Sparkles className="h-4 w-4" />
        {busy ? "Запускаю…" : label}
      </Button>

      {open && !unlocked && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-bg-base/70 p-4 backdrop-blur-sm">
          <Card className="w-full max-w-md p-5 space-y-3">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-ink-50">
                Operator unlock
              </span>
              <Badge variant="outline">memory-only</Badge>
            </div>
            <p className="text-[12px] text-ink-300 leading-relaxed">
              Quality Brief вызывает реальный LLM на бэке. Введи admin token —
              он останется только в памяти этой страницы и сотрётся при
              refresh.
            </p>
            <Input
              ref={tokenInputRef}
              type="password"
              autoComplete="off"
              spellCheck={false}
              placeholder="X-Admin-Token"
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  void handleUnlockAndRun();
                }
              }}
            />
            <div className="flex justify-end gap-2 pt-1">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setOpen(false)}
                disabled={busy}
              >
                Отмена
              </Button>
              <Button onClick={handleUnlockAndRun} disabled={busy}>
                Unlock & запустить
              </Button>
            </div>
            <p className="text-[10px] text-ink-500">
              Токен не сохраняется в localStorage, sessionStorage, cookies или
              URL.
            </p>
          </Card>
        </div>
      )}
    </>
  );
}
