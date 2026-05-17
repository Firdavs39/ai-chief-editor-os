import * as React from "react";
import { NavBrand, NavFooter, NavLinks } from "./nav-content";

export function Sidebar() {
  return (
    <aside className="hidden lg:flex sticky top-0 h-screen w-[232px] xl:w-[248px] 3xl:w-[280px] shrink-0 flex-col border-r border-white/[0.05] bg-bg-base/45 px-3 py-5 backdrop-blur-xl">
      <NavBrand />
      <NavLinks />
      <NavFooter />
    </aside>
  );
}
