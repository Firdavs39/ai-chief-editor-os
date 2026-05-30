import * as React from "react";
import { Megaphone } from "lucide-react";
import { Toaster } from "sonner";
import { Topbar } from "@/components/layout/topbar";
import { PageShell } from "@/components/layout/page-shell";
import { Card } from "@/components/ui/card";
import { ChannelsManager } from "@/components/feature/channels/channels-manager";
import { data } from "@/lib/data";
import type { StyleProfile } from "@/lib/types";

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
      <Toaster theme="dark" position="top-right" />
      <Topbar
        title="Channels"
        subtitle="Outbound destinations — each with its own style and sources"
        pill={{ label: `${channels.length} channels`, tone: "violet" }}
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
                One deployment, many channels.
              </div>
              <div className="mt-0.5 text-xs leading-relaxed text-ink-300">
                Each channel publishes to its own Telegram destination with its
                own voice and source pool. Bot tokens stay in the vault — only a
                public chat id lives here. Publishing always requires approval.
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
