import Link from "next/link"
import { Quote, ShieldCheck } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { getCitations, getMarket, getMarketCount } from "@/lib/cite"

// Regenerated every thirty seconds, and served from the cache in between.
// The page reads the live chain, so it is rendered per request rather than
// baked into the build, which would spend the RPC budget of a whole minute.
export const revalidate = 30
export const dynamic = "force-dynamic"

export const metadata = { title: "Settlements — Cite" }

export default async function SettlementsPage() {
  let markets: any[] = []
  try {
    const count = await getMarketCount()
    markets = await Promise.all(
      Array.from({ length: count }, (_, index) => getMarket(index))
    )
  } catch {
    markets = []
  }

  const settled = markets.filter(
    (market) => market.status === "resolved" || market.status === "settled"
  )
  const voided = markets.filter((market) => market.status === "voided")

  return (
    <div className="mx-auto max-w-5xl px-5 py-12 md:px-8">
      <header className="mb-10">
        <h1 className="text-3xl font-bold tracking-tight text-white md:text-4xl">
          Settlements
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-slate-400">
          Every settlement the committee reached, with the quotes it relied on.
          The contract checked each of them against the page it points at, so
          the trail can be read by hand.
        </p>
      </header>

      {settled.length === 0 && voided.length === 0 && (
        <p className="rounded-xl border border-dashed border-white/10 p-10 text-center text-sm text-slate-500">
          Nothing has settled yet.
        </p>
      )}

      <div className="space-y-5">
        {settled.map((market) => (
          <SettlementRow key={market.market_id} market={market} />
        ))}
      </div>

      {voided.length > 0 && (
        <>
          <h2 className="mb-4 mt-12 text-lg font-semibold text-white">
            Refused to settle
          </h2>
          <div className="space-y-3">
            {voided.map((market) => (
              <Link
                key={market.market_id}
                href={`/markets/${market.market_id}`}
                className="glass-card block rounded-xl p-4"
              >
                <div className="mb-2 flex items-center gap-2">
                  <Badge variant="void">voided</Badge>
                  <span className="font-mono text-[11px] text-slate-500">
                    #{market.market_id}
                  </span>
                </div>
                <p className="text-sm text-slate-300">{market.question}</p>
                <p className="mt-1.5 text-xs text-slate-500">
                  The evidence was not good enough, so everybody was refunded
                  instead of the market guessing.
                </p>
              </Link>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

async function SettlementRow({ market }: { market: any }) {
  const trail = await getCitations(market.market_id)
  const resolution = market.resolution ? JSON.parse(market.resolution) : null

  return (
    <Link
      href={`/markets/${market.market_id}`}
      className="chart-card block rounded-lg p-5"
    >
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Badge variant="resolved">settled</Badge>
        <span className="font-mono text-[11px] text-slate-500">
          #{market.market_id}
        </span>
        {trail.cited_domains.map((domain: string) => (
          <span
            key={domain}
            className="inline-flex items-center gap-1 rounded-full border border-white/10 px-2 py-0.5 font-mono text-[10px] text-slate-400"
          >
            <ShieldCheck className="h-3 w-3" />
            {domain}
          </span>
        ))}
      </div>

      <p className="mb-3 text-sm font-medium text-slate-100">{market.question}</p>

      {trail.trail.length > 0 && (
        <div className="mb-3 space-y-2">
          {trail.trail.slice(0, 2).map((entry) => (
            <blockquote
              key={`${entry.source_index}-${entry.quote}`}
              className="flex gap-2 rounded-lg border-l-2 border-cyan-400/40 bg-white/[0.02] py-1.5 pl-3"
            >
              <Quote className="mt-0.5 h-3 w-3 shrink-0 text-cyan-400/70" />
              <p className="font-mono text-[11px] leading-relaxed text-slate-400">
                {entry.quote.length > 220
                  ? `${entry.quote.slice(0, 220)}…`
                  : entry.quote}
              </p>
            </blockquote>
          ))}
        </div>
      )}

      {resolution?.leader_reading?.reasoning && (
        <p className="text-xs leading-relaxed text-slate-500">
          {resolution.leader_reading.reasoning.length > 240
            ? `${resolution.leader_reading.reasoning.slice(0, 240)}…`
            : resolution.leader_reading.reasoning}
        </p>
      )}
    </Link>
  )
}
