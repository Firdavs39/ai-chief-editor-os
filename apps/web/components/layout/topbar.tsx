import * as React from "react";
import { Search, Sparkles, Bell, Command } from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { MobileNavTrigger } from "./mobile-nav";

type Props = {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
  pill?: { label: string; tone?: "violet" | "cyan" };
};

export function Topbar({ title, subtitle, actions, pill }: Props) {
  return (
    <header className="sticky top-0 z-30 border-b border-white/[0.05] bg-bg-base/75 backdrop-blur-xl">
      <div className="flex h-14 sm:h-[60px] 3xl:h-[68px] items-center gap-2 sm:gap-3 lg:gap-4 px-3 sm:px-4 lg:px-6">
        <MobileNavTrigger />

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 sm:gap-2.5 flex-wrap">
            <span className="dot-live shrink-0 hidden sm:inline-flex" />
            <h1 className="truncate text-[14px] sm:text-[15px] 3xl:text-[17px] font-semibold tracking-tight text-ink-50">
              {title}
            </h1>
            {pill && (
              <Badge variant={pill.tone === "cyan" ? "cyan" : "violet"}>{pill.label}</Badge>
            )}
          </div>
          {subtitle && (
            <p className="truncate text-[11px] sm:text-[12px] text-ink-400 leading-tight mt-0.5 sm:ml-3.5">
              {subtitle}
            </p>
          )}
        </div>

        <div className="hidden xl:flex items-center gap-2 text-xs text-ink-400">
          <div className="group flex h-9 w-[260px] 3xl:w-[340px] items-center gap-2 rounded-xl border border-white/[0.07] bg-white/[0.025] px-3 text-ink-400 transition-colors hover:border-white/[0.12] hover:bg-white/[0.04]">
            <Search className="h-3.5 w-3.5" />
            <span className="flex-1 truncate text-[12px]">
              Search trends, candidates, sources…
            </span>
            <kbd className="hidden 2xl:inline-flex items-center gap-1 rounded border border-white/[0.10] bg-white/[0.04] px-1.5 py-0.5 text-[10px] text-ink-300">
              <Command className="h-3 w-3" /> K
            </kbd>
          </div>
        </div>

        <div className="flex items-center gap-1.5 sm:gap-2">
          <div className="hidden sm:flex items-center gap-2">{actions}</div>
          <button
            className={cn(
              "hidden sm:flex h-9 w-9 items-center justify-center rounded-xl border border-white/[0.07] bg-white/[0.025] text-ink-300 transition-colors",
              "hover:text-ink-100 hover:bg-white/[0.05] hover:border-white/[0.12]",
            )}
            aria-label="Notifications"
          >
            <Bell className="h-4 w-4" strokeWidth={1.8} />
          </button>
          <div className="hidden md:flex h-9 items-center gap-2 rounded-xl border border-white/[0.07] bg-white/[0.025] pl-1.5 pr-3 transition-colors hover:border-white/[0.12]">
            <div className="grid h-6 w-6 place-items-center rounded-md bg-gradient-to-br from-accent-violet to-accent-cyan shadow-glow">
              <Sparkles className="h-3.5 w-3.5 text-bg-base" strokeWidth={2.4} />
            </div>
            <div className="text-xs leading-tight">
              <div className="font-medium text-ink-100">Local user</div>
              <div className="text-[10px] text-ink-400">single-tenant</div>
            </div>
          </div>
          <div className="flex md:hidden h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-accent-violet to-accent-cyan shadow-glow">
            <Sparkles className="h-3.5 w-3.5 text-bg-base" strokeWidth={2.4} />
          </div>
        </div>
      </div>
      {/* hairline divider */}
      <div className="h-px bg-hairline" />
    </header>
  );
}
