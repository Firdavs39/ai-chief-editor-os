"use client";

import * as React from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Circle,
  Loader2,
  MinusCircle,
  PlayCircle,
  ShieldQuestion,
  Sparkles,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useRouter } from "next/navigation";
import type { ReadinessItem, ReadinessSection } from "@/lib/types";
import { cn } from "@/lib/utils";

const ITEM_TEST_FN: Record<string, () => Promise<ReadinessItem>> = {
  "llm.provider": () => api.testLlm(),
  "llm.anthropic": () => api.testLlm(),
  "llm.openai": () => api.testLlm(),
  "telegram.bot": () => api.testTelegramBot(),
  "telethon.session": () => api.testTelethon(),
  "reddit.api": () => api.testReddit(),
  "postiz.api": () => api.testPostiz(),
};

const STATUS_DOT: Record<string, string> = {
  valid: "bg-state-success",
  mock: "bg-accent-cyan",
  configured: "bg-accent-violet",
  missing_config: "bg-accent-amber",
  disabled: "bg-ink-500",
  invalid: "bg-state-danger",
  error: "bg-state-danger",
  unavailable: "bg-ink-500",
};

const STATUS_ICON: Record<string, React.ComponentType<{ className?: string }>> = {
  valid: CheckCircle2,
  mock: Sparkles,
  configured: Circle,
  missing_config: AlertTriangle,
  disabled: MinusCircle,
  invalid: XCircle,
  error: XCircle,
  unavailable: ShieldQuestion,
};

function statusToBadge(status: string): "mint" | "cyan" | "violet" | "amber" | "rose" | "outline" {
  if (status === "valid") return "mint";
  if (status === "mock") return "cyan";
  if (status === "configured") return "violet";
  if (status === "missing_config") return "amber";
  if (status === "invalid" || status === "error") return "rose";
  return "outline";
}

const READINESS_STATUS_RU: Record<string, string> = {
  valid: "работает",
  mock: "демо",
  configured: "настроено",
  missing_config: "нет настроек",
  disabled: "выключено",
  invalid: "неверно",
  error: "ошибка",
  unavailable: "недоступно",
};

function ReadinessRow({ item }: { item: ReadinessItem }) {
  const router = useRouter();
  const [busy, setBusy] = React.useState(false);
  const [latest, setLatest] = React.useState<ReadinessItem>(item);
  const Icon = STATUS_ICON[latest.status] ?? Circle;

  React.useEffect(() => setLatest(item), [item]);

  const test = ITEM_TEST_FN[latest.key];

  async function runTest() {
    if (!test) return;
    setBusy(true);
    try {
      const result = await test();
      setLatest(result);
      toast.success(`Проверено: ${latest.label}`, {
        description: result.message || result.status,
      });
      router.refresh();
    } catch {
      toast.error("Ошибка проверки", {
        description: "Сервер недоступен. Откройте Настройки локально или подключите бэкенд.",
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex items-start gap-3 rounded-xl border border-white/[0.05] bg-white/[0.015] p-3 sm:p-3.5 transition-colors hover:bg-white/[0.03]">
      <div
        className={cn(
          "grid h-8 w-8 sm:h-9 sm:w-9 shrink-0 place-items-center rounded-lg ring-1 ring-white/[0.05]",
          "bg-white/[0.04]",
        )}
      >
        <Icon
          className={cn(
            "h-4 w-4",
            latest.severity === "success" && "text-state-success",
            latest.severity === "warning" && "text-accent-amber",
            latest.severity === "danger" && "text-state-danger",
            latest.severity === "info" && "text-ink-200",
          )}
        />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-medium text-ink-50">{latest.label}</span>
          <Badge variant={statusToBadge(latest.status)}>
            <span className={cn("h-1.5 w-1.5 rounded-full", STATUS_DOT[latest.status])} />
            {READINESS_STATUS_RU[latest.status] ?? latest.status.replace("_", " ")}
          </Badge>
        </div>
        {latest.message && (
          <p className="mt-1 text-[12px] text-ink-300 leading-relaxed">{latest.message}</p>
        )}
        {latest.missing_env_vars.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {latest.missing_env_vars.map((v) => (
              <span
                key={v}
                className="rounded-md border border-accent-amber/30 bg-accent-amber/10 px-1.5 py-0.5 font-mono text-[10px] text-accent-amber"
              >
                {v}
              </span>
            ))}
          </div>
        )}
        {latest.next_action && (
          <p className="mt-1.5 text-[11px] text-ink-500 italic">→ {latest.next_action}</p>
        )}
        {/* surface a few safe details */}
        {Object.keys(latest.safe_details).length > 0 && (
          <SafeDetails details={latest.safe_details} />
        )}
      </div>
      {test !== undefined && latest.can_test && (
        <Button
          variant="outline"
          size="sm"
          disabled={busy}
          onClick={runTest}
          className="shrink-0"
        >
          {busy ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> Проверяю…
            </>
          ) : (
            <>
              <PlayCircle className="h-3.5 w-3.5" /> Проверить
            </>
          )}
        </Button>
      )}
    </div>
  );
}

function SafeDetails({ details }: { details: Record<string, unknown> }) {
  // Walk one level deep. Never render `prefix`/`suffix`/`token`/`secret`/`key` raw — but the
  // backend already strips those; this is belt-and-braces.
  const entries: { k: string; v: string }[] = [];
  for (const [k, v] of Object.entries(details)) {
    if (/^(token|secret|password)$/i.test(k)) continue;
    if (typeof v === "object" && v !== null) {
      const obj = v as Record<string, unknown>;
      if ("present" in obj || "length" in obj) {
        const present = obj.present ? "✓" : "—";
        const length = obj.length ? ` (len ${obj.length})` : "";
        entries.push({ k, v: `${present}${length}` });
      } else {
        entries.push({ k, v: JSON.stringify(v).slice(0, 80) });
      }
    } else {
      entries.push({ k, v: String(v).slice(0, 80) });
    }
  }
  if (entries.length === 0) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-1.5 text-[10px]">
      {entries.slice(0, 6).map((e) => (
        <span
          key={e.k}
          className="rounded-md border border-white/[0.06] bg-white/[0.02] px-1.5 py-0.5 text-ink-400"
        >
          <span className="text-ink-500">{e.k}</span>
          <span className="ml-1 text-ink-200">{e.v}</span>
        </span>
      ))}
    </div>
  );
}

function pluralChecks(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return "проверка";
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return "проверки";
  return "проверок";
}

export function ReadinessSectionCard({ section }: { section: ReadinessSection }) {
  return (
    <Card className="p-4 sm:p-5 space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-[11px] font-medium uppercase tracking-[0.18em] text-ink-400">
          {section.label}
        </div>
        <div className="text-[10px] text-ink-500">
          {section.items.length} {pluralChecks(section.items.length)}
        </div>
      </div>
      <div className="space-y-2">
        {section.items.map((it) => (
          <ReadinessRow key={it.key} item={it} />
        ))}
      </div>
    </Card>
  );
}
