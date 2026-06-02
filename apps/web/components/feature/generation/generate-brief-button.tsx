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
 * Кнопка "Создать пост".
 *
 * Поведение:
 * - Если не разблокировано: открывает окно ввода админ-токена. Токен
 *   хранится ТОЛЬКО в памяти React через `useOperatorToken`.
 * - Если разблокировано: POST /generation-runs с опциональным cluster_id,
 *   затем переход на /editor/runs/{run_id}.
 * - При 401 (токен отклонён): сбрасывает токен и снова показывает окно.
 *   Токен НИКОГДА не пишется в localStorage / sessionStorage / cookies / URL.
 *
 * Важно для UX: генерация поста реально занимает ~15–40 минут (живая модель
 * на бэке). После запуска показываем понятный тост, чтобы владелец не думал,
 * что "просто перешло и ничего не происходит".
 */
export function GenerateBriefButton({
  clusterId,
  label = "Создать пост",
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
        toast.error("Ошибка: пост не создан", {
          description: "Сервер не вернул задачу. Попробуйте ещё раз.",
        });
        return;
      }
      toast.success("Пост генерируется", {
        description:
          "Это занимает ~15–40 минут. Вкладку можно закрыть — прогресс не потеряется. Готовый пост появится в разделе Редактор.",
        duration: 12000,
      });
      router.push(`/editor/runs/${newRun.id}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg === "admin_token_invalid" || msg === "admin_token_required") {
        lock();
        setOpen(true);
        toast.error("Сначала введите админ-токен", {
          description: "Токен отклонён сервером — введите правильный (ADMIN_TOKEN из .env).",
        });
        return;
      }
      toast.error("Ошибка: не удалось создать пост", {
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
      toast.error("Введите админ-токен", {
        description: "Возьмите его из .env (поле ADMIN_TOKEN).",
      });
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
        {busy ? "Создаю…" : label}
      </Button>

      {open && !unlocked && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-bg-base/70 p-4 backdrop-blur-sm">
          <Card className="w-full max-w-md p-5 space-y-3">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-ink-50">
                Сначала введите админ-токен
              </span>
              <Badge variant="outline">только в памяти</Badge>
            </div>
            <p className="text-[12px] text-ink-300 leading-relaxed">
              Создание поста запускает живую модель на сервере. Введите
              админ-токен (из файла .env, поле ADMIN_TOKEN). Он останется только
              в памяти этой вкладки и сотрётся при обновлении страницы.
            </p>
            <p className="text-[12px] text-accent-cyan leading-relaxed">
              Генерация занимает ~15–40 минут. Вкладку можно закрыть — прогресс
              не потеряется.
            </p>
            <Input
              ref={tokenInputRef}
              type="password"
              autoComplete="off"
              spellCheck={false}
              placeholder="Админ-токен (ADMIN_TOKEN из .env)"
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
                Разблокировать и создать
              </Button>
            </div>
            <p className="text-[10px] text-ink-500">
              Токен не сохраняется в браузере (ни в localStorage, ни в cookies,
              ни в ссылке).
            </p>
          </Card>
        </div>
      )}
    </>
  );
}
