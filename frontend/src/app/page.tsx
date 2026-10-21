import { redirect } from "next/navigation"

import { MarketCard } from "@/components/MarketCard"
import ModernBackgroundPaths from "@/components/ui/modern-background-paths"
import { getCitations, getMarket, getMarketCount } from "@/lib/cite"

// Regenerated every thirty seconds, and served from the cache in between.
export const revalidate = 30

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="label-mono mb-1">{label}</p>
      <p className="font-mono text-sm text-slate-200">{value}</p>
    </div>
  )
}

async function loadBoard() {
  try {
    const count = await getMarketCount()
    const markets = await Promise.all(
      Array.from({ length: count }, (_, index) => getMarket(index))
    )
    return { markets, error: null as string | null }
  } catch (error) {
    return { markets: [] as any[], error: (error as Error).message }
  }
}

export default async function Home() {
  const { markets, error } = await loadBoard()

  const open = markets.filter((market) => market.status === "open")
  const settled = markets.filter(
    (market) => market.status === "resolved" || market.status === "settled"
  )

  const featured = open[0]
  const odds = featured
    ? featured.total_staked > 0
      ? {
          yesBps: Math.round((featured.pools[0] / featured.total_staked) * 10000),
          noBps: Math.round((featured.pools[1] / featured.total_staked) * 10000),
        }
      : { yesBps: 5000, noBps: 5000 }
    : { yesBps: 5000, noBps: 5000 }

  const settledWithTrail = settled[0]
  const trail = settledWithTrail ? await getCitations(settledWithTrail.market_id) : null
  const resolution = settledWithTrail?.resolution
    ? JSON.parse(settledWithTrail.resolution)
    : null
  return (
    <>
      <ModernBackgroundPaths
        market={
          featured
            ? {
                city: "Jakarta",
                question: featured.question,
                yesBps: odds.yesBps,
                noBps: odds.noBps,
                closesIn: "live",
                sourceCount:
                  featured.source_urls.length + featured.event_urls.length,
              }
            : undefined
        }
        settlement={
          trail && trail.trail.length > 0
            ? {
                city: "New York",
                outcome: "Yes",
                metric: `${settledWithTrail?.metric_value ?? 0}`,
                quote: trail.trail[0].quote,
                source: trail.trail[0].url,
                publishers: trail.cited_domains,
              }
            : undefined
        }
      />

      {error && (
        <div className="mx-auto max-w-3xl px-5 py-10">
          <div className="rounded-xl border border-amber-400/30 bg-amber-400/5 p-5 text-sm text-amber-200">
            <p className="mb-1 font-medium">The contract is not reachable yet.</p>
            <p className="text-amber-200/70">
              Copy <code className="font-mono">.env.example</code> to{" "}
              <code className="font-mono">.env.local</code> and set{" "}
              <code className="font-mono">NEXT_PUBLIC_CONTRACT_ADDRESS</code>.
              <br />
              <span className="font-mono text-xs opacity-60">{error}</span>
            </p>
          </div>
        </div>
      )}

      <section id="markets" className="mx-auto max-w-7xl px-5 py-16 md:px-8">
        <div className="mb-8 flex items-end justify-between gap-4">
          <div>
            <h2 className="text-2xl font-bold tracking-tight text-white md:text-3xl">
              The board
            </h2>
            <p className="mt-1.5 text-sm text-slate-400">
              Every market locks its station, its variables, its units and its
              publishers before anyone can bet.
            </p>
          </div>
          <span className="font-mono text-xs text-slate-500">
            {markets.length} on chain
          </span>
        </div>

        {markets.length === 0 ? (
          <p className="rounded-xl border border-dashed border-white/10 p-10 text-center text-sm text-slate-500">
            No markets yet. Seed them with{" "}
            <code className="font-mono text-slate-400">
              python scripts/demo_studionet.py
            </code>
            .
          </p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {markets.map((market) => (
              <MarketCard key={market.market_id} market={market} />
            ))}
          </div>
        )}
      </section>

      {resolution && (
        <section className="mx-auto max-w-7xl px-5 pb-20 md:px-8">
          <div className="rounded-lg border border-white/[0.08] bg-[#0B0F16]/85 p-6">
            <div className="mb-4 flex flex-wrap items-center gap-3">
              <p className="label-mono">Agreed by the committee</p>
              <span className="font-mono text-[10px] uppercase tracking-wider text-slate-600">
                {resolution.consensus.confidence_band} confidence ·{" "}
                {resolution.consensus.citations_verified} citations verified
              </span>
            </div>
            <div className="mb-5 grid gap-4 sm:grid-cols-3">
              <Fact
                label="Outcome"
                value={
                  resolution.consensus.resolved
                    ? "settled"
                    : "not settled"
                }
              />
              <Fact
                label="Citations verified"
                value={`${resolution.consensus.citations_verified}`}
              />
              <Fact
                label="Event citations"
                value={`${resolution.consensus.event_citations_verified}`}
              />
            </div>
            {resolution.consensus.undetermined_reason && (
              <p className="mb-5 text-sm text-amber-300/90">
                {resolution.consensus.undetermined_reason}
              </p>
            )}
            <p className="label-mono mb-2">The leader&apos;s reading</p>
            <p className="max-w-3xl text-sm leading-relaxed text-slate-400">
              {resolution.leader_reading.reasoning}
            </p>
            <p className="mt-3 text-[11px] leading-relaxed text-slate-600">
              Only the outcome, the confidence band and the number of verified
              citations are agreed by the committee. The prose above is one
              reader&apos;s account of the evidence, kept for the record.
            </p>
          </div>
        </section>
      )}
    </>
  )
}
