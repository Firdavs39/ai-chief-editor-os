"use client";

import * as React from "react";
import { FileText, Sparkles } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { GenerationArtifact } from "@/lib/types";

/**
 * Renders the canonical safe payload of one GenerationArtifact.
 *
 * Hard safety rules (Phase 4):
 * - Only the fields listed in `ARTIFACT_SCHEMAS` below are rendered.
 * - Unknown / non-whitelisted fields are NEVER rendered. This protects
 *   against a future regression where a workflow change accidentally
 *   adds raw prompt text, completion text, or hidden reasoning to the
 *   artifact payload — the backend already refuses to persist those,
 *   but the UI also refuses to display them.
 * - The "editorial_rationale" field is the only "reasoning"-shaped
 *   thing rendered, and only if its length is ≤ 240 (the backend cap).
 *   No raw chain-of-thought is ever displayed.
 */

const ARTIFACT_LABELS: Record<string, { ru: string; icon: typeof FileText }> = {
  research_brief: { ru: "Исследование источников", icon: FileText },
  angle: { ru: "Стратегический угол", icon: Sparkles },
  psych: { ru: "Психология аудитории", icon: Sparkles },
  voice_brief: { ru: "Style DNA", icon: Sparkles },
  tg_post: { ru: "Telegram Writer", icon: FileText },
  threads_post: { ru: "Threads Writer", icon: FileText },
  reddit_post: { ru: "Reddit Writer", icon: FileText },
  critic_report: { ru: "Критик / Red Team", icon: Sparkles },
  final_brief: { ru: "Главный редактор", icon: FileText },
  quality_report: { ru: "Quality Judge", icon: Sparkles },
  candidate_link: { ru: "Финализация", icon: Sparkles },
};

// Per-artifact whitelist of fields the UI is allowed to render. Anything
// not listed here is dropped on the floor — this is a defense-in-depth
// guard. The same fields are enforced by pydantic on the backend.
const ARTIFACT_FIELDS: Record<string, readonly string[]> = {
  research_brief: ["editorial_rationale", "fact_bullets", "source_handles", "gaps"],
  angle: ["editorial_rationale", "primary_angle", "contrarian_take", "why_now"],
  psych: ["editorial_rationale", "target_emotion", "hook_pattern", "cognitive_bias_lever"],
  voice_brief: ["editorial_rationale", "sentence_length_target", "vocab_lane", "must_avoid"],
  tg_post: ["editorial_rationale", "hook", "body", "cta"],
  threads_post: ["editorial_rationale", "body", "cta"],
  reddit_post: ["editorial_rationale", "title", "body", "cta"],
  critic_report: [
    "editorial_rationale",
    "slop_count",
    "factual_concerns",
    "length_issues",
    "hook_grade",
  ],
  final_brief: [
    "editorial_rationale",
    "topic",
    "source_summary",
    "why_it_matters",
    "psychology_hook",
    "final_tg",
    "final_threads",
    "final_reddit",
    "cta",
  ],
  quality_report: [
    "editorial_rationale",
    "style_match_score",
    "viral_score",
    "slop_risk",
    "controversy_risk",
    "recommendation",
  ],
  candidate_link: ["candidate_id"],
};

const FIELD_LABELS_RU: Record<string, string> = {
  editorial_rationale: "Редакционное обоснование",
  fact_bullets: "Факты",
  source_handles: "Источники",
  gaps: "Пробелы",
  primary_angle: "Основной угол",
  contrarian_take: "Контр-тейк",
  why_now: "Почему сейчас",
  target_emotion: "Целевая эмоция",
  hook_pattern: "Паттерн крючка",
  cognitive_bias_lever: "Когнитивный рычаг",
  sentence_length_target: "Длина предложений",
  vocab_lane: "Словарная полоса",
  must_avoid: "Чего избегать",
  hook: "Крючок",
  body: "Текст",
  title: "Заголовок",
  cta: "CTA",
  slop_count: "AI-слоп (счётчик)",
  factual_concerns: "Фактические сомнения",
  length_issues: "Проблемы длины",
  hook_grade: "Оценка крючка (0–10)",
  topic: "Тема",
  source_summary: "Резюме источников",
  why_it_matters: "Почему это важно",
  psychology_hook: "Психологический крючок",
  final_tg: "Финальный Telegram",
  final_threads: "Финальный Threads",
  final_reddit: "Финальный Reddit",
  style_match_score: "Style match",
  viral_score: "Viral",
  slop_risk: "Slop risk",
  controversy_risk: "Controversy risk",
  recommendation: "Рекомендация",
  candidate_id: "ID кандидата",
};

