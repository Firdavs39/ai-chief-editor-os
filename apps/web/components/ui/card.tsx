import * as React from "react";
import { cn } from "@/lib/utils";

type Tone = "default" | "violet" | "cyan" | "subtle" | "raised";

export const Card = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & { tone?: Tone; interactive?: boolean }
>(({ className, tone = "default", interactive = false, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "relative rounded-2xl",
      tone === "default" && "glass",
      tone === "violet" && "glass-violet",
      tone === "cyan" && "glass-cyan",
      tone === "subtle" && "bg-white/[0.02] border border-white/[0.05]",
      tone === "raised" && "glass-strong",
      interactive && "lift hover:border-white/[0.12] cursor-pointer",
      className,
    )}
    {...props}
  />
));
Card.displayName = "Card";

export const CardHeader = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex flex-col gap-1 px-4 pt-4 sm:px-5 sm:pt-5 3xl:px-6 3xl:pt-6", className)}
    {...props}
  />
));
CardHeader.displayName = "CardHeader";

export const CardTitle = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "text-[14px] sm:text-[15px] 3xl:text-[16px] font-semibold tracking-tight text-ink-50",
      className,
    )}
    {...props}
  />
));
CardTitle.displayName = "CardTitle";

export const CardDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn("text-sm text-ink-400", className)}
    {...props}
  />
));
CardDescription.displayName = "CardDescription";

export const CardContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("px-4 pb-4 pt-2.5 sm:px-5 sm:pb-5 sm:pt-3 3xl:px-6 3xl:pb-6", className)}
    {...props}
  />
));
CardContent.displayName = "CardContent";

export const CardFooter = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex items-center px-4 pb-4 sm:px-5 sm:pb-5 3xl:px-6 3xl:pb-6", className)}
    {...props}
  />
));
CardFooter.displayName = "CardFooter";
