/**
 * A typed view of the Cite contract.
 *
 * Every function here maps one to one onto a public method of
 * contracts/cite.py. The shapes are the ones the contract returns.
 */

import { cached, invalidate } from "@/lib/cache"
import { getContractAddress, getReadClient, getWriteClient } from "@/lib/genlayer-client"

export type MarketStatus = "open" | "closed" | "resolved" | "settled" | "voided"

export interface Market {
  market_id: number
  creator: string
  question: string
  criteria: string
  outcomes: string[]
  source_urls: string[]
  allowed_domains: string[]
  close_ts: number
  resolution_deadline_ts: number
  challenge_deadline_ts: number
  status: MarketStatus
  outcome: number
  confidence: number
  resolution: string
  resolved_at: string
  pools: number[]
  total_staked: number
  paid_out: number
  refunded: number
  fee_wei: number
  challenge_count: number
  swept: boolean
  resolution_mode: string
  comparator: string
  threshold: number
  metric_name: string
  metric_value: number
  window_start_ts: number
  window_end_ts: number
  require_citation: boolean
  citations_verified: number
  cited_domains: string[]
  measurement: Record<string, any>
  event_urls: string[]
  event_domains: string[]
  event_citations_verified: number
}

export interface MarketOdds {
  market_id: number
  status: MarketStatus
  outcomes: string[]
  pools: number[]
  total_staked: number
  implied_probability_bps: number[]
  odds_bps: number[]
}

export interface Citation {
  source_index: number
  url: string
  quote: string
}

export interface CitationTrail {
  market_id: number
  status: MarketStatus
  citations_verified: number
  cited_domains: string[]
  trail: Citation[]
  challenge: {
    url: string
    verdict: boolean
    reasoning: string
    citations: Citation[]
  }
}

export interface Accounting {
  total_staked_all: number
  paid_out_all: number
  refunded_all: number
  bonds_received_all: number
  bonds_returned_all: number
  fees_collected: number
  fees_withdrawn_all: number
  fees_from_pools: number
  owed_all: number
  in_flight_all: number
  failed_transfers: number
  swept_stranded: number
  bettor_owed: number
  protocol_owned: number
  stranded: number
  obligations: number
  expected_balance: number
  contract_balance: number
  covered: boolean
  reconciled: boolean
  invariant_holds: boolean
  market_count: number
}

/** What the committee actually agreed on. */
export interface Consensus {
  resolved: boolean
  outcome_index: number
  confidence_band: string
  citations_verified: number
  event_citations_verified: number
  metric_tolerance: number | null
  undetermined_reason: string
}

/** What one reader said. Not consensus bound. */
export interface LeaderReading {
  metric: number
  confidence: number
  reasoning: string
  citations: Citation[]
  cited_domains: string[]
  cited_primary_source: boolean
  verified_sources: number
  verified_domains: number
  single_publisher: boolean
}

export interface Resolution {
  consensus: Consensus
  leader_reading: LeaderReading
}

export interface PendingPayout {
  market_id: number
  bettor: string
  outcome: number
  owed: number
  delivered: boolean
}

function address() {
  const contract = getContractAddress()
  if (!contract) {
    throw new Error(
      "NEXT_PUBLIC_CONTRACT_ADDRESS is not set. Copy .env.example to .env.local."
    )
  }
  return contract
}

/** The contract returns uint256 values, which arrive as bigints. */
function number(value: unknown): number {
  if (typeof value === "bigint") return Number(value)
  if (typeof value === "string") return Number(value)
  return Number(value ?? 0)
}

function normalizeMarket(raw: any): Market {
  return {
    ...raw,
    market_id: number(raw.market_id),
    close_ts: number(raw.close_ts),
    resolution_deadline_ts: number(raw.resolution_deadline_ts),
    challenge_deadline_ts: number(raw.challenge_deadline_ts),
    outcome: number(raw.outcome),
    confidence: number(raw.confidence),
    pools: (raw.pools ?? []).map(number),
    total_staked: number(raw.total_staked),
    paid_out: number(raw.paid_out),
    refunded: number(raw.refunded),
    fee_wei: number(raw.fee_wei),
    challenge_count: number(raw.challenge_count),
    threshold: number(raw.threshold),
    metric_value: number(raw.metric_value),
    window_start_ts: number(raw.window_start_ts),
    window_end_ts: number(raw.window_end_ts),
    citations_verified: number(raw.citations_verified),
    event_citations_verified: number(raw.event_citations_verified),
  }
}

