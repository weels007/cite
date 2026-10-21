"use client"

import Link from "next/link"

import { CiteLogo } from "@/components/CiteLogo"
import { ConnectWallet } from "@/components/ConnectWallet"

const NAV = [
  { href: "/", label: "Overview" },
  { href: "/markets", label: "Markets" },
  { href: "/settlements", label: "Settlements" },
]

export function Header() {
  return (
    <header className="sticky top-0 z-40 border-b border-white/[0.07] bg-[#0A0C11]/85 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 md:px-8">
        <div className="flex items-center gap-9">
          <Link href="/" className="flex items-center gap-2.5">
            <CiteLogo size={30} />
            <span className="text-[17px] font-semibold tracking-[-0.02em] text-[#E9E6DF]">
              Cite
            </span>
            <span className="hidden font-mono text-[10px] uppercase tracking-[0.2em] text-slate-600 sm:inline">
              weather markets
            </span>
          </Link>

          <nav className="hidden items-center gap-1 md:flex">
            {NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="rounded-md px-3 py-1.5 text-[13px] text-slate-400 transition-colors hover:bg-white/5 hover:text-[#E9E6DF]"
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>

        <div className="flex items-center gap-3">
          <span className="hidden items-center gap-2 font-mono text-[10px] uppercase tracking-[0.18em] text-slate-600 lg:inline-flex">
            <span className="h-1 w-1 animate-pulse rounded-full bg-emerald-500/70" />
            studionet
          </span>
          <ConnectWallet />
        </div>
      </div>
    </header>
  )
}
