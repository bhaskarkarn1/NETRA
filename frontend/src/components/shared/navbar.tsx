"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { Shield, Search, Network, Swords, LayoutDashboard, BarChart3 } from "lucide-react";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/detect", label: "Detect", icon: Search },
  { href: "/investigate", label: "Investigate", icon: Network },
  { href: "/simulate", label: "Simulate", icon: Swords },
  { href: "/evaluation", label: "Evaluation", icon: BarChart3 },
];

export function Navbar() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-50 border-b border-white/[0.06] bg-[#09090b]/80 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2.5 group">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 shadow-lg shadow-cyan-500/20 transition-shadow group-hover:shadow-cyan-500/40">
            <Shield className="h-5 w-5 text-white" />
          </div>
          <div className="flex flex-col">
            <span className="text-lg font-bold tracking-tight bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">
              NETRA
            </span>
            <span className="text-[10px] font-medium text-gray-500 -mt-1 tracking-widest uppercase">
              नेत्र — The Eye
            </span>
          </div>
        </Link>

        {/* Navigation */}
        <nav className="flex items-center gap-1">
          {NAV_ITEMS.map((item) => {
            const isActive =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);
            const Icon = item.icon;

            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200",
                  isActive
                    ? "bg-white/[0.08] text-cyan-400 shadow-inner shadow-cyan-500/5"
                    : "text-gray-400 hover:text-gray-200 hover:bg-white/[0.04]"
                )}
              >
                <Icon className={cn("h-4 w-4", isActive && "text-cyan-400")} />
                <span className="hidden sm:inline">{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Status indicator */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-3 py-1.5 border border-emerald-500/20">
            <div className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-xs font-medium text-emerald-400">
              Online
            </span>
          </div>
        </div>
      </div>
    </header>
  );
}
