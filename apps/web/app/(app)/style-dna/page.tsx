import * as React from "react";
import { Type, Save, Quote, Slash, Target, Languages } from "lucide-react";
import { Topbar } from "@/components/layout/topbar";
import { PageShell, PageSection } from "@/components/layout/page-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { VoiceRadar } from "@/components/feature/voice-radar";
import { data } from "@/lib/data";

export default async function StyleDnaPage() {
  const style = await data.style();
  const sliders = Object.entries(style.voice_sliders ?? {}).map(([key, value]) => ({
    key,
    value: typeof value === "number" ? value : Number(value) || 0,
  }));

  return (
    <>
      <Topbar
        title="Style DNA"
        subtitle="Brand voice control panel — голос редакции и его границы"
        pill={{ label: style.lang_primary.toUpperCase(), tone: "violet" }}
        actions={
          <Button size="sm">
            <Save className="h-4 w-4" /> Save profile
          </Button>
        }
      />
      <PageShell>
        {/* Voice signature hero */}
        <Card tone="violet" className="overflow-hidden">
          <div className="grid gap-4 p-4 sm:p-5 3xl:p-6 sm:grid-cols-[1fr_auto] items-center">
            <div className="space-y-3 min-w-0">
              <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-accent-violet/90">
                <Type className="h-3.5 w-3.5" />
                Voice signature
              </div>
              <h2 className="display text-[20px] sm:text-[24px] 3xl:text-[28px] font-semibold leading-tight tracking-tight text-ink-50">
                <span className="text-ink-300">Tone:</span>{" "}
                {style.tone || "Экспертно, по-человечески, без воды."}
              </h2>
              <p className="text-sm text-ink-300 leading-relaxed">
                <span className="text-ink-400">Audience —</span>{" "}
                {style.audience || "Создатели контента и маркетологи 24-40."}
              </p>
              <div className="flex flex-wrap gap-1.5 pt-1">
                <Badge variant="cyan">
                  <Languages className="h-3 w-3" /> primary: {style.lang_primary}
                </Badge>
                {style.target_topics.slice(0, 3).map((t) => (
                  <Badge key={t} variant="outline">
                    {t}
                  </Badge>
                ))}
                {style.target_topics.length > 3 && (
                  <Badge variant="outline">+{style.target_topics.length - 3}</Badge>
                )}
              </div>
            </div>
            <div className="grid place-items-center">
              <VoiceRadar sliders={sliders} size={200} />
            </div>
          </div>
        </Card>

        <div className="grid gap-4 lg:gap-5 xl:gap-6 xl:grid-cols-[1.2fr_1fr]">
          <div className="space-y-3 sm:space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm flex items-center gap-2">
                  <Type className="h-4 w-4 text-accent-violet" /> Tone & audience
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <Field label="Tone">
                  <Textarea defaultValue={style.tone} className="min-h-[88px]" />
                </Field>
                <Field label="Audience">
                  <Textarea defaultValue={style.audience} className="min-h-[72px]" />
                </Field>
                <Field label="Writing rules">
                  <Textarea defaultValue={style.writing_rules} className="min-h-[110px]" />
                </Field>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm flex items-center gap-2">
                  <Quote className="h-4 w-4 text-accent-cyan" /> Example posts
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {style.example_posts.map((p, i) => (
                  <figure
                    key={i}
                    className="relative rounded-xl border border-white/[0.06] bg-white/[0.02] p-4 text-[14px] leading-relaxed text-ink-100"
                  >
                    <Quote
                      className="absolute -top-2 left-3 h-4 w-4 text-accent-cyan bg-bg-base px-0.5"
                      strokeWidth={2.2}
                    />
                    <blockquote className="italic">{p}</blockquote>
                    <figcaption className="mt-2 text-[10px] uppercase tracking-[0.18em] text-ink-500">
                      example · {String(i + 1).padStart(2, "0")}
                    </figcaption>
                  </figure>
                ))}
                <Button variant="outline" size="sm">
                  + Add example
                </Button>
              </CardContent>
            </Card>
          </div>

          <div className="space-y-3 sm:space-y-4">
            <Card tone="violet">
              <CardHeader>
                <CardTitle className="text-sm flex items-center gap-2">
                  <Target className="h-4 w-4 text-accent-violet" /> Voice sliders
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {sliders.map((s) => (
                  <div key={s.key}>
                    <div className="flex items-center justify-between text-[11px] uppercase tracking-wider text-ink-400">
                      <span>{s.key}</span>
                      <span className="num text-ink-100">{Math.round(s.value * 100)}</span>
                    </div>
                    <div className="score-bar mt-1.5">
                      <span style={{ width: `${s.value * 100}%` }} />
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm flex items-center gap-2">
                  <Slash className="h-4 w-4 text-state-danger" /> Banned phrases
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex flex-wrap gap-1.5">
                  {style.banned_phrases.map((p) => (
                    <span
                      key={p}
                      className="inline-flex items-center gap-1.5 rounded-full border border-state-danger/30 bg-state-danger/10 px-2 py-1 text-[11px] text-state-danger"
                    >
                      <span className="h-1 w-1 rounded-full bg-state-danger" />
                      {p}
                    </span>
                  ))}
                </div>
                <Input placeholder="Add a banned phrase…" />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Target topics</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-1.5">
                  {style.target_topics.map((t) => (
                    <Badge key={t} variant="cyan">
                      {t}
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </PageShell>
    </>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-1 text-[10px] uppercase tracking-[0.18em] text-ink-400">{label}</div>
      {children}
    </div>
  );
}
