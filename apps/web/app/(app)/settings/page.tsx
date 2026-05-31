import * as React from "react";
import {
  AlertTriangle,
  Beaker,
  CircleDot,
  KeyRound,
  Plug,
  PlugZap,
  Radio,
  Shield,
  ShieldAlert,
  Wifi,
} from "lucide-react";
import { Topbar } from "@/components/layout/topbar";
import { PageShell, PageSection } from "@/components/layout/page-shell";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ReadinessSectionCard } from "@/components/feature/readiness-section";
import { FirstPostChecklist } from "@/components/feature/first-post-checklist";
import { IntegrationsVault } from "@/components/feature/vault/integrations-vault";
import { data } from "@/lib/data";
import type { ApiConnection } from "@/lib/types";
import { cn } from "@/lib/utils";

const CONNECTION_STATE_RU: Record<string, string> = {
  connected: "подключено",
  worker_stale: "процесс молчит",
  missing_integrations: "нет подключений",
  fallback: "демо без сервера",
};

export default async function SettingsPage() {
  const [status, readiness, candidates, sources, jobs, connection] = await Promise.all([
    data.status(),
    data.readiness(),
    data.candidates(),
    data.sources(),
    data.jobs(),
    data.connection(),
  ]);

  const live = status.live_mode;

  return (
    <>
      <Topbar
        title="Настройки"
        subtitle="Готовность к боевому режиму, подключения и безопасность"
        pill={{ label: live ? "Боевой режим" : "Демо-режим", tone: live ? "violet" : "cyan" }}
      />
      <PageShell>
        {/* Safety banner */}
        <Card tone="violet" className="overflow-hidden p-4 sm:p-5">
          <div className="flex items-start gap-3 sm:items-center">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-accent-violet/15 ring-1 ring-accent-violet/40 shrink-0">
              <Shield className="h-4 w-4 text-accent-violet" strokeWidth={2.2} />
            </div>
            <div className="min-w-0 flex-1 text-sm text-ink-100">
              <div className="font-medium text-ink-50">
                Без вашего одобрения ни один пост не уйдёт.
              </div>
              <div className="text-xs text-ink-300 mt-0.5 leading-relaxed">
                Кнопки проверки ничего не публикуют. Тестовый просмотр не связывается
                с внешними сервисами. Запрет на публикацию без одобрения держат
                три независимых слоя защиты.
              </div>
            </div>
            <Badge variant="violet" className="hidden sm:inline-flex">
              тройная защита
            </Badge>
          </div>
        </Card>

        {/* Mode overview */}
        <PageSection title="Режимы работы" description="Пять переключателей определяют, как ведёт себя система">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
            <ModeCard
              label="Демо-режим"
              flag={status.demo_mode}
              tone="cyan"
              icon={Beaker}
              on="Показываются демо-данные"
              off="Только реальные данные"
              envVar="DEMO_MODE"
            />
            <ModeCard
              label="Заглушки сервисов"
              flag={status.mock_mode}
              tone="cyan"
              icon={CircleDot}
              on="Без ключей работают заглушки"
              off="Без ключей будет ошибка"
              envVar="MOCK_MODE"
            />
            <ModeCard
              label="Боевой режим"
              flag={status.live_mode}
              tone="violet"
              icon={Wifi}
              on="Нужны реальные настройки"
              off="Активен демо-режим"
              envVar="LIVE_MODE"
            />
            <ModeCard
              label="Тестовая публикация"
              flag={status.dry_run_publish}
              tone="violet"
              icon={Shield}
              on="Готовит текст, но не отправляет"
              off="Реальная отправка включена"
              envVar="DRY_RUN_PUBLISH"
            />
            <ModeCard
              label="Публикация включена"
              flag={status.publishing_enabled}
              tone="rose"
              icon={ShieldAlert}
              on="ГЛАВНЫЙ переключатель — реальная отправка доступна"
              off="Реальная отправка невозможна"
              envVar="PUBLISHING_ENABLED"
              dangerOn
            />
          </div>
        </PageSection>

        {/* Connection honesty — 4 distinct states */}
        <ConnectionCard connection={connection} />

        {/* Integrations vault */}
        <PageSection
          title="Хранилище ключей"
          description="Добавляйте ключи API без правки файла .env. Хранятся в зашифрованном виде. Значения из .env имеют приоритет."
        >
          <IntegrationsVault />
        </PageSection>

        {/* First post checklist */}
        <FirstPostChecklist
          report={readiness}
          candidates={candidates}
          sources={sources}
          jobs={jobs}
        />

        {/* Readiness sections */}
        {readiness ? (
          <PageSection
            title="Готовность к запуску"
            description={`Готовность ${readiness.overall_score}% — ${readiness.overall_label}`}
          >
            <div className="grid gap-3 lg:grid-cols-2 3xl:grid-cols-2">
              {readiness.sections.map((section) => (
                <ReadinessSectionCard key={section.key} section={section} />
              ))}
            </div>
          </PageSection>
        ) : (
          <Card className="p-6 text-center text-sm text-ink-400">
            Отчёт о готовности недоступен — сервер не отвечает. Запустите бэкенд,
            чтобы заполнить этот раздел.
          </Card>
        )}

        {/* Runbook hint */}
        <Card className="p-4 sm:p-5">
          <div className="flex items-center gap-2 text-sm font-medium text-ink-50">
            <KeyRound className="h-4 w-4 text-accent-cyan" />
            Как безопасно перейти в боевой режим
          </div>
          <ol className="mt-2 space-y-1 pl-4 text-xs text-ink-300 leading-relaxed list-decimal">
            <li>
              Заполните значения в <code className="text-ink-100">.env</code> (см.{" "}
              <code className="text-ink-100">.env.example</code> и{" "}
              <code className="text-ink-100">docs/INTEGRATIONS.md</code>).
            </li>
            <li>
              Поставьте <code className="text-ink-100">LIVE_MODE=true</code> и{" "}
              <code className="text-ink-100">MOCK_MODE=false</code>.
            </li>
            <li>
              На первый полный прогон оставьте{" "}
              <code className="text-ink-100">DRY_RUN_PUBLISH=true</code>.
            </li>
            <li>Проверьте каждое подключение кнопками выше.</li>
            <li>Одобрите один пост → посмотрите тестовый просмотр в редакторе.</li>
            <li>
              Только когда всё зелёное: поставьте{" "}
              <code className="text-ink-100">DRY_RUN_PUBLISH=false</code> и{" "}
              <code className="text-ink-100">PUBLISHING_ENABLED=true</code>.
            </li>
          </ol>
        </Card>
      </PageShell>
    </>
  );
}

