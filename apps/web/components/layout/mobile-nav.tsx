"use client";

import * as React from "react";
import { Menu } from "lucide-react";
import { usePathname } from "next/navigation";
import { Sheet, SheetContent, SheetTitle, SheetDescription, SheetTrigger } from "@/components/ui/sheet";
import { NavBrand, NavFooter, NavLinks } from "./nav-content";

export function MobileNavTrigger() {
  const [open, setOpen] = React.useState(false);
  const pathname = usePathname();

  // Close drawer on route change.
  React.useEffect(() => {
    setOpen(false);
  }, [pathname]);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <button
          type="button"
          aria-label="Open navigation"
          className="lg:hidden flex h-9 w-9 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.03] text-ink-200 transition-colors hover:bg-white/[0.06] hover:text-ink-50"
        >
          <Menu className="h-4 w-4" />
        </button>
      </SheetTrigger>
      <SheetContent side="left" className="px-3 py-5">
        <SheetTitle className="sr-only">Navigation</SheetTitle>
        <SheetDescription className="sr-only">
          Quick links across the AI Chief Editor OS dashboard
        </SheetDescription>
        <NavBrand />
        <NavLinks onNavigate={() => setOpen(false)} />
        <NavFooter />
      </SheetContent>
    </Sheet>
  );
}
