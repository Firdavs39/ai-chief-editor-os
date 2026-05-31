"use client";

import * as React from "react";
import { FileSearch, Loader2, Shield, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetTitle,
  SheetDescription,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import type { DryRunPreview } from "@/lib/types";

export function DryRunButton({
  candidateId,
  defaultPlatform = "telegram",
}: {
  candidateId: string;
  defaultPlatform?: "telegram" | "threads" | "reddit";
}) {
  const [open, setOpen] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  const [platform, setPlatform] = React.useState(defaultPlatform);
  const [preview, setPreview] = React.useState<DryRunPreview | null>(null);

  async function run(p: typeof platform) {
    setPlatform(p);
    setLoading(true);
    try {
      const result = await api.dryRunPublish(candidateId, p);
      setPreview(result);
    } catch {
      toast.error("Ошибка: проверка не прошла", {
        description: "Сервер недоступен. Попробуйте ещё раз.",
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <Sheet
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (o && !preview) run(platform);
      }}
    >
      <SheetTrigger asChild>
        <Button variant="outline" size="sm" className="text-accent-cyan hover:border-accent-cyan/40">
          <FileSearch className="h-3.5 w-3.5" /> Проверить (без отправки)
        </Button>
      </SheetTrigger>
      <SheetContent side="right" className="w-full sm:w-[420px] 3xl:w-[480px] p-5 overflow-y-auto">
        <div className="flex items-start gap-3 pb-3">
          <div className="grid h-9 w-9 place-items-center rounded-xl bg-accent-cyan/15 ring-1 ring-accent-cyan/40">
            <Shield className="h-4 w-4 text-accent-cyan" strokeWidth={2.2} />
          </div>
          <div className="min-w-0">
            <SheetTitle className="text-[14px]">Проверка перед публикацией</SheetTitle>
            <SheetDescription className="text-[11px]">
              Показываем, что именно ушло бы в канал. Никуда ничего не отправляется.
            </SheetDescription>
          </div>
        </div>

        <div className="mt-2 flex gap-1.5">
          {(["telegram", "threads", "reddit"] as const).map((p) => (
            <button
              key={p}
              onClick={() => run(p)}
              className={
                "rounded-md px-2.5 py-1 text-[11px] font-medium uppercase tracking-wide transition-colors " +
                (platform === p
                  ? "bg-accent-cyan/15 text-accent-cyan ring-1 ring-accent-cyan/30"
                  : "border border-white/[0.07] bg-white/[0.02] text-ink-300 hover:bg-white/[0.04]")
              }
            >
              {p}
            </button>
          ))}
        </div>

        {loading && (
          <div className="mt-4 flex items-center gap-2 text-sm text-ink-300">
            <Loader2 className="h-4 w-4 animate-spin" /> Готовлю текст…
          </div>
        )}

        {!loading && preview && (
          <PreviewBody preview={preview} />
        )}
      </SheetContent>
    </Sheet>
  );
}

function PreviewBody({ preview }: { preview: DryRunPreview }) {
  const p = preview.preview;
  const overLimit = p.body_length > (p.limits?.max_length ?? Infinity);
  return (
    <div className="mt-4 space-y-4 text-sm">
      <div className="flex flex-wrap gap-1.5">
        <Badge variant="cyan">{p.platform}</Badge>
        <Badge variant={overLimit ? "rose" : "outline"}>
          {p.body_length} / {p.limits?.max_length ?? "?"} символов
        </Badge>
        <Badge variant={p.would_send ? "violet" : "outline"}>
          {p.would_send ? "отправилось бы" : "не отправилось бы"}
        </Badge>
      </div>

      <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
        <div className="text-[10px] uppercase tracking-[0.18em] text-ink-500 mb-1.5">
          Текст поста
        </div>
        <pre className="whitespace-pre-wrap break-words text-[12.5px] leading-relaxed text-ink-100 font-sans">
          {p.body}
        </pre>
      </div>

      {p.cta && (
        <div className="rounded-xl border border-accent-violet/20 bg-accent-violet/[0.05] p-3">
          <div className="text-[10px] uppercase tracking-[0.18em] text-accent-violet/80 mb-1.5">
            CTA
          </div>
          <p className="text-[12.5px] text-ink-100">{p.cta}</p>
        </div>
      )}

      <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3 space-y-1.5 text-[11px]">
        <div className="text-[10px] uppercase tracking-[0.18em] text-ink-500 mb-1">
          Состояние безопасности
        </div>
        <Row k="PUBLISHING_ENABLED" v={String(p.safety.publishing_enabled)} />
        <Row k="DRY_RUN_PUBLISH" v={String(p.safety.dry_run_publish)} />
        <Row k="MOCK_MODE" v={String(p.safety.mock_mode)} />
        {p.platform === "telegram" && (
          <>
            <Row k="bot_token_present" v={String(Boolean((p as Record<string, unknown>)["bot_token_present"]))} />
            <Row k="target_channel_id_present" v={String(Boolean((p as Record<string, unknown>)["target_channel_id_present"]))} />
          </>
        )}
        {p.platform === "threads" && (
          <>
            <Row k="postiz_base_url_present" v={String(Boolean((p as Record<string, unknown>)["postiz_base_url_present"]))} />
            <Row
              k="postiz_threads_integration_id_present"
              v={String(Boolean((p as Record<string, unknown>)["postiz_threads_integration_id_present"]))}
            />
          </>
        )}
        {p.platform === "reddit" && (
          <>
            <Row k="postiz_base_url_present" v={String(Boolean((p as Record<string, unknown>)["postiz_base_url_present"]))} />
            <Row
              k="postiz_reddit_integration_id_present"
              v={String(Boolean((p as Record<string, unknown>)["postiz_reddit_integration_id_present"]))}
            />
          </>
        )}
      </div>

      <p className="text-[11px] text-ink-500 leading-relaxed">
        {preview.safety_note}
      </p>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-center justify-between gap-2 font-mono">
      <span className="text-ink-500">{k}</span>
      <span className="text-ink-100">{v}</span>
    </div>
  );
}
