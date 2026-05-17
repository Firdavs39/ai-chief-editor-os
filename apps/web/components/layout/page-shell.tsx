import * as React from "react";
import { cn } from "@/lib/utils";

export function PageShell({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex-1 px-3 sm:px-4 lg:px-6 3xl:px-10 pb-12 sm:pb-16 pt-4 sm:pt-6",
        className,
      )}
    >
      <div className="mx-auto w-full max-w-[1280px] 3xl:max-w-[1600px] 4xl:max-w-[2000px] space-y-4 sm:space-y-5 lg:space-y-6 3xl:space-y-8">
        {children}
      </div>
    </div>
  );
}

export function PageSection({
  title,
  description,
  action,
  children,
  className,
}: {
  title?: string;
  description?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("space-y-2.5 sm:space-y-3", className)}>
      {(title || action) && (
        <div className="flex items-end justify-between gap-3 flex-wrap">
          <div className="min-w-0">
            {title && (
              <h2 className="text-[11px] sm:text-[13px] 3xl:text-sm font-medium uppercase tracking-[0.18em] text-ink-400">
                {title}
              </h2>
            )}
            {description && (
              <p className="mt-1 text-xs sm:text-sm text-ink-400">{description}</p>
            )}
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </div>
      )}
      {children}
    </section>
  );
}
