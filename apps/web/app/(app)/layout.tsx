import * as React from "react";
import { Sidebar } from "@/components/layout/sidebar";
import { MockModePill } from "@/components/feature/mock-mode-pill";
import { ApiConnectionBadge } from "@/components/feature/api-connection-badge";
import { data } from "@/lib/data";
import { OperatorTokenProvider } from "@/lib/operator-auth";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [status, connection] = await Promise.all([data.status(), data.connection()]);
  return (
    // OperatorTokenProvider keeps the X-Admin-Token in React state only.
    // It is mounted here so the "Запустить Quality Brief" button on
    // /editor and /trends shares the same in-memory unlock with the
    // /editor/runs/[id] viewer (no re-typing on client-side navigation).
    // The token is NEVER persisted to localStorage / sessionStorage /
    // cookies / URL — refresh clears it intentionally.
    <OperatorTokenProvider>
      <div className="app-shell flex min-h-screen text-ink-100">
        <Sidebar />
        <main className="flex min-h-screen min-w-0 flex-1 flex-col">{children}</main>
        <MockModePill active={status.mock_mode} />
        <div className="fixed bottom-3 left-3 z-40 sm:bottom-5 sm:left-5">
          <ApiConnectionBadge connection={connection} />
        </div>
      </div>
    </OperatorTokenProvider>
  );
}
