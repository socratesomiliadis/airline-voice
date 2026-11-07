"use client";

import { ArrowUpRight, ChartNoAxesCombined, LayoutDashboard, MessagesSquare } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";

const navigation = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/conversations", label: "Conversations", icon: MessagesSquare },
  { href: "/evaluations", label: "Evaluations", icon: ChartNoAxesCombined },
] as const;

export function SidebarNavigation() {
  const pathname = usePathname();
  const { setOpenMobile } = useSidebar();
  return (
    <nav aria-label="Main navigation">
      <SidebarMenu className="gap-1.5">
        {navigation.map(({ href, label, icon: Icon }) => (
          <SidebarMenuItem key={href}>
            <SidebarMenuButton
              isActive={pathname === href}
              render={<Link href={href} />}
              aria-current={pathname === href ? "page" : undefined}
              onClick={() => setOpenMobile(false)}
              className="h-11 gap-3 rounded-md px-3 text-[13px] text-white/60 hover:bg-white/5 hover:text-white data-active:bg-white/10 data-active:text-white"
            >
              <Icon aria-hidden="true" className={pathname === href ? "text-teal-300" : ""} />
              <span>{label}</span>
              {pathname === href && (
                <ArrowUpRight className="ml-auto size-3.5 text-white/40" aria-hidden="true" />
              )}
            </SidebarMenuButton>
          </SidebarMenuItem>
        ))}
      </SidebarMenu>
    </nav>
  );
}
