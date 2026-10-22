import Link from "next/link"
import { notFound } from "next/navigation"
import { ArrowLeft, FileSearch, Gauge, Quote, TriangleAlert } from "lucide-react"

import { BetPanel } from "@/components/BetPanel"
import { Badge } from "@/components/ui/badge"
import {
  describeMetric,
  formatBps,
  formatGen,
  formatTimestamp,
  getCitations,
  getMarket,
  getMarketOdds,
} from "@/lib/cite"

// Regenerated every thirty seconds, and served from the cache in between.
export const revalidate = 30

export default async function MarketPage({
  params,
}: {
  params: { id: string }
}) {
  const marketId = Number(params.id)
  if (!Number.isInteger(marketId) || marketId < 0) notFound()

  let market
  let odds
  let trail
  try {
    market = await getMarket(marketId)
    odds = await getMarketOdds(marketId)
    trail = await getCitations(marketId)
  } catch {
    notFound()
  }

  const resolution = market.resolution ? JSON.parse(market.resolution) : null
  const measurement = market.measurement ?? {}
  const event = measurement.event ?? {}
  const consensus = resolution?.consensus ?? null
  const described = describeMetric(market)
  const isMetricMode = market.resolution_mode === "metric"
  const outcomeLabel =
    consensus && typeof consensus.outcome_index === "number"
      ? (market.outcomes?.[consensus.outcome_index] ?? "undetermined")
      : null

  return (
    <div className="mx-auto max-w-7xl px-5 py-12 md:px-8">
      <Link
        href="/markets"
        className="mb-8 inline-flex items-center gap-2 text-sm text-slate-500 transition-colors hover:text-slate-300"
      >
        <ArrowLeft className="h-4 w-4" />
        All markets
      </Link>

      <div className="grid gap-8 lg:grid-cols-[1fr_360px]">
        <div>
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <Badge variant={market.status === "open" ? "open" : "outline"}>
              {market.status}
            </Badge>
            <span className="font-mono text-xs text-slate-600">
              #{market.market_id}
            </span>
          </div>

          <h1 className="mb-4 text-2xl font-bold leading-snug tracking-tight text-white md:text-3xl">
            {market.question}
          </h1>

          <p className="mb-8 max-w-2xl text-sm leading-relaxed text-slate-400">
            {market.criteria}
          </p>

          {/* The number behind the settlement */}
          {consensus && market.status !== "open" && (
            <section className="mb-8">
              <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
                <Gauge className="h-4 w-4 text-[#E0A458]" />
                The number behind the settlement
              </h2>
              <div className="chart-card rounded-2xl p-5">
                <div className="grid gap-5 sm:grid-cols-[auto_1fr] sm:items-start">
                  <div className="sm:w-40">
                    {isMetricMode ? (
                      <>
                        <p className="font-mono text-4xl leading-none text-[#E9E6DF]">
                          {described.value}
                        </p>
                        <p className="mt-2 font-mono text-[10px] uppercase tracking-[0.15em] text-slate-500">
                          {described.unit}
                        </p>
                      </>
                    ) : (
                      <>
                        <p className="font-mono text-3xl leading-none text-[#E9E6DF]">
                          {outcomeLabel ?? "voided"}
                        </p>
                        <p className="mt-2 font-mono text-[10px] uppercase tracking-[0.15em] text-slate-500">
                          the committee&apos;s decision
                        </p>
                      </>
                    )}
                  </div>

                  <div className="space-y-3">
                    <div>
                      {isMetricMode ? (
                        <>
                          <p className="text-sm text-slate-200">
                            {described.label}
                          </p>
                          <p className="mt-1 text-xs text-slate-500">
                            Counted by {described.countedBy}.
                          </p>
                        </>
                      ) : (
                        <>
                          <p className="text-sm text-slate-200">
                            The committee weighed the measured value against the
                            event evidence and chose one side.
                          </p>
                          <p className="mt-1 text-xs text-slate-500">
                            In this mode the number is context, not the result.
                          </p>
                        </>
                      )}
                    </div>

                    <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-3">
                      {(
                        [
                          ["outcome", outcomeLabel],
                          [
                            "confidence",
                            consensus.confidence_band
                              ? consensus.confidence_band
                              : null,
                          ],
                          [
                            "citations",
                            `${consensus.citations_verified ?? 0} verified${
                              consensus.event_citations_verified
                                ? `, ${consensus.event_citations_verified} from the event feed`
                                : ""
                            }`,
                          ],
                        ] as const
                      )
                        .filter(([label, value]) => Boolean(value))
                        .filter(([label]) => isMetricMode || label !== "outcome")
                        .map(([label, value]) => (
                          <div key={label}>
                            <dt className="font-mono text-[10px] uppercase tracking-[0.15em] text-slate-500">
                              {label}
                            </dt>
                            <dd className="mt-1 text-sm text-slate-200">
                              {String(value)}
                            </dd>
                          </div>
                        ))}
                    </dl>

                    {described.countedByContract && (
                      <p className="rounded-lg border border-cyan-400/20 bg-cyan-400/5 p-3 text-xs leading-relaxed text-slate-400">
                        The committee was asked to quote, not to count. The
                        contract fetched the feed, matched every record against
                        the count rules, and produced this number itself. A
                        committee that misreads the feed cannot move the result.
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </section>
          )}

          {/* What is measured */}
          {Object.keys(measurement).length > 0 && (
            <section className="mb-8">
              <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
                <FileSearch className="h-4 w-4 text-cyan-400" />
                The measurement specification
              </h2>
              <dl className="chart-card grid gap-x-6 gap-y-3 rounded-2xl p-5 sm:grid-cols-2">
                {(
                  [
                    ["station", measurement.station],
                    ["variable", measurement.variable],
                    ["unit", measurement.unit],
                    ["day boundary", measurement.day_boundary],
                    ["missing data", measurement.missing_data],
                    ["mode", market.resolution_mode],
                  ] as const
                )
                  .filter(([, value]) => Boolean(value))
                  .map(([label, value]) => (
                    <div key={label}>
                      <dt className="font-mono text-[10px] uppercase tracking-[0.15em] text-slate-500">
                        {label}
                      </dt>
                      <dd className="mt-1 text-sm text-slate-200">{String(value)}</dd>
                    </div>
                  ))}
              </dl>
            </section>
          )}

          {/* The consequence */}
          {Object.keys(event).length > 0 && (
            <section className="mb-8">
              <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
                <TriangleAlert className="h-4 w-4 text-amber-400" />
                The event specification
              </h2>
              <dl className="chart-card grid gap-x-6 gap-y-3 rounded-2xl p-5 sm:grid-cols-2">
                {(
                  [
                    ["publisher", event.publisher],
                    ["area", event.area],
                    ["criteria", event.criteria],
                  ] as const
                )
                  .filter(([, value]) => Boolean(value))
                  .map(([label, value]) => (
                    <div key={label}>
                      <dt className="font-mono text-[10px] uppercase tracking-[0.15em] text-slate-500">
                        {label}
                      </dt>
                      <dd className="mt-1 text-sm text-slate-200">{String(value)}</dd>
                    </div>
                  ))}
              </dl>
            </section>
          )}

            {trail.challenge?.url && (
              <section className="mb-8">
                <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
                  <TriangleAlert className="h-4 w-4 text-amber-400" />
                  The dispute
                  <span className="font-mono text-xs font-normal text-slate-500">
                    {trail.challenge.verdict ? "upheld" : "rejected"}
                  </span>
                </h2>
                <div className="chart-card rounded-lg p-4">
                  <p className="mb-2 font-mono text-[11px] text-amber-400/80">
                    {trail.challenge.url}
                  </p>
                  {trail.challenge.reasoning && (
                    <p className="mb-3 text-sm leading-relaxed text-slate-300">
                      {trail.challenge.reasoning}
                    </p>
                  )}
                  {trail.challenge.citations?.map((citation) => (
                    <blockquote
                      key={citation.quote}
                      className="border-l border-amber-400/40 pl-3 font-mono text-[11px] leading-relaxed text-slate-400"
                    >
                      {citation.quote}
                    </blockquote>
                  ))}
                </div>
              </section>
            )}

            {/* The citation trail */}
          <section className="mb-8">
            <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
              <Quote className="h-4 w-4 text-cyan-400" />
              The citation trail
              <span className="font-mono text-xs font-normal text-slate-500">
                {trail.citations_verified} verified
                {market.event_citations_verified > 0 &&
                  ` · ${market.event_citations_verified} from the event sources`}
              </span>
            </h2>

            {trail.trail.length === 0 ? (
              <p className="rounded-xl border border-dashed border-white/10 p-6 text-center text-sm text-slate-500">
                {market.status === "open"
                  ? "The trail appears once the committee settles the market."
                  : "No citation could be verified, which is why the market was voided."}
              </p>
            ) : (
              <ul className="space-y-3">
                {described.countedByContract && (
                  <li className="rounded-lg border border-cyan-400/20 bg-cyan-400/5 px-4 py-3 text-xs leading-relaxed text-slate-400">
                    These are the records the contract matched against the count
                    rules. Each one is a quote the committee had to pull from the
                    feed, and the count above is the contract&apos;s own tally of
                    them.
                  </li>
                )}
                {trail.trail.map((entry) => (
                  <li key={`${entry.source_index}-${entry.quote}`} className="chart-card rounded-lg p-4">
                    <p className="mb-2 font-mono text-[11px] text-cyan-400/80">
                      SOURCE {entry.source_index} · {entry.url}
                    </p>
                    <p className="font-mono text-xs leading-relaxed text-slate-300">
                      {entry.quote}
                    </p>
                  </li>
                ))}
              </ul>
            )}

            {resolution && (
              <div className="mt-4 space-y-4">
                <div className="rounded-lg border border-white/[0.08] bg-[#0B0F16]/85 p-4">
                  <p className="label-mono mb-2">Agreed by the committee</p>
                  <div className="grid gap-4 sm:grid-cols-3">
                    <div>
                      <p className="label-mono mb-1">Outcome</p>
                      <p className="font-mono text-sm text-slate-200">
                        {resolution.consensus.resolved
                          ? `outcome ${resolution.consensus.outcome_index}`
                          : "not settled"}
                      </p>
                    </div>
                    <div>
                      <p className="label-mono mb-1">Confidence</p>
                      <p className="font-mono text-sm text-slate-200">
                        {resolution.consensus.confidence_band}
                      </p>
                    </div>
                    <div>
                      <p className="label-mono mb-1">Citations</p>
                      <p className="font-mono text-sm text-slate-200">
                        {resolution.consensus.citations_verified} verified
                      </p>
                    </div>
                  </div>
                  {resolution.consensus.undetermined_reason && (
                    <p className="mt-3 text-sm text-amber-300/90">
                      {resolution.consensus.undetermined_reason}
                    </p>
                  )}
                </div>

                <div className="rounded-lg border border-white/[0.08] bg-[#0B0F16]/85 p-4">
                  <p className="label-mono mb-2">The leader&apos;s reading</p>
                  <p className="text-sm leading-relaxed text-slate-400">
                    {resolution.leader_reading.reasoning}
                  </p>
                  <p className="mt-3 text-[11px] leading-relaxed text-slate-600">
                    The committee agreed on the outcome, the confidence band and
                    the number of verified citations. The prose is one
                    reader&apos;s account, kept for the record.
                  </p>
                </div>
              </div>
            )}
          </section>
        </div>

        {/* Side panel */}
        <aside className="space-y-4">
          <BetPanel
            marketId={market.market_id}
            status={market.status}
            outcome={market.outcome}
            outcomes={market.outcomes}
            totalStaked={market.total_staked}
            challengeDeadlineTs={market.challenge_deadline_ts}
          />

          <div className="chart-card rounded-lg p-5">
            <h3 className="mb-4 text-sm font-semibold text-white">The odds</h3>
            <div className="space-y-3">
              {odds.outcomes.map((label, index) => (
                <div key={label}>
                  <div className="mb-1.5 flex items-center justify-between text-xs">
                    <span className="text-slate-300">{label}</span>
                    <span className="font-mono text-slate-200">
                      {formatBps(odds.implied_probability_bps[index] ?? 0)}
                    </span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-white/5">
                    <div
                      className={`h-full rounded-full ${
                        index === 0
                          ? "bg-gradient-to-r from-cyan-400 to-teal-300"
                          : "bg-gradient-to-r from-slate-500 to-slate-400"
                      }`}
                      style={{
                        width: `${(odds.implied_probability_bps[index] ?? 0) / 100}%`,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>

            <dl className="mt-5 space-y-2 border-t border-white/5 pt-4 text-xs">
              <div className="flex justify-between">
                <dt className="text-slate-500">Staked</dt>
                <dd className="font-mono text-slate-300">
                  {formatGen(odds.total_staked)} GEN
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">Closes</dt>
                <dd className="font-mono text-slate-300">
                  {formatTimestamp(market.close_ts)}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">Resolve by</dt>
                <dd className="font-mono text-slate-300">
                  {formatTimestamp(market.resolution_deadline_ts)}
                </dd>
              </div>
              {market.confidence > 0 && (
                <div className="flex justify-between">
                  <dt className="text-slate-500">Confidence</dt>
                  <dd className="font-mono text-slate-300">{market.confidence}%</dd>
                </div>
              )}
              {market.metric_value > 0 && (
                <div className="flex justify-between">
                  <dt className="text-slate-500">Metric</dt>
                  <dd className="font-mono text-slate-300">
                    {market.metric_value}
                  </dd>
                </div>
              )}
            </dl>
          </div>
        </aside>
      </div>
    </div>
  )
}
