"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Calendar,
  CheckCircle2,
  Compass,
  LayoutDashboard,
  LineChart,
  Radio,
  Settings,
  Sparkles,
  Type,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

export type NavItem = {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string; strokeWidth?: number }>;
  hint?: string;
  group: "primary" | "ops" | "system";
};

export const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Command Center", icon: LayoutDashboard, group: "primary" },
  { href: "/trends", label: "Trend Radar", icon: Radio, group: "primary", hint: "live" },
  { href: "/editor", label: "AI Editor", icon: Sparkles, group: "primary" },
  { href: "/approvals", label: "Approvals", icon: CheckCircle2, group: "ops", hint: "3" },
  { href: "/calendar", label: "Calendar", icon: Calendar, group: "ops" },
  { href: "/sources", label: "Sources", icon: Compass, group: "ops" },
  { href: "/style-dna", label: "Style DNA", icon: Type, group: "system" },
  { href: "/analytics", label: "Analytics", icon: LineChart, group: "system" },
  { href: "/settings", label: "Settings", icon: Settings, group: "system" },
];

const GROUP_LABEL: Record<NavItem["group"], string> = {
  primary: "Workspace",
  ops: "Operations",
  system: "System",
};

export function NavBrand() {
  return (
    <div className="flex items-center gap-2.5 px-2 pb-5">
      <div className="relative grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-accent-violet/25 via-accent-violet/10 to-accent-cyan/15 ring-1 ring-accent-violet/40 3xl:h-10 3xl:w-10">
        <Activity className="h-4 w-4 text-accent-violet 3xl:h-[18px] 3xl:w-[18px]" strokeWidth={2.2} />
        <div className="absolute -inset-px rounded-xl ring-1 ring-inset ring-white/[0.06]" />
      </div>
      <div className="flex flex-col leading-tight">
        <span className="text-[13px] font-semibold tracking-tight text-ink-50 3xl:text-[14px]">
          Chief Editor OS
        </span>
        <span className="text-[10px] uppercase tracking-[0.18em] text-ink-500">Alpha · v0.1</span>
      </div>
    </div>
  );
}

export function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav className="flex-1 space-y-4 overflow-y-auto px-1">
      {(["primary", "ops", "system"] as const).map((group, gi) => (
        <div key={group}>
          <div className="flex items-center gap-2 px-2 pb-1.5 text-[10px] font-medium uppercase tracking-[0.18em] text-ink-500">
            <span>{GROUP_LABEL[group]}</span>
            <div className="dot-row flex-1 opacity-50" />
          </div>
          <div className="space-y-0.5">
            {NAV_ITEMS.filter((n) => n.group === group).map((n) => {
              const active = pathname === n.href || pathname?.startsWith(n.href + "/");
              const Icon = n.icon;
              return (
                <Link
                  key={n.href}
                  href={n.href}
                  onClick={onNavigate}
                  className={cn(
                    "group relative flex items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-sm transition-all 3xl:py-2 3xl:text-[14px]",
                    active
                      ? "bg-white/[0.05] text-ink-50"
                      : "text-ink-300 hover:bg-white/[0.03] hover:text-ink-100",
                  )}
                >
                  {active && (
                    <>
                      <span className="absolute left-0 top-1/2 h-5 w-[2px] -translate-y-1/2 rounded-r-full bg-accent-violet shadow-[0_0_14px_rgba(139,92,246,0.7)]" />
                      <span className="absolute inset-0 rounded-lg ring-1 ring-inset ring-white/[0.06]" />
                    </>
                  )}
                  <Icon
                    className={cn(
                      "h-4 w-4 3xl:h-[17px] 3xl:w-[17px]",
                      active ? "text-accent-violet" : "text-ink-400 group-hover:text-ink-200",
                    )}
                    strokeWidth={active ? 2.2 : 1.8}
                  />
                  <span className="flex-1 leading-tight">{n.label}</span>
                  {n.hint && (
                    <Badge
                      variant={n.hint === "live" ? "cyan" : "violet"}
                      className="px-1.5 py-0 text-[9px]"
                    >
                      {n.hint}
                    </Badge>
                  )}
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </nav>
  );
}

export function NavFooter() {
  return (
    <div className="mt-4 px-1">
      <div className="relative overflow-hidden rounded-xl border border-accent-cyan/20 bg-gradient-to-br from-accent-cyan/[0.08] to-transparent p-3 text-xs leading-relaxed text-ink-300">
        <div className="mb-1.5 flex items-center gap-2 text-ink-50">
          <span className="dot-live shrink-0" />
          <span className="text-[11px] font-semibold tracking-tight">Demo Mode active</span>
        </div>
        <p className="text-[11px] leading-relaxed text-ink-400">
          Внешние API не вызываются. Подключи ключи в{" "}
          <Link href="/settings" className="text-accent-cyan hover:text-accent-cyan/80">
            Settings
          </Link>
          .
        </p>
      </div>
    </div>
  );
}
