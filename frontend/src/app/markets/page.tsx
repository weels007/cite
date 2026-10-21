import { MarketCard } from "@/components/MarketCard"
import { getMarket, getMarketCount } from "@/lib/cite"

// Regenerated every thirty seconds, and served from the cache in between.
export const revalidate = 30

export const metadata = { title: "Markets — Cite" }

export default async function MarketsPage() {
  let markets: any[] = []
  let error: string | null = null

  try {
    const count = await getMarketCount()
    markets = await Promise.all(
      Array.from({ length: count }, (_, index) => getMarket(index))
    )
  } catch (caught) {
    error = (caught as Error).message
  }

  const open = markets.filter((market) => market.status === "open")
  const closed = markets.filter((market) => market.status === "closed")
  const settled = markets.filter(
    (market) => market.status === "resolved" || market.status === "settled"
  )
  const voided = markets.filter((market) => market.status === "voided")

  const groups = [
    { title: "Open", hint: "still taking bets", markets: open },
    { title: "Settled", hint: "resolved with a citation trail", markets: settled },
    { title: "Voided", hint: "refunded, because the evidence was not enough", markets: voided },
    { title: "Closed", hint: "betting ended, waiting for the committee", markets: closed },
  ]

  return (
    <div className="mx-auto max-w-7xl px-5 py-12 md:px-8">
      <header className="mb-10">
        <h1 className="text-3xl font-bold tracking-tight text-white md:text-4xl">
          Markets
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-slate-400">
          Each market pins down what is measured, in which unit, over which day,
          and which publisher is allowed to decide. The committee reads the same
          pages and has to agree before anything settles.
        </p>
      </header>

      {error && (
        <p className="rounded-xl border border-amber-400/30 bg-amber-400/5 p-5 text-sm text-amber-200">
          {error}
        </p>
      )}

      {groups.map((group) =>
        group.markets.length === 0 ? null : (
          <section key={group.title} className="mb-12">
            <div className="mb-5 flex items-baseline gap-3">
              <h2 className="text-lg font-semibold text-white">{group.title}</h2>
              <span className="text-xs text-slate-500">{group.hint}</span>
              <span className="ml-auto font-mono text-xs text-slate-600">
                {group.markets.length}
              </span>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {group.markets.map((market) => (
                <MarketCard key={market.market_id} market={market} />
              ))}
            </div>
          </section>
        )
      )}
    </div>
  )
}
