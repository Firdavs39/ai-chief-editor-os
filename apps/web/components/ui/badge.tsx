import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-medium tracking-wide uppercase",
  {
    variants: {
      variant: {
        default:
          "border-white/[0.10] bg-white/[0.04] text-ink-200",
        violet:
          "border-accent-violet/40 bg-accent-violet/15 text-accent-violet",
        cyan:
          "border-accent-cyan/40 bg-accent-cyan/15 text-accent-cyan",
        mint:
          "border-accent-mint/40 bg-accent-mint/15 text-accent-mint",
        amber:
          "border-accent-amber/40 bg-accent-amber/15 text-accent-amber",
        rose:
          "border-accent-rose/40 bg-accent-rose/15 text-accent-rose",
        outline:
          "border-white/[0.12] bg-transparent text-ink-300",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}
