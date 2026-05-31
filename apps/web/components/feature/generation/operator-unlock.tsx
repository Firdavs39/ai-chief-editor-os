"use client";

import * as React from "react";
import { KeyRound, Lock, ShieldAlert, Unlock } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useOperatorToken } from "@/lib/operator-auth";

/**
 * Operator unlock card. Reads/writes the X-Admin-Token through the
 * memory-only `useOperatorToken` hook. NEVER persists the token.
 *
 * - `compact` variant is used inside dialogs / inline flows.
 * - The text input ref is cleared after a successful unlock so the
 *   token value does not linger in the DOM.
 */
export function OperatorUnlock({
  title = "Введите админ-токен",
  description,
  compact = false,
}: {
  title?: string;
  description?: string;
  compact?: boolean;
}) {
  const { token, unlocked, unlock, lock } = useOperatorToken();
  const inputRef = React.useRef<HTMLInputElement | null>(null);

  function tryUnlock() {
    const t = inputRef.current?.value?.trim() ?? "";
    if (!t) return;
    unlock(t);
    if (inputRef.current) {
      inputRef.current.value = "";
    }
  }

  if (unlocked) {
    return (
      <div className="flex items-center gap-2 text-[12px] text-ink-300">
        <Badge variant="mint">
          <Unlock className="h-3 w-3" /> разблокировано
        </Badge>
        <span className="text-ink-500">
          {compact ? "" : "Токен в памяти вкладки · обновление страницы его сотрёт"}
        </span>
        <Button variant="ghost" size="sm" onClick={() => lock()} className="ml-auto">
          <Lock className="h-3.5 w-3.5" /> Заблокировать
        </Button>
        {/* Never render the token itself; just confirm presence. */}
        <span className="sr-only">token length {token.length}</span>
      </div>
    );
  }

  return (
    <Card className={compact ? "p-3" : "p-4 sm:p-5"}>
      <div className="flex items-start gap-3">
        <div className="grid h-9 w-9 place-items-center rounded-xl bg-accent-violet/15 ring-1 ring-accent-violet/40 shrink-0">
          <KeyRound className="h-4 w-4 text-accent-violet" strokeWidth={2.2} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-ink-50">{title}</span>
            <Badge variant="amber">
              <Lock className="h-3 w-3" /> заблокировано
            </Badge>
          </div>
          <p className="mt-1 text-[12px] text-ink-300 leading-relaxed">
            {description ??
              "Введите админ-токен (из .env, поле ADMIN_TOKEN), чтобы создать пост. Токен хранится только в памяти вкладки — обновление страницы его сотрёт."}
          </p>
          <div className="mt-3 flex items-center gap-2">
            <div className="flex items-center gap-2 text-[11px] text-accent-amber">
              <ShieldAlert className="h-3 w-3" />
              только в памяти · не в браузере · не в ссылке
            </div>
          </div>
          <div className="mt-3 flex gap-2">
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
            <Button onClick={tryUnlock}>Разблокировать</Button>
          </div>
        </div>
      </div>
    </Card>
  );
}
