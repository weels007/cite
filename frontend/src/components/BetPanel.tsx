"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { toast } from "sonner"
import { Loader2, TriangleAlert } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  claim,
  claimRefund,
  confirmPayout,
  gen,
  placeBet,
  resolveMarket,
} from "@/lib/cite"
import { getReadClient } from "@/lib/genlayer-client"
import { useWallet } from "@/lib/WalletContext"

export interface BetPanelProps {
  marketId: number
  status: string
  outcome: number
  outcomes: string[]
  totalStaked: number
  hasPosition?: boolean
}

const AMOUNTS = [1, 10, 100]

export function BetPanel({
  marketId,
  status,
  outcome,
  outcomes,
  totalStaked,
  hasPosition = false,
}: BetPanelProps) {
  const { address, provider, connectWallet } = useWallet()
  const router = useRouter()
  const [amount, setAmount] = useState(10)
  const [busy, setBusy] = useState<string | null>(null)

  async function run(label: string, action: () => Promise<string>) {
    if (!address || !provider) {
      await connectWallet()
      return
    }
    setBusy(label)
    try {
      const hash = await action()
      // The transaction is not finished until the receipt says so. Reporting
      // success before that would be reporting a lie.
      toast.loading(`${label}…`, { id: hash, description: hash.slice(0, 18) + "…" })
      await waitForReceipt(hash)
      toast.success(`${label} confirmed`, { id: hash })
      // The pools and the odds moved, so pull the page again.
      router.refresh()
    } catch (error) {
      toast.error(`${label} failed`, {
        description: (error as Error).message.slice(0, 180),
      })
    } finally {
      setBusy(null)
    }
  }

  async function waitForReceipt(hash: string) {
    const client = getReadClient()
    for (let attempt = 0; attempt < 90; attempt++) {
      try {
        const receipt = await client.getTransactionReceipt(hash as any)
        const status = String(
          (receipt as any)?.status ?? (receipt as any)?.execution_result ?? ""
        )
        if (status && status !== "PENDING" && status !== "PROPOSING") {
          if (status === "ERROR" || status === "REJECTED" || status === "UNDETERMINED") {
            throw new Error(`the network answered ${status}`)
          }
          return receipt
        }
      } catch (error) {
        if ((error as Error).message.includes("answered")) throw error
      }
      await new Promise((resolve) => setTimeout(resolve, 3000))
    }
    throw new Error("the network did not confirm the transaction in time")
  }

  const isOpen = status === "open"
  const isSettled = status === "resolved" || status === "settled"
  const isVoided = status === "voided"

  return (
    <div className="chart-card p-5">
      <h3 className="mb-4 text-sm font-semibold text-white">
        {isOpen ? "Back it" : isSettled ? "Collect" : isVoided ? "Refund" : "Status"}
      </h3>

      {isOpen && (
        <>
          <div className="mb-4 flex gap-2">
            {AMOUNTS.map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => setAmount(value)}
                className={`flex-1 rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
                  amount === value
                    ? "border-cyan-400/40 bg-cyan-400/10 text-cyan-200"
                    : "border-white/10 text-slate-400 hover:border-white/20"
                }`}
              >
                {value} GEN
              </button>
            ))}
          </div>

          <div className="mb-4 space-y-2">
            {outcomes.map((label, index) => (
              <Button
                key={label}
                className="w-full justify-between rounded-lg bg-gradient-to-r from-cyan-500/90 to-teal-400/90 font-semibold text-slate-950 hover:opacity-90"
                disabled={busy !== null}
                onClick={() =>
                  run(`Bet ${label}`, () =>
                    placeBet(
                      address as `0x${string}`,
                      provider,
                      marketId,
                      index,
                      gen(amount)
                    )
                  )
                }
              >
                <span>Bet {label}</span>
                {busy === `Bet ${label}` && (
                  <Loader2 className="h-4 w-4 animate-spin" />
                )}
              </Button>
            ))}
          </div>

          <p className="text-[11px] leading-relaxed text-slate-500">
            Staked so far: {totalStaked} wei. The pool is parimutuel, so the odds
            move with every bet.
          </p>
        </>
      )}

      {isSettled && (
        <>
          <p className="mb-4 text-sm text-slate-400">
            Settled on{" "}
            <span className="font-medium text-white">
              {outcomes[outcome] ?? "—"}
            </span>
            . Claiming pays out your share of the pool, to the wei.
          </p>
          <Button
            className="w-full rounded-lg bg-gradient-to-r from-emerald-500 to-teal-400 font-semibold text-slate-950 hover:opacity-90"
            disabled={busy !== null}
            onClick={() =>
              run("Claim", async () => {
                await claim(address as `0x${string}`, provider, marketId)
                // The payout is only released once the delivery is confirmed.
                return confirmPayout(
                  address as `0x${string}`,
                  provider,
                  marketId,
                  outcome
                )
              })
            }
          >
            {busy === "Claim" ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              "Claim winnings"
            )}
          </Button>
          <p className="mt-2 text-[11px] leading-relaxed text-slate-600">
            The claim reserves your share and sends it. If the transfer does not
            arrive, the obligation stays open and can be claimed again.
          </p>
        </>
      )}

      {isVoided && (
        <>
          <p className="mb-4 flex items-start gap-2 text-sm text-slate-400">
            <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
            The committee could not settle this one, so everybody gets their
            stake back.
          </p>
          <Button
            className="w-full rounded-lg bg-gradient-to-r from-amber-500 to-orange-400 font-semibold text-slate-950 hover:opacity-90"
            disabled={busy !== null}
            onClick={() =>
              run("Refund", () =>
                claimRefund(address as `0x${string}`, provider, marketId)
              )
            }
          >
            {busy === "Refund" ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              "Claim refund"
            )}
          </Button>
        </>
      )}

      {!isOpen && !isSettled && !isVoided && (
        <p className="text-sm text-slate-400">
          Betting has closed. The committee resolves it once the deadline for
          resolution is reached.
        </p>
      )}

      <Button
        variant="ghost"
        size="sm"
        className="mt-4 w-full text-slate-500 hover:text-slate-300"
        disabled={busy !== null}
        onClick={() =>
          run("Resolve", () =>
            resolveMarket(address as `0x${string}`, provider, marketId)
          )
        }
      >
        {busy === "Resolve" ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          "Ask the committee to resolve"
        )}
      </Button>
    </div>
  )
}