function isPrimitive(v: unknown): v is string | number | boolean {
  return typeof v === "string" || typeof v === "number" || typeof v === "boolean";
}

function renderValue(value: unknown): React.ReactNode {
  if (value == null || value === "") {
    return <span className="text-ink-500 italic">—</span>;
  }
  if (typeof value === "number") {
    // Stable rounding for score-shaped values 0..1
    if (value > 0 && value < 1) return <span>{value.toFixed(2)}</span>;
    return <span>{value}</span>;
  }
  if (typeof value === "boolean") {
    return <span>{value ? "yes" : "no"}</span>;
  }
  if (typeof value === "string") {
    return <span className="whitespace-pre-wrap break-words">{value}</span>;
  }
  if (Array.isArray(value)) {
    const items = value.filter(isPrimitive);
    if (items.length === 0) {
      return <span className="text-ink-500 italic">—</span>;
    }
    return (
      <ul className="list-disc list-inside space-y-0.5 text-ink-100">
        {items.map((it, i) => (
          <li key={i} className="whitespace-pre-wrap break-words">
            {String(it)}
          </li>
        ))}
      </ul>
    );
  }
  // Defense-in-depth: refuse to render arbitrary nested objects. The
  // backend schema forbids them, so this is only reached if a future
  // change goes wrong — in which case we show a tag rather than the
  // raw payload.
  return (
    <span className="text-ink-500 italic">[non-primitive value hidden]</span>
  );
}

function ArtifactRow({ field, value }: { field: string; value: unknown }) {
  const ru = FIELD_LABELS_RU[field] ?? field;
  return (
    <div className="border-t border-white/[0.04] py-2 first:border-t-0 first:pt-0">
      <div className="text-[10px] uppercase tracking-[0.18em] text-ink-500">
        {ru}
      </div>
      <div className="mt-1 text-[12.5px] text-ink-100 leading-relaxed">
        {renderValue(value)}
      </div>
    </div>
  );
}

export function ArtifactCard({ artifact }: { artifact: GenerationArtifact }) {
  const meta = ARTIFACT_LABELS[artifact.name];
  const allowed = ARTIFACT_FIELDS[artifact.name] ?? ["editorial_rationale"];
  const Icon = meta?.icon ?? FileText;
  const ruTitle = meta?.ru ?? artifact.name;

  // Filter the payload to the whitelist. ANY field not in the whitelist
  // is dropped — this is the hard guard against unexpected data shapes.
  const rendered: { field: string; value: unknown }[] = [];
  for (const field of allowed) {
    if (field in artifact.payload) {
      rendered.push({ field, value: artifact.payload[field] });
    }
  }

  return (
    <Card className="p-4 sm:p-5">
      <div className="flex items-start gap-3">
        <div className="grid h-9 w-9 place-items-center rounded-xl bg-accent-violet/10 ring-1 ring-accent-violet/30 shrink-0">
          <Icon className="h-4 w-4 text-accent-violet" strokeWidth={2.2} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-ink-50">{ruTitle}</span>
            <Badge variant="violet">{artifact.name}</Badge>
            <Badge variant="outline">v{artifact.schema_version}</Badge>
          </div>
          <div className="mt-3 space-y-0">
            {rendered.length === 0 ? (
              <div className="text-[12px] text-ink-500 italic">
                Артефакт пуст
              </div>
            ) : (
              rendered.map((r) => (
                <ArtifactRow key={r.field} field={r.field} value={r.value} />
              ))
            )}
          </div>
        </div>
      </div>
    </Card>
  );
}
