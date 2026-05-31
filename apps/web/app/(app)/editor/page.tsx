import * as React from "react";
import Link from "next/link";
import { Sparkles, Filter } from "lucide-react";
import { Topbar } from "@/components/layout/topbar";
import { PageShell, PageSection } from "@/components/layout/page-shell";
import { CandidateCard } from "@/components/feature/candidate-card";
import { EmptyState } from "@/components/feature/empty-state";
import { GenerateBriefButton } from "@/components/feature/generation/generate-brief-button";
import { UnlockBanner } from "@/components/feature/unlock-banner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { data } from "@/lib/data";

export default async function EditorIndexPage() {
  const candidates = await data.candidates();
  const drafts = candidates.filter((c) => c.status === "draft" || c.status === "revised");
  const reviewed = candidates.filter((c) => c.status !== "draft" && c.status !== "revised");

  return (
    <>
      <Topbar
        title="Редактор"
        subtitle="Все посты, которые подготовил ИИ-редактор"
        pill={{ label: `${candidates.length} постов`, tone: "violet" }}
        actions={
          <div className="flex items-center gap-2">
            <GenerateBriefButton size="sm" />
            <Button size="sm" variant="outline" asChild>
              <Link href="/trends"><Sparkles className="h-4 w-4" /> Из тренда →</Link>
            </Button>
          </div>
        }
      />
      <PageShell>
        {/* Плашка разблокировки — кнопка "Создать пост" требует админ-токен. */}
        <UnlockBanner description="Введите админ-токен (из .env, поле ADMIN_TOKEN), чтобы создавать посты и одобрять их. Просмотр готовых постов работает и без токена." />

        {candidates.length === 0 ? (
          <EmptyState
            title="Постов пока нет"
            description="Нажмите «Создать пост» вверху или возьмите готовый тренд в разделе Тренды — и здесь появятся черновики."
            action={
              <Button variant="outline" asChild>
                <Link href="/trends">Перейти к трендам →</Link>
              </Button>
            }
          />
        ) : (
          <>
            <PageSection
              title="Черновики на проверку"
              description="Свежие посты, которые ждут вашей правки или одобрения"
              action={
                <div className="flex items-center gap-2 text-xs text-ink-400">
                  <Filter className="h-3.5 w-3.5" />
                  черновики и доработанные
                </div>
              }
            >
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 3xl:grid-cols-3 4xl:grid-cols-4">
                {drafts.map((c) => (
                  <CandidateCard key={c.id} candidate={c} />
                ))}
                {drafts.length === 0 && (
                  <Badge variant="outline">Нет постов на проверке</Badge>
                )}
              </div>
            </PageSection>

            <PageSection
              title="Уже рассмотрено"
              description="Одобренные, опубликованные и отклонённые — вся история"
            >
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 3xl:grid-cols-3 4xl:grid-cols-4">
                {reviewed.map((c) => (
                  <CandidateCard key={c.id} candidate={c} variant="compact" />
                ))}
              </div>
            </PageSection>
          </>
        )}
      </PageShell>
    </>
  );
}
