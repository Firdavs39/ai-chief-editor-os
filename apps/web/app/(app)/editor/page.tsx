import * as React from "react";
import Link from "next/link";
import { Sparkles, Filter } from "lucide-react";
import { Topbar } from "@/components/layout/topbar";
import { PageShell, PageSection } from "@/components/layout/page-shell";
import { CandidateCard } from "@/components/feature/candidate-card";
import { EmptyState } from "@/components/feature/empty-state";
import { GenerateBriefButton } from "@/components/feature/generation/generate-brief-button";
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
        title="AI Editor"
        subtitle="Workspace для всех кандидатов от ИИ-редактора"
        pill={{ label: `${candidates.length} candidates`, tone: "violet" }}
        actions={
          <div className="flex items-center gap-2">
            <GenerateBriefButton size="sm" />
            <Button size="sm" variant="outline" asChild>
              <Link href="/trends"><Sparkles className="h-4 w-4" /> New from trend</Link>
            </Button>
          </div>
        }
      />
      <PageShell>
        {candidates.length === 0 ? (
          <EmptyState
            title="No candidates yet"
            description="Запусти Trend Radar или нажми Generate brief на любом кластере — и здесь появятся карточки кандидатов."
            action={
              <Button asChild>
                <Link href="/trends">Open Trend Radar</Link>
              </Button>
            }
          />
        ) : (
          <>
            <PageSection
              title="Drafts ready for review"
              description="Свежие кандидаты, ждущие твоей правки или approval"
              action={
                <div className="flex items-center gap-2 text-xs text-ink-400">
                  <Filter className="h-3.5 w-3.5" />
                  status: draft + revised
                </div>
              }
            >
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 3xl:grid-cols-3 4xl:grid-cols-4">
                {drafts.map((c) => (
                  <CandidateCard key={c.id} candidate={c} />
                ))}
                {drafts.length === 0 && (
                  <Badge variant="outline">Ничего на проверке</Badge>
                )}
              </div>
            </PageSection>

            <PageSection
              title="Reviewed"
              description="Approved, published, rejected — историческая линейка"
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
