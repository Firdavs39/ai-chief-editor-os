import * as React from "react";
import { Megaphone } from "lucide-react";
import { Topbar } from "@/components/layout/topbar";
import { PageShell } from "@/components/layout/page-shell";
import { Card } from "@/components/ui/card";
import { ChannelsManager } from "@/components/feature/channels/channels-manager";
import { data } from "@/lib/data";
import type { StyleProfile } from "@/lib/types";

function pluralChannels(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return "канал";
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return "канала";
  return "каналов";
}

export default async function ChannelsPage() {
  // Open reads, server-side. Channels load from the live API; sources feed the
  // attach/detach picker; the default style profile drives the style selector
  // (the backend has no list endpoint for profiles, only the default).
  const [channels, sources, styleProfile] = await Promise.all([
    data.channels(),
    data.sources(),
    data.style().catch((): StyleProfile | null => null),
  ]);

  return (
    <>
      <Topbar
        title="Каналы"
        subtitle="Куда публикуем — у каждого канала свой стиль и свои источники"
        pill={{ label: `${channels.length} ${pluralChannels(channels.length)}`, tone: "violet" }}
      />
      <PageShell>
        {/* Context banner — matches the dark-glass canon used elsewhere. */}
        <Card tone="violet" className="overflow-hidden p-4 sm:p-5">
          <div className="flex items-start gap-3 sm:items-center">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-accent-violet/15 ring-1 ring-accent-violet/40 shrink-0">
              <Megaphone className="h-4 w-4 text-accent-violet" strokeWidth={2.2} />
            </div>
            <div className="min-w-0 flex-1 text-sm text-ink-100">
              <div className="font-medium text-ink-50">
                Один сервис — много каналов.
              </div>
              <div className="mt-0.5 text-xs leading-relaxed text-ink-300">
                Каждый канал публикуется в свой Telegram со своим голосом и
                набором источников. Токен бота хранится в защищённом хранилище —
                здесь только публичный ID канала. Публикация всегда требует
                одобрения.
              </div>
            </div>
          </div>
        </Card>

        <ChannelsManager
          initialChannels={channels}
          sources={sources}
          styleProfile={styleProfile}
        />
      </PageShell>
    </>
  );
}