function ConnectionCard({ connection }: { connection: ApiConnection }) {
  const meta = (() => {
    switch (connection.state) {
      case "connected":
        return {
          icon: PlugZap,
          tone: "success" as const,
          label: "Сервер подключён",
          hint: "Дашборд работает с живым API. Фоновый процесс активен.",
        };
      case "worker_stale":
        return {
          icon: AlertTriangle,
          tone: "warning" as const,
          label: "Фоновый процесс молчит",
          hint: `API доступен, но фоновый процесс давно не выходил на связь (статус: ${
            connection.worker_overall ?? "неизвестно"
          }). Пока он не восстановится, одобренные посты не будут отправляться.`,
        };
      case "missing_integrations":
        return {
          icon: Radio,
          tone: "warning" as const,
          label: "Не хватает подключений",
          hint:
            "Боевой режим включён, но не настроены важные сервисы: " +
            (connection.missing?.join(", ") ?? "—") +
            ". Система безопасно переключится на заглушки или заблокирует отправку.",
        };
      default:
        return {
          icon: Plug,
          tone: "warning" as const,
          label: "Демо без сервера",
          hint:
            "Дашборд не может достучаться до API — все экраны показывают демо-данные. " +
            "Укажите NEXT_PUBLIC_API_URL в Vercel на доступный бэкенд (см. docs/DEPLOY_BACKEND_RUNTIME.md).",
        };
    }
  })();
  const Icon = meta.icon;
  const dotClass = meta.tone === "success" ? "bg-state-success" : "bg-accent-amber";
  const badgeVariant = meta.tone === "success" ? "mint" : "amber";

  return (
    <Card className="p-4 sm:p-5">
      <div className="flex items-start gap-3">
        <div
          className={cn(
            "grid h-9 w-9 place-items-center rounded-xl ring-1 shrink-0",
            meta.tone === "success"
              ? "bg-state-success/10 ring-state-success/30"
              : "bg-accent-amber/10 ring-accent-amber/30",
          )}
        >
          <Icon
            className={cn(
              "h-4 w-4",
              meta.tone === "success" ? "text-state-success" : "text-accent-amber",
            )}
            strokeWidth={2.2}
          />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-ink-50">{meta.label}</span>
            <Badge variant={badgeVariant}>
              <span className={cn("h-1.5 w-1.5 rounded-full", dotClass)} />
              {CONNECTION_STATE_RU[connection.state] ?? connection.state.replace("_", " ")}
            </Badge>
          </div>
          <p className="mt-1 text-[12px] text-ink-300 leading-relaxed">{meta.hint}</p>
          <div className="mt-1.5 text-[11px] text-ink-500">
            адрес сервера <span className="font-mono text-ink-300">{connection.base}</span>
            {connection.worker_overall && (
              <>
                <span className="mx-1.5 text-ink-600">·</span>
                фоновый процесс{" "}
                <span className="font-mono text-ink-300">{connection.worker_overall}</span>
              </>
            )}
          </div>
        </div>
      </div>
      {connection.state === "fallback" && (
        <>
          <Separator className="my-3" />
          <p className="text-[11px] text-ink-400 leading-relaxed">
            Чтобы выйти из демо-режима: разверните бэкенд (см.{" "}
            <code className="text-ink-100">docs/DEPLOY_BACKEND_RUNTIME.md</code>) и укажите{" "}
            <code className="text-ink-100">NEXT_PUBLIC_API_URL</code> в проекте Vercel.
          </p>
        </>
      )}
    </Card>
  );
}

