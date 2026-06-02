"use client";

import * as React from "react";
import {
  Check,
  Hash,
  Languages,
  Link2,
  Link2Off,
  Loader2,
  Megaphone,
  Palette,
  Pencil,
  Plus,
  Send,
  Settings2,
  Star,
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
import { channelsApi } from "@/lib/api";
import type { Channel, ChannelUpdate, Source, StyleProfile } from "@/lib/types";
import { cn } from "@/lib/utils";
import { handleChannelError } from "./channels-manager";
import {
  LANG_OPTIONS,
  STYLE_NONE_VALUE,
  selectClassName,
  styleLabelFor,
  styleOptionsFrom,
} from "./shared";

const PLATFORM_ICON: Record<string, React.ComponentType<{ className?: string; strokeWidth?: number }>> = {
  telegram: Send,
  threads: Megaphone,
  reddit: Megaphone,
};

export function ChannelCard({
  channel,
  sources,
  styleProfile,
  onChanged,
  onNeedsRefresh,
  getAdminToken,
}: {
  channel: Channel;
  sources: Source[];
  styleProfile: StyleProfile | null;
  onChanged: (updated: Channel) => void;
  onNeedsRefresh: () => void | Promise<void>;
  getAdminToken: () => string;
}) {
  const [editing, setEditing] = React.useState(false);
  const [togglingEnabled, setTogglingEnabled] = React.useState(false);
  const [sourcesOpen, setSourcesOpen] = React.useState(false);

  const PlatformIcon = PLATFORM_ICON[channel.platform] ?? Megaphone;
  const linkedSources = sources.filter((s) => channel.source_ids.includes(s.id));

  async function toggleEnabled() {
    // Client-side guard mirrors the backend 409 — the default channel is the
    // fallback destination and cannot be disabled.
    if (channel.is_default && channel.enabled) {
      toast.error("Основной канал нельзя выключить", {
        description: "Это запасной канал для постов без назначенного канала.",
      });
      return;
    }
    setTogglingEnabled(true);
    try {
      const updated = await channelsApi.update(
        channel.id,
        { enabled: !channel.enabled },
        getAdminToken(),
      );
      onChanged(updated);
      toast.success(updated.enabled ? "Готово: канал включён" : "Готово: канал выключен", {
        description: updated.name,
      });
    } catch (err) {
      handleChannelError(err);
    } finally {
      setTogglingEnabled(false);
    }
  }

  return (
    <Card className="flex flex-col gap-3 p-4 sm:p-5">
      {/* Header */}
      <div className="flex items-start gap-3">
        <div
          className={cn(
            "grid h-9 w-9 sm:h-10 sm:w-10 place-items-center rounded-xl bg-gradient-to-br ring-1 ring-white/[0.06] shrink-0",
            channel.enabled
              ? "from-accent-violet/25 to-accent-violet/5"
              : "from-white/[0.06] to-white/[0.01]",
          )}
        >
          <PlatformIcon className="h-4 w-4 text-ink-100" strokeWidth={1.9} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="truncate text-sm sm:text-[15px] font-medium text-ink-50">
              {channel.name || channel.slug}
            </span>
            {channel.is_default && (
              <Badge variant="violet">
                <Star className="h-3 w-3" /> основной
              </Badge>
            )}
            <Badge variant={channel.enabled ? "mint" : "outline"}>
              <span
                className={cn(
                  "h-1.5 w-1.5 rounded-full",
                  channel.enabled ? "bg-accent-mint" : "bg-ink-500",
                )}
              />
              {channel.enabled ? "включён" : "выключен"}
            </Badge>
          </div>
          <div className="mt-0.5 flex items-center gap-1.5 text-[11px] text-ink-500 font-mono">
            <Hash className="h-3 w-3" />
            {channel.slug}
            <span className="text-ink-600">·</span>
            <span className="uppercase tracking-wide">{channel.platform}</span>
          </div>
        </div>
      </div>

      {editing ? (
        <ChannelEditor
          channel={channel}
          styleProfile={styleProfile}
          getAdminToken={getAdminToken}
          onChanged={onChanged}
          onClose={() => setEditing(false)}
        />
      ) : (
        <>
          {/* Meta grid */}
          <div className="grid grid-cols-2 gap-2 text-[12px]">
            <Meta icon={Send} label="Куда">
              <span className="font-mono text-ink-200">
                {channel.target_chat_id || <span className="text-ink-500">— не указано —</span>}
              </span>
            </Meta>
            <Meta icon={Languages} label="Язык">
              <span className="uppercase text-ink-200">{channel.lang}</span>
            </Meta>
            <Meta icon={Palette} label="Стиль">
              <span className="text-ink-200">
                {styleLabelFor(channel.style_profile_id, styleProfile)}
              </span>
            </Meta>
            <Meta icon={Link2} label="Источники">
              <span className="num text-ink-200">{channel.source_ids.length}</span>
            </Meta>
          </div>

          {/* Actions */}
          <div className="mt-auto flex items-center gap-2 pt-1">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setEditing(true)}
              className="flex-1"
            >
              <Pencil className="h-3.5 w-3.5" /> Изменить
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setSourcesOpen(true)}
              className="flex-1"
            >
              <Settings2 className="h-3.5 w-3.5" /> Источники
            </Button>
            <button
              type="button"
              onClick={toggleEnabled}
              disabled={togglingEnabled}
              aria-pressed={channel.enabled}
              aria-label={channel.enabled ? "Выключить канал" : "Включить канал"}
              title={
                channel.is_default && channel.enabled
                  ? "Основной канал нельзя выключить"
                  : channel.enabled
                  ? "Выключить канал"
                  : "Включить канал"
              }
              className={cn(
                "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors disabled:opacity-50",
                channel.enabled ? "bg-accent-mint/70" : "bg-white/[0.10]",
                channel.is_default && channel.enabled && "cursor-not-allowed",
              )}
            >
              <span
                className={cn(
                  "inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform",
                  channel.enabled ? "translate-x-6" : "translate-x-1",
                )}
              >
                {togglingEnabled && (
                  <Loader2 className="h-4 w-4 animate-spin text-bg-base" />
                )}
              </span>
            </button>
          </div>
        </>
      )}

      <ChannelSourcesSheet
        open={sourcesOpen}
        onOpenChange={setSourcesOpen}
        channel={channel}
        sources={sources}
        linkedSources={linkedSources}
        getAdminToken={getAdminToken}
        onChanged={onChanged}
        onNeedsRefresh={onNeedsRefresh}
      />
    </Card>
  );
}

