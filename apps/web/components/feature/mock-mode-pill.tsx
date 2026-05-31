import * as React from "react";
import { cn } from "@/lib/utils";

export function MockModePill({ active = true }: { active?: boolean }) {
  if (!active) return null;
  return (
    <div className="fixed bottom-5 right-5 z-40 hidden sm:block">
      <div className={cn(
        "flex items-center gap-1.5 sm:gap-2 rounded-full border border-accent-cyan/30 bg-bg-base/80 px-2.5 py-1 sm:px-3 sm:py-1.5 backdrop-blur-md",
        "shadow-glow-cyan",
      )}>
        <span className="relative flex h-1.5 w-1.5 sm:h-2 sm:w-2">
          <span className="absolute inset-0 animate-ping rounded-full bg-accent-cyan/60" />
          <span className="relative h-1.5 w-1.5 sm:h-2 sm:w-2 rounded-full bg-accent-cyan" />
        </span>
        <span className="text-[10px] sm:text-[11px] font-medium uppercase tracking-[0.18em] text-accent-cyan">
          <span className="sm:hidden">Демо</span>
          <span className="hidden sm:inline">Демо-режим</span>
        </span>
      </div>
    </div>
  );
}
