"use client";

/**
 * Operator auth — memory-only X-Admin-Token holder for the (app)/ route
 * tree. NEVER persisted to localStorage, sessionStorage, cookies, or URL.
 *
 * - The token lives in React state only. A page reload clears it.
 * - The provider sits in `(app)/layout.tsx` so the runs UI and the
 *   "Generate Quality Brief" button (mounted on /editor and /trends)
 *   share the same in-memory unlock — the operator does not have to
 *   re-enter the token after a client-side route change.
 * - The Vault UI (`components/feature/vault/integrations-vault.tsx`)
 *   keeps its own local state by design; we intentionally do NOT
 *   migrate it in Phase 4 (out of scope per the user's "do not touch
 *   Vault backend" constraint, and the duplicate-unlock cost is small).
 *
 * Safety guarantees enforced by this module:
 * - The token is never logged via `console.log`.
 * - `getAdminHeaders()` returns the header map; callers must not write
 *   the token into a response or render it back to the DOM.
 */

import * as React from "react";

type OperatorTokenContextValue = {
  token: string;
  unlocked: boolean;
  unlock: (next: string) => void;
  lock: () => void;
  getAdminHeaders: () => Record<string, string>;
};

const OperatorTokenContext = React.createContext<OperatorTokenContextValue | null>(
  null,
);

export function OperatorTokenProvider({ children }: { children: React.ReactNode }) {
  // Memory-only state. Refresh wipes it on purpose.
  const [token, setToken] = React.useState<string>("");

  const value = React.useMemo<OperatorTokenContextValue>(
    () => ({
      token,
      unlocked: token.length > 0,
      unlock: (next: string) => setToken(next.trim()),
      lock: () => setToken(""),
      getAdminHeaders: () => {
        const headers: Record<string, string> = {};
        if (token) headers["X-Admin-Token"] = token;
        return headers;
      },
    }),
    [token],
  );

  return (
    <OperatorTokenContext.Provider value={value}>
      {children}
    </OperatorTokenContext.Provider>
  );
}

export function useOperatorToken(): OperatorTokenContextValue {
  const ctx = React.useContext(OperatorTokenContext);
  if (!ctx) {
    throw new Error(
      "useOperatorToken must be called inside <OperatorTokenProvider> " +
        "— check that (app)/layout.tsx wraps the route tree.",
    );
  }
  return ctx;
}