function ModeCard({
  label,
  flag,
  tone,
  icon: Icon,
  on,
  off,
  envVar,
  dangerOn,
}: {
  label: string;
  flag: boolean;
  tone: "cyan" | "violet" | "rose";
  icon: React.ComponentType<{ className?: string; strokeWidth?: number }>;
  on: string;
  off: string;
  envVar: string;
  dangerOn?: boolean;
}) {
  const active = flag;
  const ringClass =
    active && tone === "violet"
      ? "ring-accent-violet/30 bg-accent-violet/[0.07]"
      : active && tone === "rose"
      ? "ring-state-danger/30 bg-state-danger/[0.07]"
      : active
      ? "ring-accent-cyan/30 bg-accent-cyan/[0.07]"
      : "";
  return (
    <Card className={cn("p-3.5 transition-colors", active && "ring-1", ringClass)}>
      <div className="flex items-center gap-2">
        <Icon className={cn("h-3.5 w-3.5", active ? "" : "text-ink-400")} strokeWidth={2} />
        <span className="text-[11px] uppercase tracking-[0.18em] text-ink-400">{label}</span>
        <Badge
          variant={
            active
              ? dangerOn
                ? "rose"
                : tone === "violet"
                ? "violet"
                : "cyan"
              : "outline"
          }
          className="ml-auto"
        >
          {active ? "ВКЛ" : "ВЫКЛ"}
        </Badge>
      </div>
      <div className="mt-2 text-[12px] text-ink-100 leading-snug min-h-[32px]">
        {active ? on : off}
      </div>
      <div className="mt-1.5 text-[10px] font-mono text-ink-500">{envVar}</div>
    </Card>
  );
}
