"use client";

import {
  BookOpen,
  FileCode2,
  LayoutDashboard,
  ListChecks,
  MessagesSquare,
  Repeat2,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const navigation = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/conversations", label: "Conversations", icon: MessagesSquare },
  { href: "/evaluations", label: "Evaluations", icon: ListChecks },
  { href: "/changes", label: "Code & prompt changes", icon: FileCode2 },
  { href: "/iterations", label: "Iteration history", icon: Repeat2 },
  { href: "/knowledge", label: "Knowledge base", icon: BookOpen },
] as const;

export function SidebarNavigation() {
  const pathname = usePathname();

  return (
    <nav aria-label="Main navigation" className="flex flex-wrap gap-1 lg:flex-col">
      {navigation.map(({ href, label, icon: Icon }) => {
        const active = pathname === href;

        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 ${
              active
                ? "bg-emerald-50 font-medium text-emerald-800"
                : "text-slate-500 hover:bg-slate-50 hover:text-slate-900"
            }`}
          >
            <Icon aria-hidden="true" className="size-4 shrink-0" />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
