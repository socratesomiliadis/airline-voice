"use client";

import {
  ChartNoAxesCombined,
  FileCode2,
  LayoutDashboard,
  MessagesSquare,
  Repeat2,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";

const navigation = [
  { href: "/", label: "Live overview", icon: LayoutDashboard },
  { href: "/conversations", label: "Conversations", icon: MessagesSquare },
  { href: "/evaluations", label: "Evaluation scores", icon: ChartNoAxesCombined },
  { href: "/changes", label: "Prompt & code diffs", icon: FileCode2 },
  { href: "/iterations", label: "Iteration history", icon: Repeat2 },
] as const;

export function SidebarNavigation() {
  const pathname = usePathname();
  const { setOpenMobile } = useSidebar();
  return (
    <nav aria-label="Main navigation">
      <SidebarMenu>
        {navigation.map(({ href, label, icon: Icon }) => (
          <SidebarMenuItem key={href}>
            <SidebarMenuButton
              isActive={pathname === href}
              render={<Link href={href} />}
              aria-current={pathname === href ? "page" : undefined}
              onClick={() => setOpenMobile(false)}
              className="h-10 text-xs"
            >
              <Icon aria-hidden="true" />
              <span>{label}</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        ))}
      </SidebarMenu>
    </nav>
  );
}
