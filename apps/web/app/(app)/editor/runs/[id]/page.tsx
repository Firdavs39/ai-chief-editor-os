"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { PageShell, PageSection } from "@/components/layout/page-shell";
import { Topbar } from "@/components/layout/topbar";
import { Button } from "@/components/ui/button";
import { OperatorUnlock } from "@/components/feature/generation/operator-unlock";
import { RunTimeline } from "@/components/feature/generation/run-timeline";
import { useOperatorToken } from "@/lib/operator-auth";

/**
 * Run viewer page for the Quality Editorial Workflow.
 *
 * - Client component. Uses the memory-only operator token via the context
 *   provider mounted in (app)/layout.tsx.
 * - Polling, status rendering, artifact display, and cancel button all
 *   live inside `<RunTimeline>`. The page itself only handles unlock
 *   gating and layout.
 */
export default function RunPage() {
  const params = useParams<{ id: string }>();
  const id = String(params?.id ?? "");
  const { unlocked } = useOperatorToken();

  return (
    <>
      <Topbar
        title="Создание поста"
        subtitle={`Задача №${id || "—"}`}
        pill={{
          label: unlocked ? "разблокировано" : "заблокировано",
          tone: unlocked ? "violet" : "cyan",
        }}
        actions={
          <Button asChild variant="ghost" size="sm">
            <Link href="/editor">
              <ArrowLeft className="h-4 w-4" /> К списку постов
            </Link>
          </Button>
        }
      />
      <PageShell>
        {!unlocked ? (
          <PageSection
            title="Разблокировать просмотр"
            description="Токен хранится только в памяти этой вкладки — обновление страницы его сотрёт."
          >
            <OperatorUnlock
              title="Введите админ-токен"
              description="Чтобы видеть прогресс создания поста, введите админ-токен (из .env, поле ADMIN_TOKEN). Он не сохраняется в браузере и не попадает в ссылку."
            />
          </PageSection>
        ) : id ? (
          <PageSection title="Прогресс создания">
            <RunTimeline runId={id} />
          </PageSection>
        ) : (
          <PageSection title="Номер задачи не указан">
            <div className="text-[12px] text-ink-400">
              В ссылке нет номера задачи — проверьте адрес.
            </div>
          </PageSection>
        )}
      </PageShell>
    </>
  );
}
