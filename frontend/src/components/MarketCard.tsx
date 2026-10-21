import Link from "next/link"
import { CloudRain, FileSearch, MapPin, Thermometer, TriangleAlert } from "lucide-react"

import { Badge, type BadgeVariant } from "@/components/ui/badge"
import {
  describeMetric,
  formatBps,
  formatGen,
  formatTimestamp,
  type Market,
} from "@/lib/cite"

const STATUS_VARIANT: Record<string, BadgeVariant> = {
  open: "open",
  closed: "outline",
  resolved: "resolved",
  settled: "resolved",
  voided: "void",
}

export function MarketCard({ market }: { market: Market }) {
  const total = market.total_staked
  const yesShare = total > 0 ? (market.pools[0] / total) * 10000 : 0
  const isWeather = market.measurement?.station !== undefined
  const hasEvent = (market.event_urls?.length ?? 0) > 0
  const described = describeMetric(market)
  const settledLabel =
    market.status === "resolved" || market.status === "settled"
      ? (market.outcomes?.[market.outcome] ?? "undetermined")
      : null

  return (
    <Link
      href={`/markets/${market.market_id}`}
      className="chart-card block rounded-lg p-5 focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/60"
    >
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={STATUS_VARIANT[market.status] ?? "default"}>
            {market.status}
          </Badge>
          {market.resolution_mode === "metric" && (
            <Badge variant="outline" className="gap-1">
              <Thermometer className="h-3 w-3" />
              {market.metric_name || "metric"}
            </Badge>
          )}
          {hasEvent && (
            <Badge variant="outline" className="gap-1">
              <TriangleAlert className="h-3 w-3" />
              event
            </Badge>
          )}
        </div>
        <span className="font-mono text-[11px] text-slate-500">
          #{market.market_id}
        </span>
      </div>

      <p className="mb-4 text-sm font-medium leading-snug text-slate-100">
        {market.question}
      </p>

      {settledLabel && (
        <div className="mb-4 flex items-baseline gap-3 rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2">
          {market.resolution_mode === "metric" && (
            <>
              <span className="font-mono text-lg leading-none text-[#E9E6DF]">
                {described.value}
              </span>
              <span className="font-mono text-[10px] uppercase tracking-[0.15em] text-slate-500">
                {described.unit}
              </span>
            </>
          )}
          <span className="text-xs text-slate-400">{settledLabel}</span>
        </div>
      )}

      {total > 0 && (
        <div className="mb-4 space-y-2">
          <div className="flex items-center justify-between text-[11px] text-slate-400">
            <span>Implied probability</span>
            <span className="font-mono">{formatBps(yesShare)}</span>
          </div>
          <div className="flex h-1.5 overflow-hidden rounded-full bg-white/5">
            <div
              className="h-full bg-gradient-to-r from-cyan-400 to-teal-300"
              style={{ width: `${yesShare / 100}%` }}
            />
            <div
              className="h-full bg-gradient-to-r from-slate-500 to-slate-400"
              style={{ width: `${100 - yesShare / 100}%` }}
            />
          </div>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 border-t border-white/5 pt-3 text-[11px] text-slate-500">
        <span className="inline-flex items-center gap-1.5">
          <MapPin className="h-3 w-3" />
          {market.measurement?.station
            ? String(market.measurement.station).slice(0, 42)
            : "—"}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <FileSearch className="h-3 w-3" />
          {market.source_urls.length + market.event_urls.length} sources
        </span>
        <span className="inline-flex items-center gap-1.5">
          <CloudRain className="h-3 w-3" />
          {formatGen(total)} GEN
        </span>
        <span className="ml-auto font-mono">
          {market.status === "open"
            ? `closes ${formatTimestamp(market.close_ts)}`
            : formatTimestamp(market.close_ts)}
        </span>
      </div>
    </Link>
  )
}
