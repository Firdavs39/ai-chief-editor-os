"use client";

import * as React from "react";
import { KeyRound, Lock, ShieldCheck, Unlock } from "lucide-react";
import { toast } from "sonner";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useOperatorToken } from "@/lib/operator-auth";

/**
 * Заметная плашка "Разблокировать действия".
 *
 * Зачем: владелец жаловался, что жмёт кнопки (создать пост, одобрить, править
 * канал) и "ничего не происходит". Часть действий требует админ-токен
 * (X-Admin-Token из .env, поле ADMIN_TOKEN). Без токена сервер отвечает 401,
 * и раньше это было незаметно. Эта плашка объясняет гейт простым языком и
 * визуально показывает состояние "разблокировано / заблокировано".
 *
 * Безопасность: токен живёт ТОЛЬКО в памяти React (lib/operator-auth.tsx).
 * Он НИКОГДА не пишется в localStorage / sessionStorage / cookies / URL —
 * обновление страницы стирает его. Это намеренно.
 */
export function UnlockBanner({
  description = "Введите админ-токен (из файла .env, поле ADMIN_TOKEN), чтобы выполнять действия — создавать посты, одобрять, отклонять и править каналы. Просмотр работает и без токена.",
}: {
  description?: string;
}) {
  const { unlocked, unlock, lock } = useOperatorToken();
  const inputRef = React.useRef<HTMLInputElement | null>(null);

  function tryUnlock() {
    const t = inputRef.current?.value?.trim() ?? "";
    if (!t) {
      toast.error("Введите админ-токен", {
        description: "Поле пустое. Возьмите токен из .env (ADMIN_TOKEN).",
      });
      return;
    }
    unlock(t);
    if (inputRef.current) inputRef.current.value = "";
    toast.success("Действия разблокированы", {
      description: "Теперь можно создавать посты, одобрять и править каналы.",
    });
  }

  if (unlocked) {
    return (
      <Card tone="subtle" className="flex items-center gap-2.5 p-3 sm:p-3.5">
        <div className="grid h-9 w-9 place-items-center rounded-xl bg-state-success/15 ring-1 ring-state-success/40 shrink-0">
          <ShieldCheck className="h-4 w-4 text-state-success" strokeWidth={2.2} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-ink-50">Действия разблокированы</span>
            <Badge variant="mint">
              <Unlock className="h-3 w-3" /> разблокировано
            </Badge>
          </div>
          <p className="mt-0.5 text-[11px] text-ink-500 leading-relaxed">
            Токен хранится только в памяти вкладки. Обновление страницы его
            сотрёт — это нормально, просто введите снова.
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={() => lock()} className="shrink-0">
          <Lock className="h-3.5 w-3.5" /> Заблокировать
        </Button>
      </Card>
    );
  }

  return (
    <Card tone="violet" className="p-4 sm:p-5">
      <div className="flex items-start gap-3">
        <div className="grid h-10 w-10 place-items-center rounded-xl bg-accent-violet/15 ring-1 ring-accent-violet/40 shrink-0">
          <KeyRound className="h-4 w-4 text-accent-violet" strokeWidth={2.2} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-ink-50">
              Разблокировать действия
            </span>
            <Badge variant="amber">
              <Lock className="h-3 w-3" /> заблокировано
            </Badge>
          </div>
          <p className="mt-1 text-[12px] text-ink-200 leading-relaxed">{description}</p>
          <div className="mt-3 flex flex-col gap-2 sm:flex-row">
            <Input
              ref={inputRef}
              type="password"
              autoComplete="off"
              spellCheck={false}
              placeholder="Админ-токен (ADMIN_TOKEN из .env)"
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  tryUnlock();
                }
              }}
            />
            <Button onClick={tryUnlock} className="shrink-0">
              <Unlock className="h-4 w-4" /> Разблокировать
            </Button>
          </div>
          <p className="mt-2 text-[11px] text-ink-500 leading-relaxed">
            Токен нигде не сохраняется (ни в браузере, ни в ссылке) и стирается
            при обновлении страницы. Это сделано ради безопасности.
          </p>
        </div>
      </div>
    </Card>
  );
}
