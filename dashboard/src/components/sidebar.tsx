"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", label: "Dashboard", icon: "◉" },
  { href: "/inbox", label: "Inbox", icon: "📥" },
  { href: "/tasks", label: "Tasks", icon: "☑" },
  { href: "/approvals", label: "Approvals", icon: "🔐" },
  { href: "/gmail", label: "Gmail Events", icon: "✉" },
  { href: "/linkedin", label: "LinkedIn", icon: "💼" },
  // Gold Tier
  { href: "/xero", label: "Xero", icon: "💰" },
  { href: "/social", label: "Social Media", icon: "📱" },
  { href: "/briefings", label: "CEO Briefings", icon: "📊" },
  { href: "/contacts", label: "Contacts", icon: "👤" },
  { href: "/audit", label: "Audit Logs", icon: "📋" },
  { href: "/settings", label: "Settings", icon: "⚙" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-screen w-64 flex-col border-r bg-muted/40">
      <div className="flex h-14 items-center border-b px-4">
        <h1 className="text-lg font-semibold">AI Employee</h1>
        <span className="ml-2 rounded bg-primary/10 px-2 py-0.5 text-xs text-primary">
          Gold Tier
        </span>
      </div>
      <nav className="flex-1 space-y-1 p-2">
        {navItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
              pathname === item.href
                ? "bg-primary text-primary-foreground"
                : "hover:bg-muted"
            )}
          >
            <span>{item.icon}</span>
            {item.label}
          </Link>
        ))}
      </nav>
      <div className="border-t p-4 text-xs text-muted-foreground">
        Hackathon 0 — Personal AI Employee
      </div>
    </aside>
  );
}
