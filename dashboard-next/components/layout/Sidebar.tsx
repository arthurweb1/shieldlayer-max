// components/layout/Sidebar.tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FileText, LayoutDashboard, Settings, Shield } from "lucide-react";

const NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/audit", label: "Audit Log", icon: FileText },
  { href: "/settings", label: "Settings", icon: Settings },
];

function cn(...classes: (string | boolean | undefined)[]) {
  return classes.filter(Boolean).join(" ");
}

export function Sidebar() {
  const path = usePathname();
  return (
    <aside
      style={{ background: "#0f0f10", borderRight: "1px solid rgba(255,255,255,0.05)" }}
      className="fixed left-0 top-0 h-screen w-16 flex flex-col items-center py-6 gap-6 z-50"
    >
      <Shield className="w-7 h-7 mb-4" style={{ color: "#60a5fa" }} />
      {NAV.map(({ href, label, icon: Icon }) => (
        <Link
          key={href}
          href={href}
          title={label}
          className={cn(
            "p-3 rounded-xl transition-all hover:bg-white/5",
            path === href && "bg-white/10"
          )}
          style={path === href ? { color: "#60a5fa" } : { color: "#71717a" }}
        >
          <Icon className="w-5 h-5" />
        </Link>
      ))}
    </aside>
  );
}
