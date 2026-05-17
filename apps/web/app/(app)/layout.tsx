import * as React from "react";
import { Sidebar } from "@/components/layout/sidebar";
import { MockModePill } from "@/components/feature/mock-mode-pill";
import { ApiConnectionBadge } from "@/components/feature/api-connection-badge";
import { data } from "@/lib/data";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [status, connection] = await Promise.all([data.status(), data.connection()]);
  return (
    <div className="app-shell flex min-h-screen text-ink-100">
      <Sidebar />
      <main className="flex min-h-screen min-w-0 flex-1 flex-col">{children}</main>
      <MockModePill active={status.mock_mode} />
      <div className="fixed bottom-3 left-3 z-40 sm:bottom-5 sm:left-5">
        <ApiConnectionBadge connection={connection} />
      </div>
    </div>
  );
}
