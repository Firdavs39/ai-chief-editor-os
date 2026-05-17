import * as React from "react";
import { cn } from "@/lib/utils";

export const Input = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(({ className, type, ...props }, ref) => (
  <input
    type={type}
    ref={ref}
    className={cn(
      "flex h-9 w-full rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-sm text-ink-50 placeholder:text-ink-500 transition-colors focus:outline-none focus:border-accent-violet/40 focus:bg-white/[0.05] disabled:cursor-not-allowed disabled:opacity-50",
      className,
    )}
    {...props}
  />
));
Input.displayName = "Input";

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      "flex w-full rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-sm text-ink-50 placeholder:text-ink-500 transition-colors focus:outline-none focus:border-accent-violet/40 focus:bg-white/[0.05] disabled:cursor-not-allowed disabled:opacity-50",
      className,
    )}
    {...props}
  />
));
Textarea.displayName = "Textarea";