export async function getMarketCount(): Promise<number> {
  return cached("marketCount", 20_000, async () => {
    const value = await getReadClient().readContract({
      address: address(),
      functionName: "get_market_count",
    })
    return Number(value)
  })
}

export async function getMarket(marketId: number): Promise<Market> {
  return cached(`market:${marketId}`, 20_000, async () => {
    const value = await getReadClient().readContract({
      address: address(),
      functionName: "get_market",
      args: [marketId],
    })
    return normalizeMarket(value)
  })
}

export async function getMarketOdds(marketId: number): Promise<MarketOdds> {
  return cached(`odds:${marketId}`, 20_000, async () => {
    const value = await getReadClient().readContract({
      address: address(),
      functionName: "get_market_odds",
      args: [marketId],
    })
    return {
      ...(value as unknown as MarketOdds),
      market_id: number((value as any).market_id),
      pools: ((value as any).pools ?? []).map(number),
      total_staked: number((value as any).total_staked),
      implied_probability_bps: ((value as any).implied_probability_bps ?? []).map(number),
      odds_bps: ((value as any).odds_bps ?? []).map(number),
    }
  })
}

export async function getCitations(marketId: number): Promise<CitationTrail> {
  return cached(`citations:${marketId}`, 20_000, async () => {
    const value = await getReadClient().readContract({
      address: address(),
      functionName: "get_citations",
      args: [marketId],
    })
    return {
      ...(value as unknown as CitationTrail),
      market_id: number((value as any).market_id),
      citations_verified: number((value as any).citations_verified),
      trail: ((value as any).trail ?? []).map((entry: any) => ({
        source_index: number(entry.source_index),
        url: entry.url ?? "",
        quote: entry.quote ?? "",
      })),
    }
  })
}

export async function getAccounting(): Promise<Accounting> {
  return cached("accounting", 20_000, async () => {
    const value = await getReadClient().readContract({
      address: address(),
      functionName: "get_accounting",
    })
    const raw = value as any
    return {
      ...raw,
      total_staked_all: number(raw.total_staked_all),
      paid_out_all: number(raw.paid_out_all),
      refunded_all: number(raw.refunded_all),
      bonds_received_all: number(raw.bonds_received_all),
      bonds_returned_all: number(raw.bonds_returned_all),
      fees_collected: number(raw.fees_collected),
      fees_withdrawn_all: number(raw.fees_withdrawn_all),
      fees_from_pools: number(raw.fees_from_pools),
      owed_all: number(raw.owed_all),
      in_flight_all: number(raw.in_flight_all),
      failed_transfers: number(raw.failed_transfers),
      swept_stranded: number(raw.swept_stranded),
      bettor_owed: number(raw.bettor_owed),
      protocol_owned: number(raw.protocol_owned),
      stranded: number(raw.stranded),
      obligations: number(raw.obligations),
      expected_balance: number(raw.expected_balance),
      contract_balance: number(raw.contract_balance),
      covered: Boolean(raw.covered),
      reconciled: Boolean(raw.reconciled),
      invariant_holds: Boolean(raw.invariant_holds),
      market_count: number(raw.market_count),
    }
  })
}

export async function placeBet(
  walletAddress: `0x${string}`,
  provider: any,
  marketId: number,
  outcome: number,
  amountWei: bigint
): Promise<string> {
  const client = getWriteClient(walletAddress, provider)
  const hash = await client.writeContract({
    address: address(),
    functionName: "place_bet",
    args: [marketId, outcome],
    value: amountWei,
  })
  invalidate()
  return hash
}

