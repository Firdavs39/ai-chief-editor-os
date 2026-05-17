import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-violet/60 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default:
          "bg-accent-violet/90 text-white shadow-glow hover:bg-accent-violet hover:shadow-elev",
        secondary:
          "glass text-ink-100 hover:bg-white/[0.06] hover:border-white/[0.14]",
        ghost:
          "text-ink-200 hover:bg-white/[0.05] hover:text-ink-50",
        outline:
          "border border-white/[0.10] bg-transparent text-ink-100 hover:bg-white/[0.04]",
        destructive:
          "bg-accent-rose/90 text-white hover:bg-accent-rose",
        cyan:
          "bg-accent-cyan/90 text-bg-base shadow-glow-cyan hover:bg-accent-cyan",
      },
      size: {
        default: "h-9 px-4",
        sm: "h-8 px-3 text-xs",
        lg: "h-11 px-6 text-base",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        ref={ref}
        className={cn(buttonVariants({ variant, size, className }))}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
