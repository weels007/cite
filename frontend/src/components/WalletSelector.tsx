"use client"

import { useEffect, useState } from "react"
import { Loader2, Wallet, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { useWallet } from "@/lib/WalletContext"
import { detectWallets, type DetectedWallet } from "@/lib/wallets"

export function WalletSelector({
  onSelect,
  onClose,
}: {
  onSelect: (wallet: DetectedWallet) => void
  onClose: () => void
}) {
  const [wallets, setWallets] = useState<DetectedWallet[]>([])

  useEffect(() => {
    setWallets(detectWallets())
  }, [])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />

      <div className="relative w-full max-w-sm rounded-xl border border-white/10 bg-[#0E131C] p-6 shadow-2xl">
        <button
          onClick={onClose}
          className="absolute right-4 top-4 rounded-md p-1.5 text-slate-500 transition-colors hover:bg-white/5 hover:text-slate-200"
          aria-label="Close"
        >
          <X className="h-4 w-4" />
        </button>

        <h2 className="mb-1 text-base font-semibold text-[#E9E6DF]">Connect a wallet</h2>
        <p className="mb-6 font-mono text-[11px] uppercase tracking-[0.15em] text-slate-500">
          studionet · 61999
        </p>

        {wallets.length === 0 ? (
          <div className="py-8 text-center">
            <Wallet className="mx-auto mb-3 h-8 w-8 text-slate-600" />
            <p className="text-sm text-slate-400">No wallet found</p>
            <p className="mt-1 text-xs text-slate-600">
              Install MetaMask, Rabby or Coinbase Wallet and reload.
            </p>
          </div>
        ) : (
          <ul className="space-y-1.5">
            {wallets.map((wallet) => (
              <li key={wallet.id}>
                <button
                  onClick={() => onSelect(wallet)}
                  className="flex w-full items-center gap-3 rounded-lg border border-white/10 px-4 py-3 text-left transition-colors hover:border-white/20 hover:bg-white/[0.04]"
                >
                  <span className="flex h-7 w-7 items-center justify-center rounded-md border border-white/10 font-mono text-[11px] text-slate-400">
                    {wallet.name.slice(0, 1).toUpperCase()}
                  </span>
                  <span className="text-sm text-slate-200">{wallet.name}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