export async function confirmPayout(
  walletAddress: `0x${string}`,
  provider: any,
  marketId: number,
  outcome: number
): Promise<string> {
  const client = getWriteClient(walletAddress, provider)
  const hash = await client.writeContract({
    address: address(),
    functionName: "confirm_payout",
    args: [marketId, outcome],
    value: 0n,
  })
  invalidate()
  return hash
}

export async function getPendingPayouts(): Promise<PendingPayout[]> {
  const value = await getReadClient().readContract({
    address: address(),
    functionName: "get_pending_payouts",
  })
  const raw = value as any
  return (raw?.pending ?? []).map((entry: any) => ({
    market_id: number(entry.market_id),
    bettor: entry.bettor ?? "",
    outcome: number(entry.outcome),
    owed: number(entry.owed),
    delivered: Boolean(entry.delivered),
  }))
}

export async function claim(
  walletAddress: `0x${string}`,
  provider: any,
  marketId: number
): Promise<string> {
  const client = getWriteClient(walletAddress, provider)
  const hash = await client.writeContract({
    address: address(),
    functionName: "claim",
    args: [marketId],
    value: 0n,
  })
  invalidate()
  return hash
}

export async function claimRefund(
  walletAddress: `0x${string}`,
  provider: any,
  marketId: number
): Promise<string> {
  const client = getWriteClient(walletAddress, provider)
  const hash = await client.writeContract({
    address: address(),
    functionName: "claim_refund",
    args: [marketId],
    value: 0n,
  })
  invalidate()
  return hash
}

export async function resolveMarket(
  walletAddress: `0x${string}`,
  provider: any,
  marketId: number
): Promise<string> {
  const client = getWriteClient(walletAddress, provider)
  const hash = await client.writeContract({
    address: address(),
    functionName: "resolve_market",
    args: [marketId],
    value: 0n,
  })
  invalidate()
  return hash
}

export async function challenge(
  walletAddress: `0x${string}`,
  provider: any,
  marketId: number,
  evidenceUrl: string
): Promise<string> {
  const client = getWriteClient(walletAddress, provider)
  const hash = await client.writeContract({
    address: address(),
    functionName: "challenge_market",
    args: [marketId, evidenceUrl],
    value: gen(0.1),
  })
  invalidate()
  return hash
}

/** The GEN amount, as the contract counts it. */
/** How the number behind a settlement was arrived at. */
export function describeMetric(market: Market) {
  const measurement = (market.measurement ?? {}) as Record<string, any>
  const event = (measurement.event ?? {}) as Record<string, any>
  const rules = event.count_rules
  const countedByContract =
    Boolean(rules) && typeof rules === "object" && Object.keys(rules).length > 0

  const scale =
    typeof measurement.scale === "number" && measurement.scale > 0
      ? measurement.scale
      : 1
  const unit = typeof measurement.unit === "string" ? measurement.unit : ""
  const isCount = unit === "count"
  const raw = market.metric_value
  const shown = isCount ? String(raw) : (raw / scale).toFixed(1)

  return {
    value: shown,
    unit: isCount ? "records" : unit,
    label: market.metric_name || "the measured value",
    isCount,
    countedByContract,
    countedBy: countedByContract
      ? "the contract, counting the feed itself"
      : market.event_citations_verified > 0
        ? "the committee, from the event feed"
        : "the committee, from the authoritative source",
  }
}

export function gen(value: number): bigint {
  return BigInt(Math.round(value * 1e18))
}

export function formatGen(wei: number | bigint | string): string {
  const amount = typeof wei === "bigint" ? wei : BigInt(Math.round(Number(wei)))
  const whole = amount / 10n ** 18n
  const fraction = (amount % 10n ** 18n).toString().padStart(18, "0").slice(0, 2)
  return `${whole.toString()}.${fraction}`
}

export function formatBps(bps: number): string {
  return `${(bps / 100).toFixed(1)}%`
}

export function formatTimestamp(seconds: number): string {
  if (!seconds) return "—"
  return new Date(seconds * 1000).toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  })
}