function Meta({
  icon: Icon,
  label,
  children,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-white/[0.05] bg-white/[0.015] px-2.5 py-1.5">
      <div className="flex items-center gap-1 text-[10px] uppercase tracking-[0.14em] text-ink-500">
        <Icon className="h-3 w-3" />
        {label}
      </div>
      <div className="mt-0.5 truncate">{children}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Inline editor (target_chat_id / lang / style)
// ---------------------------------------------------------------------------

function ChannelEditor({
  channel,
  styleProfile,
  getAdminToken,
  onChanged,
  onClose,
}: {
  channel: Channel;
  styleProfile: StyleProfile | null;
  getAdminToken: () => string;
  onChanged: (updated: Channel) => void;
  onClose: () => void;
}) {
  const [targetChatId, setTargetChatId] = React.useState(channel.target_chat_id);
  const [lang, setLang] = React.useState(channel.lang);
  const [styleId, setStyleId] = React.useState(
    channel.style_profile_id ?? STYLE_NONE_VALUE,
  );
  const [saving, setSaving] = React.useState(false);

  const styleOptions = styleOptionsFrom(styleProfile, channel.style_profile_id);

  async function save() {
    const body: ChannelUpdate = {
      target_chat_id: targetChatId.trim(),
      lang,
      style_profile_id: styleId === STYLE_NONE_VALUE ? null : styleId,
    };
    setSaving(true);
    try {
      const updated = await channelsApi.update(channel.id, body, getAdminToken());
      onChanged(updated);
      toast.success("Готово: канал обновлён", { description: updated.name });
      onClose();
    } catch (err) {
      handleChannelError(err);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-3">
      <label className="block space-y-1">
        <span className="text-[11px] uppercase tracking-[0.14em] text-ink-500">
          ID канала в Telegram
        </span>
        <Input
          value={targetChatId}
          onChange={(e) => setTargetChatId(e.target.value)}
          placeholder="@buai_uz или -1001234567890"
          className="font-mono"
        />
      </label>
      <div className="grid grid-cols-2 gap-2">
        <label className="block space-y-1">
          <span className="text-[11px] uppercase tracking-[0.14em] text-ink-500">
            Язык
          </span>
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
        </label>
        <label className="block space-y-1">
          <span className="text-[11px] uppercase tracking-[0.14em] text-ink-500">
            Стиль
          </span>
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
        </label>
      </div>
      <div className="flex items-center justify-end gap-2 pt-0.5">
        <Button variant="ghost" size="sm" onClick={onClose} disabled={saving}>
          <X className="h-3.5 w-3.5" /> Отмена
        </Button>
        <Button size="sm" onClick={save} disabled={saving}>
          {saving ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> Сохраняю…
            </>
          ) : (
            <>
              <Check className="h-3.5 w-3.5" /> Сохранить
            </>
          )}
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sources drawer — attach / detach from the shared source pool
// ---------------------------------------------------------------------------

function ChannelSourcesSheet({
  open,
  onOpenChange,
  channel,
  sources,
  linkedSources,
  getAdminToken,
  onChanged,
  onNeedsRefresh,
}: {
  open: boolean;
  onOpenChange: (next: boolean) => void;
  channel: Channel;
  sources: Source[];
  linkedSources: Source[];
  getAdminToken: () => string;
  onChanged: (updated: Channel) => void;
  onNeedsRefresh: () => void | Promise<void>;
}) {
  const [busyId, setBusyId] = React.useState<string | null>(null);
  const linkedIds = new Set(channel.source_ids);
  const available = sources.filter((s) => !linkedIds.has(s.id));

  async function attach(sourceId: string) {
    setBusyId(sourceId);
    try {
      const updated = await channelsApi.attachSource(
        channel.id,
        sourceId,
        getAdminToken(),
      );
      onChanged(updated);
      toast.success("Готово: источник привязан");
    } catch (err) {
      handleChannelError(err);
    } finally {
      setBusyId(null);
    }
  }

  async function detach(sourceId: string) {
    setBusyId(sourceId);
    try {
      await channelsApi.detachSource(channel.id, sourceId, getAdminToken());
      // DELETE returns 204, so pull the fresh channel to update source_ids.
      await onNeedsRefresh();
      toast.success("Готово: источник отвязан");
    } catch (err) {
      handleChannelError(err);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full p-0 sm:w-[420px]">
        <div className="flex h-full flex-col">
          <div className="border-b border-white/[0.06] px-5 py-4">
            <SheetTitle>Источники · {channel.name || channel.slug}</SheetTitle>
            <SheetDescription>
              Выберите, какие источники питают этот канал. Один источник может
              питать несколько каналов.
            </SheetDescription>
          </div>

          <div className="flex-1 space-y-5 overflow-y-auto px-5 py-4">
            <section className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] uppercase tracking-[0.18em] text-ink-400">
                  Привязаны
                </span>
                <Badge variant="outline">{linkedSources.length}</Badge>
              </div>
              {linkedSources.length === 0 ? (
                <p className="rounded-lg border border-white/[0.05] bg-white/[0.015] px-3 py-2.5 text-[12px] text-ink-500">
                  Пока ничего не привязано — у канала нет входящих источников.
                </p>
              ) : (
                <div className="space-y-1.5">
                  {linkedSources.map((s) => (
                    <SourceRow
                      key={s.id}
                      source={s}
                      busy={busyId === s.id}
                      action="detach"
                      onAction={() => detach(s.id)}
                    />
                  ))}
                </div>
              )}
            </section>

            <section className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] uppercase tracking-[0.18em] text-ink-400">
                  Доступны
                </span>
                <Badge variant="outline">{available.length}</Badge>
              </div>
              {available.length === 0 ? (
                <p className="rounded-lg border border-white/[0.05] bg-white/[0.015] px-3 py-2.5 text-[12px] text-ink-500">
                  Все источники уже привязаны.
                </p>
              ) : (
                <div className="space-y-1.5">
                  {available.map((s) => (
                    <SourceRow
                      key={s.id}
                      source={s}
                      busy={busyId === s.id}
                      action="attach"
                      onAction={() => attach(s.id)}
                    />
                  ))}
                </div>
              )}
            </section>
          </div>

          <div className="flex items-center justify-end border-t border-white/[0.06] px-5 py-4">
            <Button variant="ghost" onClick={() => onOpenChange(false)}>
              <X className="h-4 w-4" /> Готово
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}

function SourceRow({
  source,
  busy,
  action,
  onAction,
}: {
  source: Source;
  busy: boolean;
  action: "attach" | "detach";
  onAction: () => void;
}) {
  return (
    <div className="flex items-center gap-2.5 rounded-lg border border-white/[0.05] bg-white/[0.015] px-2.5 py-2">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <span className="truncate text-[13px] text-ink-100">
            {source.title || source.handle}
          </span>
          <Badge variant="outline" className="uppercase">
            {source.kind}
          </Badge>
        </div>
        <div className="truncate text-[11px] font-mono text-ink-500">{source.handle}</div>
      </div>
      <Button
        variant={action === "detach" ? "ghost" : "outline"}
        size="sm"
        onClick={onAction}
        disabled={busy}
        className="shrink-0"
      >
        {busy ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : action === "detach" ? (
          <>
            <Link2Off className="h-3.5 w-3.5" /> Убрать
          </>
        ) : (
          <>
            <Plus className="h-3.5 w-3.5" /> Добавить
          </>
        )}
      </Button>
    </div>
  );
}
