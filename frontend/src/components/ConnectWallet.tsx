"use client"

import { useState } from "react"
import { AlertTriangle, Loader2, LogOut, Wallet } from "lucide-react"

import { Button } from "@/components/ui/button"
import { WalletSelector } from "@/components/WalletSelector"
import { useWallet } from "@/lib/WalletContext"
import { defaultProvider, type DetectedWallet } from "@/lib/wallets"

export function ConnectWallet() {
  const {
    address,
    loading,
    wrongChain,
    available,
    connectWallet,
    disconnectWallet,
  } = useWallet()
  const [busy, setBusy] = useState(false)
  const [picking, setPicking] = useState(false)

  if (loading) {
    return (
      <Button variant="ghost" size="sm" disabled className="gap-2 text-slate-500">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        <span className="hidden sm:inline">Loading</span>
      </Button>
    )
  }

  if (address) {
    return (
      <div className="flex items-center gap-2">
        {wrongChain && (
          <span
            title="This wallet is on the wrong network"
            className="inline-flex items-center gap-1.5 rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-1 font-mono text-[10px] uppercase tracking-wider text-amber-300"
          >
            <AlertTriangle className="h-3 w-3" />
            wrong network
          </span>
        )}
        <span className="hidden rounded-md border border-white/10 bg-white/[0.03] px-2.5 py-1 font-mono text-[11px] text-slate-300 sm:inline">
          {address.slice(0, 6)}…{address.slice(-4)}
        </span>
        <Button
          variant="ghost"
          size="sm"
          onClick={disconnectWallet}
          className="gap-2 text-slate-500 hover:text-slate-300"
        >
          <LogOut className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">Disconnect</span>
        </Button>
      </div>
    )
  }

  return (
    <>
      <Button
        size="sm"
        onClick={async () => {
          // One wallet connects straight away. Several, and the user picks.
          const only = defaultProvider()
          if (only) {
            setBusy(true)
            await connectWallet(only)
            setBusy(false)
            return
          }
          if (available.length > 1) {
            setPicking(true)
            return
          }
          setBusy(true)
          await connectWallet()
          setBusy(false)
        }}
        disabled={busy}
        className="gap-2 rounded-lg border border-white/10 bg-white/[0.04] font-medium text-slate-200 transition-colors hover:border-white/20 hover:bg-white/[0.07]"
      >
        {busy ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <Wallet className="h-3.5 w-3.5" />
        )}
        Connect
      </Button>

      {picking && (
        <WalletSelector
          onClose={() => setPicking(false)}
          onSelect={async (wallet: DetectedWallet) => {
            setPicking(false)
            setBusy(true)
            await connectWallet(wallet)
            setBusy(false)
          }}
        />
      )}
    </>
  )
}
