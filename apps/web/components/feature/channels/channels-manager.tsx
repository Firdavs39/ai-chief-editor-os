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
      toast.error("Could not refresh channels", {
        description: "Backend unreachable — showing the last loaded list.",
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
        <StatCard label="Channels" value={channels.length} />
        <StatCard label="Enabled" value={enabledCount} tone="mint" />
        <StatCard label="Source links" value={sourceLinks} />
        <StatCard label="Sources pool" value={sources.length} />
      </div>

      {/* Toolbar. */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-ink-400">
          <Megaphone className="h-3.5 w-3.5 text-accent-violet" />
          Outbound channels
          {refreshing && (
            <Loader2 className="h-3 w-3 animate-spin text-ink-500" />
          )}
        </div>
        <Button
          size="sm"
          onClick={() => setCreateOpen(true)}
          disabled={!unlocked}
          title={unlocked ? "Create a channel" : "Unlock with the admin token first"}
        >
          <Plus className="h-4 w-4" /> Add channel
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
      toast.error("Enter the admin token");
      return;
    }
    unlock(t);
    if (inputRef.current) inputRef.current.value = "";
  }

  if (unlocked) {
    return (
      <Card tone="subtle" className="flex items-center gap-2.5 p-3 sm:p-3.5">
        <div className="grid h-8 w-8 place-items-center rounded-lg bg-accent-violet/15 ring-1 ring-accent-violet/40 shrink-0">
          <Unlock className="h-3.5 w-3.5 text-accent-violet" strokeWidth={2.2} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-ink-50">Operator unlocked</span>
            <Badge variant="violet">
              <Unlock className="h-3 w-3" /> unlocked
            </Badge>
          </div>
          <p className="mt-0.5 text-[11px] text-ink-500">
            Admin token held in memory · refresh clears it · mutations are enabled
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={onLock} className="shrink-0">
          <Lock className="h-3.5 w-3.5" /> Lock
        </Button>
      </Card>
    );
  }

  return (
    <Card className="p-4 sm:p-5">
      <div className="flex items-start gap-3">
        <div className="grid h-10 w-10 place-items-center rounded-xl bg-accent-violet/15 ring-1 ring-accent-violet/40 shrink-0">
          <KeyRound className="h-4 w-4 text-accent-violet" strokeWidth={2.2} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-ink-50">Operator unlock</span>
            <Badge variant="outline">
              <Lock className="h-3 w-3" /> locked
            </Badge>
          </div>
          <p className="mt-1 text-[12px] text-ink-300 leading-relaxed">
            Viewing channels is open. Creating or editing a channel changes where
            approved content publishes, so it needs the admin token. The token
            stays in memory only — refresh clears it.
          </p>
          <div className="mt-2 flex items-center gap-2 text-[11px] text-accent-amber">
            <ShieldAlert className="h-3 w-3" />
            memory-only · no localStorage · no cookies · no URL
          </div>
          <div className="mt-3 flex gap-2">
            <Input
              ref={inputRef}
              type="password"
              autoComplete="off"
              spellCheck={false}
              placeholder="X-Admin-Token"
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  tryUnlock();
                }
              }}
            />
            <Button onClick={tryUnlock}>Unlock</Button>
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
        <div className="text-sm font-medium text-ink-50">No channels yet</div>
        <p className="mx-auto max-w-sm text-[12px] leading-relaxed text-ink-400">
          A channel is one outbound destination (e.g. a Telegram channel) with
          its own style and its own pool of sources. The backend may still be
          starting — channels load from the live API.
        </p>
      </div>
      <Button onClick={onCreate} disabled={!unlocked} size="sm">
        <Plus className="h-4 w-4" /> Add your first channel
      </Button>
      {!unlocked && (
        <p className="text-[11px] text-ink-500">Unlock with the admin token to create one.</p>
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
      toast.error("Channel name is required");
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
      toast.success("Channel created", { description: created.name });
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
            <SheetTitle>New channel</SheetTitle>
            <SheetDescription>
              One outbound destination with its own style and sources.
            </SheetDescription>
          </div>

          <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
            <Field label="Name" hint="Shown in the dashboard. The slug is auto-derived.">
              <Input
                value={name}
                autoFocus
                onChange={(e) => setName(e.target.value)}
                placeholder="BUAI · main feed"
              />
            </Field>

            <Field
              label="Target chat id"
              hint="Public channel @username or numeric chat id. Never a bot token."
            >
              <Input
                value={targetChatId}
                onChange={(e) => setTargetChatId(e.target.value)}
                placeholder="@buai_uz or -1001234567890"
                className="font-mono"
              />
            </Field>

            <div className="grid grid-cols-2 gap-3">
              <Field label="Language">
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
              <Field label="Style profile">
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
              The bot token is not set here. It lives in the Integration Secrets
              Vault and is resolved at publish time via the channel&apos;s bot
              provider. Publishing still requires manual approval.
            </div>
          </div>

          <div className="flex items-center justify-end gap-2 border-t border-white/[0.06] px-5 py-4">
            <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={saving}>
              <X className="h-4 w-4" /> Cancel
            </Button>
            <Button onClick={submit} disabled={saving}>
              {saving ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" /> Creating…
                </>
              ) : (
                <>
                  <Plus className="h-4 w-4" /> Create channel
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
    toast.error("Admin token required", {
      description: "Unlock with the operator token before making changes.",
    });
    return;
  }
  if (e?.code === "admin_token_invalid") {
    toast.error("Admin token rejected", {
      description: "The token was refused (401). Re-enter a valid admin token.",
    });
    return;
  }
  if (e?.code === "conflict") {
    const map: Record<string, string> = {
      default_channel_cannot_be_disabled:
        "The default channel can't be disabled — it's the fallback destination.",
      channel_slug_taken:
        "A channel with this slug already exists. Pick a different name.",
    };
    toast.error("Conflict", {
      description: map[e.detail ?? ""] ?? e.detail ?? "Request conflicts with current state.",
    });
    return;
  }
  if (e?.code === "not_found") {
    toast.error("Not found", { description: "The channel or source no longer exists." });
    return;
  }
  toast.error("Request failed", {
    description: (e instanceof Error ? e.message : String(err)).slice(0, 200),
  });
}
