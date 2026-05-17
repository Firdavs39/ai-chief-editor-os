import * as React from "react";
import { Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";

export function EmptyState({
  title,
  description,
  action,
  icon: Icon = Sparkles,
  className,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
  icon?: React.ComponentType<{ className?: string }>;
  className?: string;
}) {
  return (
    <Card className={cn("flex flex-col items-center gap-3 p-10 text-center", className)}>
      <div className="grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br from-accent-violet/20 to-accent-cyan/20 ring-1 ring-white/[0.06]">
        <Icon className="h-5 w-5 text-ink-100" />
      </div>
      <h3 className="text-base font-semibold tracking-tight text-ink-50">{title}</h3>
      {description && <p className="max-w-sm text-sm text-ink-400">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </Card>
  );
}
