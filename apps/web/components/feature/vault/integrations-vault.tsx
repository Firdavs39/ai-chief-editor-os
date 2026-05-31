"use client";

import * as React from "react";
import { KeyRound, Lock, ShieldAlert, Unlock } from "lucide-react";
import { toast } from "sonner";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { vaultApi } from "@/lib/api";
import type { VaultListResponse, VaultProviderSummary } from "@/lib/types";
import { ProviderCard } from "./provider-card";

/**
 * Integrations Vault section for /settings.
 *
 * Security rules enforced here:
 * - Admin token lives ONLY in React state for the lifetime of this component.
 *   Reload (or navigating away) clears it. Never persisted to localStorage,
 *   sessionStorage, cookies, or the URL.
 * - Every API call (including reads) carries the X-Admin-Token header.
 * - We do not pre-fill any input value from API responses.
 */
export function IntegrationsVault() {
  const [adminToken, setAdminToken] = React.useState<string>("");
  const tokenInput = React.useRef<HTMLInputElement | null>(null);
  const [unlocked, setUnlocked] = React.useState(false);
  const [list, setList] = React.useState<VaultListResponse | null>(null);
  const [loading, setLoading] = React.useState(false);

  const refresh = React.useCallback(
    async (token: string) => {
      setLoading(true);
      try {
        const data = await vaultApi.list(token);
        setList(data);
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        if (msg === "admin_token_invalid" || msg === "admin_token_required") {
          toast.error("Хранилище заблокировано", {
            description: "Админ-токен не указан или неверный.",
          });
          setUnlocked(false);
          setAdminToken("");
        } else {
          toast.error("Хранилище недоступно", { description: msg.slice(0, 200) });
        }
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  async function tryUnlock() {
    const t = tokenInput.current?.value?.trim() ?? "";
    if (!t) {
      toast.error("Введите админ-токен", {
        description: "Возьмите его из .env (поле ADMIN_TOKEN).",
      });
      return;
    }
    await refresh(t);
    // Only mark unlocked if refresh did not reset the token.
    setAdminToken(t);
    setUnlocked(true);
    // Wipe input field so the token isn't sitting in the DOM after unlock.
    if (tokenInput.current) tokenInput.current.value = "";
  }

  function lockNow() {
    setAdminToken("");
    setUnlocked(false);
    setList(null);
  }

  function updateProvider(p: VaultProviderSummary) {
    setList((prev) =>
      prev
        ? {
            ...prev,
            providers: prev.providers.map((x) =>
              x.provider === p.provider ? p : x,
            ),
          }
        : prev,
    );
  }

  return (
    <Card className="p-4 sm:p-5 space-y-4">
      <div className="flex items-start gap-3">
        <div className="grid h-10 w-10 place-items-center rounded-xl bg-accent-violet/15 ring-1 ring-accent-violet/40 shrink-0">
          <KeyRound className="h-4 w-4 text-accent-violet" strokeWidth={2.2} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-ink-50">Хранилище ключей</span>
            <Badge variant={unlocked ? "mint" : "outline"}>
              {unlocked ? <Unlock className="h-3 w-3" /> : <Lock className="h-3 w-3" />}
              {unlocked ? "разблокировано" : "заблокировано"}
            </Badge>
            {list && (
              <Badge variant={list.vault_enabled ? "mint" : "amber"}>
                {list.vault_enabled ? "шифруется" : "выключено"}
              </Badge>
            )}
          </div>
          <p className="mt-1 text-[12px] text-ink-300 leading-relaxed">
            Добавляйте ключи API без правки файла <code className="text-ink-100">.env</code>.
            Значения хранятся в зашифрованном виде. Значения из .env имеют приоритет.
            Админ-токен живёт только в этой вкладке — обновление страницы его сотрёт.
          </p>
        </div>
        {unlocked && (
          <Button variant="ghost" size="sm" onClick={lockNow} className="shrink-0">
            <Lock className="h-3.5 w-3.5" /> Заблокировать
          </Button>
        )}
      </div>

      {!unlocked && (
        <div className="rounded-xl border border-white/[0.06] bg-white/[0.015] p-3 sm:p-4">
          <div className="flex items-center gap-2 mb-2 text-[12px] text-ink-200">
            <ShieldAlert className="h-3.5 w-3.5 text-accent-amber" />
            Введите админ-токен, чтобы посмотреть или изменить ключи.
          </div>
          <div className="flex gap-2">
            <Input
              ref={tokenInput}
              type="password"
              autoComplete="off"
              spellCheck={false}
              placeholder="Админ-токен (только в памяти, обновление стирает)"
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  void tryUnlock();
                }
              }}
            />
            <Button onClick={tryUnlock} disabled={loading}>
              {loading ? "…" : "Разблокировать"}
            </Button>
          </div>
          <p className="mt-2 text-[11px] text-ink-500">
            Токен не сохраняется в браузере и не попадает в ссылку. Задайте
            <code className="ml-1 text-ink-200">ADMIN_TOKEN</code> на сервере API.
          </p>
        </div>
      )}

      {unlocked && list && !list.vault_enabled && (
        <div className="rounded-xl border border-accent-amber/30 bg-accent-amber/10 p-3 text-[12px] text-accent-amber">
          Хранилище выключено — сохранение и проверки заблокированы. Задайте
          <code className="mx-1 font-mono">MASTER_ENCRYPTION_KEY</code> на бэкенде.
          Сгенерировать ключ:{" "}
          <code className="font-mono">python -m chief_editor.services.secrets generate-key</code>.
        </div>
      )}

      {unlocked && list && (
        <div className="grid gap-3 lg:grid-cols-2">
          {list.providers.map((p) => (
            <ProviderCard
              key={p.provider}
              provider={p}
              adminToken={adminToken}
              vaultEnabled={list.vault_enabled}
              onUpdated={updateProvider}
            />
          ))}
        </div>
      )}
    </Card>
  );
}
