"use client";

import * as React from "react";
import {
  KeyRound,
  Loader2,
  Lock,
  Megaphone,
  Plus,
  ShieldAlert,
  Unlock,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetTitle,
} from "@/components/ui/sheet";
import { channelsApi, type ChannelApiError } from "@/lib/api";
import { useOperatorToken } from "@/lib/operator-auth";
import type { Channel, ChannelCreate, Source, StyleProfile } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ChannelCard } from "./channel-card";
import {
  LANG_OPTIONS,
  STYLE_NONE_VALUE,
  selectClassName,
  styleOptionsFrom,
} from "./shared";

/**
 * Channels manager — the interactive surface of /channels.
 *
 * Security:
 * - The X-Admin-Token lives ONLY in React memory via `useOperatorToken`
 *   (shared with the rest of the (app)/ tree). It is NEVER written to
 *   localStorage / sessionStorage / cookies / URL. A reload clears it.
 * - Reads (`channelsApi.list`) are open; only mutations carry the token.
 * - `target_chat_id` is a public identifier — no bot token is ever entered
 *   or displayed here.
 */
export function ChannelsManager({
  initialChannels,
  sources,
  styleProfile,
}: {
  initialChannels: Channel[];
  sources: Source[];
  styleProfile: StyleProfile | null;
}) {
  const { unlocked, getAdminHeaders, lock } = useOperatorToken();
  const [channels, setChannels] = React.useState<Channel[]>(initialChannels);
  const [refreshing, setRefreshing] = React.useState(false);
  const [createOpen, setCreateOpen] = React.useState(false);

  const styleOptions = React.useMemo(
    () => styleOptionsFrom(styleProfile),
    [styleProfile],
  );

  const adminToken = () => getAdminHeaders()["X-Admin-Token"] ?? "";

  const refresh = React.useCallback(async () => {
    setRefreshing(true);
    try {
      const next = await channelsApi.list();
      setChannels(next);
    } catch {
      // Keep the last good list; the page-level fallback already handles the
      // fully-offline case. Surface a soft hint only.
      toast.error("Не удалось обновить список каналов", {
        description: "Сервер недоступен — показываем последний загруженный список.",
      });
    } finally {
      setRefreshing(false);
    }
  }, []);

  // Optimistic single-channel replace after a card mutation, then refresh to
  // pick up server-derived fields (slug, source_ids, updated_at).
  const applyChannel = React.useCallback((updated: Channel) => {
    setChannels((prev) =>
      prev.map((c) => (c.id === updated.id ? updated : c)),
    );
  }, []);

  const enabledCount = channels.filter((c) => c.enabled).length;
  const sourceLinks = channels.reduce((n, c) => n + c.source_ids.length, 0);

  return (
    <>
      {/* Operator unlock — required for every mutation on this page. */}
      <UnlockBar unlocked={unlocked} onLock={lock} />

      {/* Summary stats. */}
      <div className="grid grid-cols-2 gap-2.5 sm:gap-3 md:grid-cols-4 3xl:gap-4">
        <StatCard label="Каналов" value={channels.length} />
        <StatCard label="Включено" value={enabledCount} tone="mint" />
        <StatCard label="Связей с источниками" value={sourceLinks} />
        <StatCard label="Источников всего" value={sources.length} />
      </div>

      {/* Toolbar. */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-ink-400">
          <Megaphone className="h-3.5 w-3.5 text-accent-violet" />
          Каналы публикации
          {refreshing && (
            <Loader2 className="h-3 w-3 animate-spin text-ink-500" />
          )}
        </div>
        <Button
          size="sm"
          onClick={() => setCreateOpen(true)}
          disabled={!unlocked}
          title={unlocked ? "Добавить канал" : "Сначала введите админ-токен"}
        >
          <Plus className="h-4 w-4" /> Добавить канал
        </Button>
      </div>

      {/* Grid / empty state. */}
      {channels.length === 0 ? (
        <EmptyChannels unlocked={unlocked} onCreate={() => setCreateOpen(true)} />
      ) : (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 3xl:grid-cols-3 3xl:gap-4">
          {channels.map((c) => (
            <ChannelCard
              key={c.id}
              channel={c}
              sources={sources}
              styleProfile={styleProfile}
              onChanged={applyChannel}
              onNeedsRefresh={refresh}
              getAdminToken={adminToken}
            />
          ))}
        </div>
      )}

      <CreateChannelSheet
        open={createOpen}
        onOpenChange={setCreateOpen}
        styleOptions={styleOptions}
        getAdminToken={adminToken}
        onCreated={refresh}
      />
    </>
  );
}

// ---------------------------------------------------------------------------
// Unlock bar
// ---------------------------------------------------------------------------

function UnlockBar({
  unlocked,
  onLock,
}: {
  unlocked: boolean;
  onLock: () => void;
}) {
  const { unlock } = useOperatorToken();
  const inputRef = React.useRef<HTMLInputElement | null>(null);

  function tryUnlock() {
    const t = inputRef.current?.value?.trim() ?? "";
    if (!t) {
      toast.error("Введите админ-токен", {
        description: "Возьмите его из .env (поле ADMIN_TOKEN).",
      });
      return;
    }
    unlock(t);
    if (inputRef.current) inputRef.current.value = "";
    toast.success("Действия разблокированы", {
      description: "Теперь можно создавать и править каналы.",
    });
  }

  if (unlocked) {
    return (
      <Card tone="subtle" className="flex items-center gap-2.5 p-3 sm:p-3.5">
        <div className="grid h-8 w-8 place-items-center rounded-lg bg-state-success/15 ring-1 ring-state-success/40 shrink-0">
          <Unlock className="h-3.5 w-3.5 text-state-success" strokeWidth={2.2} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-ink-50">Действия разблокированы</span>
            <Badge variant="mint">
              <Unlock className="h-3 w-3" /> разблокировано
            </Badge>
          </div>
          <p className="mt-0.5 text-[11px] text-ink-500">
            Токен в памяти вкладки · обновление страницы его сотрёт · правки доступны
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={onLock} className="shrink-0">
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
            <span className="text-sm font-medium text-ink-50">Разблокировать действия</span>
            <Badge variant="amber">
              <Lock className="h-3 w-3" /> заблокировано
            </Badge>
          </div>
          <p className="mt-1 text-[12px] text-ink-300 leading-relaxed">
            Просмотр каналов открыт всем. Создание и правка канала меняют, куда
            уходят одобренные посты, поэтому требуют админ-токен (из .env, поле
            ADMIN_TOKEN). Токен хранится только в памяти вкладки — обновление
            страницы его сотрёт.
          </p>
          <div className="mt-2 flex items-center gap-2 text-[11px] text-accent-amber">
            <ShieldAlert className="h-3 w-3" />
            только в памяти · не в браузере · не в ссылке
          </div>
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
        </div>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Stats + empty state
// ---------------------------------------------------------------------------

function StatCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: "mint";
}) {
  return (
    <Card className="p-3 sm:p-4 3xl:p-5">
      <div className="text-[10px] sm:text-[11px] uppercase tracking-[0.18em] text-ink-400">
        {label}
      </div>
      <div
        className={cn(
          "num mt-1 text-xl sm:text-2xl 3xl:text-[28px] font-semibold",
          tone === "mint" ? "text-accent-mint" : "text-ink-50",
        )}
      >
        {value}
      </div>
    </Card>
  );
}

function EmptyChannels({
  unlocked,
  onCreate,
}: {
  unlocked: boolean;
  onCreate: () => void;
}) {
  return (
    <Card className="flex flex-col items-center gap-3 p-8 text-center sm:p-12">
      <div className="grid h-12 w-12 place-items-center rounded-2xl bg-accent-violet/15 ring-1 ring-accent-violet/40">
        <Megaphone className="h-5 w-5 text-accent-violet" strokeWidth={2} />
      </div>
      <div className="space-y-1">
        <div className="text-sm font-medium text-ink-50">Каналов пока нет</div>
        <p className="mx-auto max-w-sm text-[12px] leading-relaxed text-ink-400">
          Канал — это одно место для публикации (например, Telegram-канал) со
          своим стилем и своим набором источников. Если список пуст — возможно,
          сервер ещё запускается.
        </p>
      </div>
      <Button onClick={onCreate} disabled={!unlocked} size="sm">
        <Plus className="h-4 w-4" /> Добавить первый канал
      </Button>
      {!unlocked && (
        <p className="text-[11px] text-ink-500">Сначала введите админ-токен, чтобы создать канал.</p>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Create channel sheet
// ---------------------------------------------------------------------------

function CreateChannelSheet({
  open,
  onOpenChange,
  styleOptions,
  getAdminToken,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (next: boolean) => void;
  styleOptions: { value: string; label: string }[];
  getAdminToken: () => string;
  onCreated: () => void | Promise<void>;
}) {
  const [name, setName] = React.useState("");
  const [targetChatId, setTargetChatId] = React.useState("");
  const [lang, setLang] = React.useState("ru");
  const [styleId, setStyleId] = React.useState(STYLE_NONE_VALUE);
  const [saving, setSaving] = React.useState(false);

  // Reset the form whenever the sheet (re)opens.
  React.useEffect(() => {
    if (open) {
      setName("");
      setTargetChatId("");
      setLang("ru");
      setStyleId(STYLE_NONE_VALUE);
    }
  }, [open]);

  async function submit() {
    const trimmed = name.trim();
    if (!trimmed) {
      toast.error("Укажите название канала");
      return;
    }
    const body: ChannelCreate = {
      name: trimmed,
      target_chat_id: targetChatId.trim(),
      lang,
      style_profile_id: styleId === STYLE_NONE_VALUE ? null : styleId,
    };
    setSaving(true);
    try {
      const created = await channelsApi.create(body, getAdminToken());
      toast.success("Готово: канал создан", { description: created.name });
      onOpenChange(false);
      await onCreated();
    } catch (err) {
      handleChannelError(err);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full p-0 sm:w-[420px]">
        <div className="flex h-full flex-col">
          <div className="border-b border-white/[0.06] px-5 py-4">
            <SheetTitle>Новый канал</SheetTitle>
            <SheetDescription>
              Одно место для публикации со своим стилем и источниками.
            </SheetDescription>
          </div>

          <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
            <Field label="Название" hint="Видно в дашборде. Короткий адрес создаётся автоматически.">
              <Input
                value={name}
                autoFocus
                onChange={(e) => setName(e.target.value)}
                placeholder="BUAI · основной канал"
              />
            </Field>

            <Field
              label="ID канала в Telegram"
              hint="Публичный @username или числовой ID канала. Не токен бота."
            >
              <Input
                value={targetChatId}
                onChange={(e) => setTargetChatId(e.target.value)}
                placeholder="@buai_uz или -1001234567890"
                className="font-mono"
              />
            </Field>

            <div className="grid grid-cols-2 gap-3">
              <Field label="Язык">
                <select
                  value={lang}
                  onChange={(e) => setLang(e.target.value)}
                  className={selectClassName}
                >
                  {LANG_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value} className="bg-bg-base">
                      {o.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Стиль">
                <select
                  value={styleId}
                  onChange={(e) => setStyleId(e.target.value)}
                  className={selectClassName}
                >
                  {styleOptions.map((o) => (
                    <option key={o.value} value={o.value} className="bg-bg-base">
                      {o.label}
                    </option>
                  ))}
                </select>
              </Field>
            </div>

            <div className="rounded-xl border border-accent-cyan/20 bg-accent-cyan/[0.06] p-3 text-[11px] leading-relaxed text-ink-300">
              Токен бота здесь не указывается. Он хранится в защищённом хранилище
              ключей и подставляется при публикации. Публикация всё равно требует
              ручного одобрения.
            </div>
          </div>

          <div className="flex items-center justify-end gap-2 border-t border-white/[0.06] px-5 py-4">
            <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={saving}>
              <X className="h-4 w-4" /> Отмена
            </Button>
            <Button onClick={submit} disabled={saving}>
              {saving ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" /> Создаю…
                </>
              ) : (
                <>
                  <Plus className="h-4 w-4" /> Создать канал
                </>
              )}
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block space-y-1.5">
      <span className="text-[12px] font-medium text-ink-100">{label}</span>
      {children}
      {hint && <span className="block text-[11px] text-ink-500">{hint}</span>}
    </label>
  );
}

// ---------------------------------------------------------------------------
// Shared error → toast mapping (401 / 409 / network).
// ---------------------------------------------------------------------------

export function handleChannelError(err: unknown) {
  const e = err as ChannelApiError;
  if (e?.code === "admin_token_required") {
    toast.error("Сначала введите админ-токен", {
      description: "Разблокируйте действия токеном (ADMIN_TOKEN из .env), прежде чем менять каналы.",
    });
    return;
  }
  if (e?.code === "admin_token_invalid") {
    toast.error("Токен не подошёл", {
      description: "Сервер отклонил токен. Введите правильный админ-токен (ADMIN_TOKEN из .env).",
    });
    return;
  }
  if (e?.code === "conflict") {
    const map: Record<string, string> = {
      default_channel_cannot_be_disabled:
        "Основной канал нельзя выключить — это запасной канал по умолчанию.",
      channel_slug_taken:
        "Канал с таким адресом уже есть. Выберите другое название.",
    };
    toast.error("Конфликт", {
      description: map[e.detail ?? ""] ?? e.detail ?? "Действие конфликтует с текущим состоянием.",
    });
    return;
  }
  if (e?.code === "not_found") {
    toast.error("Не найдено", { description: "Канал или источник больше не существует." });
    return;
  }
  toast.error("Ошибка запроса", {
    description: (e instanceof Error ? e.message : String(err)).slice(0, 200),
  });
}
