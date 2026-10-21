"use client"

import { useEffect, useMemo, useState, type ReactNode } from "react"
import { AnimatePresence, motion, useReducedMotion } from "framer-motion"
import { ArrowRight, FileSearch, Quote } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

/**
 * The backdrop of Cite, drawn as a printed weather chart.
 *
 * The reference is not a screensaver, it is the synoptic chart a weather
 * bureau prints: a fixed graticule, hairline isobars, station plots, one
 * accent colour for the data. Everything is a stroke, nothing is a glow, and
 * every path is generated from a fixed seed so the server and the browser draw
 * the same picture.
 */

export type BackgroundPattern = "synoptic" | "radar" | "stations" | "wind"

const PATTERNS: { id: BackgroundPattern; label: string; note: string }[] = [
  { id: "synoptic", label: "Synoptic", note: "the locked measurement" },
  { id: "radar", label: "Radar", note: "the field the committee reads" },
  { id: "stations", label: "Stations", note: "the validators that must agree" },
  { id: "wind", label: "Wind", note: "how the evidence moves" },
]

/** A deterministic PRNG, so the drawing never changes between renders. */
function seeded(seed: number) {
  let state = seed >>> 0
  return () => {
    state = (state + 0x6d2b79f5) >>> 0
    let t = state
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const W = 1000
const H = 620

// ---------------------------------------------------------------------------
// The fixed graticule, the same under every pattern
// ---------------------------------------------------------------------------

function Graticule() {
  const lines = useMemo(() => {
    const verticals = []
    for (let x = 0; x <= W; x += 50) verticals.push(x)
    const horizontals = []
    for (let y = 0; y <= H; y += 50) horizontals.push(y)
    return { verticals, horizontals }
  }, [])

  return (
    <g>
      {lines.verticals.map((x) => (
        <line
          key={`v${x}`}
          x1={x}
          y1={0}
          x2={x}
          y2={H}
          stroke="currentColor"
          strokeWidth={x % 200 === 0 ? 0.9 : 0.4}
          strokeOpacity={x % 200 === 0 ? 0.16 : 0.08}
        />
      ))}
      {lines.horizontals.map((y) => (
        <line
          key={`h${y}`}
          x1={0}
          y1={y}
          x2={W}
          y2={y}
          stroke="currentColor"
          strokeWidth={y % 200 === 0 ? 0.9 : 0.4}
          strokeOpacity={y % 200 === 0 ? 0.16 : 0.08}
        />
      ))}
    </g>
  )
}

// ---------------------------------------------------------------------------
// Synoptic chart: nested isobars and a cold front
// ---------------------------------------------------------------------------

function SynopticPattern({ reduced }: { reduced: boolean }) {
  const isobars = useMemo(() => {
    const random = seeded(1012)
    return Array.from({ length: 7 }, (_, index) => {
      const points: string[] = []
      const baseY = 120 + index * 62
      const amplitude = 30 + random() * 26
      const phase = random() * 6.28
      for (let x = -40; x <= W + 40; x += 40) {
        const y =
          baseY +
          Math.sin(x / 190 + phase) * amplitude +
          Math.sin(x / 71 + phase * 2) * 7
        points.push(`${x},${y.toFixed(1)}`)
      }
      return {
        id: `isobar-${index}`,
        d: `M${points.join(" L")}`,
        delay: index * 0.5,
        label: `${1012 + index * 4}`,
      }
    })
  }, [])

  const front = useMemo(() => {
    const points: string[] = []
    for (let x = 0; x <= W; x += 36) {
      const y = 470 + Math.sin(x / 130) * 34
      points.push(`${x},${y.toFixed(1)}`)
    }
    return points
  }, [])

  return (
    <g>
      {isobars.map((line) => (
        <g key={line.id}>
          <motion.path
            d={line.d}
            fill="none"
            stroke="currentColor"
            strokeWidth="1"
            strokeLinecap="round"
            initial={{ pathLength: 0, opacity: 0 }}
            animate={{ pathLength: 1, opacity: 0.42 }}
            transition={{
              pathLength: { duration: 3.2, delay: line.delay, ease: "easeInOut" },
              opacity: { duration: 1.2, delay: line.delay },
            }}
          />
          <text
            x={62 + (line.label.charCodeAt(2) % 5) * 120}
            y={Number(line.d.split(" L")[1]?.split(",")[1] ?? 120)}
            fill="currentColor"
            fillOpacity="0.5"
            fontSize="11"
            fontFamily="ui-monospace, monospace"
            letterSpacing="1"
          >
            {line.label}
          </text>
        </g>
      ))}

      {/* A cold front: a line with triangles on it */}
      <motion.path
        d={`M${front.join(" L")}`}
        fill="none"
        stroke="#E0A458"
        strokeWidth="1.6"
        strokeOpacity="0.7"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 3, ease: "easeInOut" }}
      />
      {front.slice(1, 9).map((point, index) => {
        const [x, y] = point.split(",").map(Number)
        return (
          <motion.polygon
            key={index}
            points={`${x},${y} ${x - 9},${y + 15} ${x + 9},${y + 15}`}
            fill="#E0A458"
            fillOpacity="0.7"
            initial={{ opacity: 0 }}
            animate={{ opacity: reduced ? 0.7 : [0.7, 0.35, 0.7] }}
            transition={{
              duration: 4,
              delay: index * 0.2,
              repeat: reduced ? 0 : Infinity,
              ease: "easeInOut",
            }}
          />
        )
      })}
    </g>
  )
}

// ---------------------------------------------------------------------------
// Radar: range rings, a sweep, and outlined cells
// ---------------------------------------------------------------------------

function RadarPattern({ reduced }: { reduced: boolean }) {
  const rings = [70, 140, 210, 280]

  const cells = useMemo(() => {
    const random = seeded(2026)
    return Array.from({ length: 18 }, (_, index) => {
      const angle = random() * Math.PI * 2
      const distance = 50 + random() * 220
      const cx = W / 2 + Math.cos(angle) * distance
      const cy = H / 2 + Math.sin(angle) * distance * 0.66
      const r = 16 + random() * 38
      const points = Array.from({ length: 9 }, (_, i) => {
        const a = (i / 9) * Math.PI * 2
        const rr = r * (0.72 + random() * 0.42)
        return `${(cx + Math.cos(a) * rr).toFixed(1)},${(cy + Math.sin(a) * rr * 0.8).toFixed(1)}`
      })
      return {
        id: `cell-${index}`,
        d: `M${points.join(" L")} Z`,
        delay: random() * 7,
        opacity: 0.14 + random() * 0.2,
      }
    })
  }, [])

  return (
    <g>
      {rings.map((radius) => (
        <circle
          key={radius}
          cx={W / 2}
          cy={H / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth="0.7"
          strokeOpacity="0.2"
        />
      ))}

      {cells.map((cell) => (
        <motion.path
          key={cell.id}
          d={cell.d}
          fill="none"
          stroke="#E0A458"
          strokeWidth="0.9"
          strokeOpacity={cell.opacity}
          initial={{ opacity: 0 }}
          animate={{ opacity: reduced ? cell.opacity : [cell.opacity, cell.opacity * 2.4, cell.opacity] }}
          transition={{
            duration: 6,
            delay: cell.delay,
            repeat: reduced ? 0 : Infinity,
            ease: "easeInOut",
          }}
        />
      ))}

      <motion.g
        style={{ originX: `${W / 2}px`, originY: `${H / 2}px` }}
        animate={{ rotate: reduced ? 0 : 360 }}
        transition={{ duration: 11, repeat: reduced ? 0 : Infinity, ease: "linear" }}
      >
        <line
          x1={W / 2}
          y1={H / 2}
          x2={W / 2 + 290}
          y2={H / 2}
          stroke="#E0A458"
          strokeWidth="1"
          strokeOpacity="0.55"
        />
      </motion.g>
      <circle cx={W / 2} cy={H / 2} r="2.5" fill="#E0A458" fillOpacity="0.8" />
    </g>
  )
}

// ---------------------------------------------------------------------------
// Stations: the committee, drawn as a synoptic station network
// ---------------------------------------------------------------------------

function StationsPattern({ reduced }: { reduced: boolean }) {
  const network = useMemo(() => {
    const random = seeded(974)
    const stations = Array.from({ length: 38 }, (_, index) => ({
      id: `st-${index}`,
      x: 40 + random() * (W - 80),
      y: 40 + random() * (H - 80),
      wind: random() * 360,
      strength: 2 + random() * 7,
    }))
    const links: { id: string; d: string; delay: number }[] = []
    stations.forEach((a, i) => {
      stations.forEach((b, j) => {
        if (i === j) return
        if (Math.hypot(a.x - b.x, a.y - b.y) < 165 && random() > 0.62) {
          links.push({
            id: `lk-${i}-${j}`,
            d: `M${a.x},${a.y} L${b.x},${b.y}`,
            delay: random() * 9,
          })
        }
      })
    })
    return { stations, links }
  }, [])

  return (
    <g>
      {network.links.map((link) => (
        <motion.path
          key={link.id}
          d={link.d}
          stroke="currentColor"
          strokeWidth="0.4"
          strokeOpacity="0.24"
          fill="none"
          initial={{ pathLength: 0, opacity: 0 }}
          animate={{ pathLength: [0, 1], opacity: [0, 0.45, 0] }}
          transition={{
            duration: 8,
            delay: link.delay,
            repeat: reduced ? 0 : Infinity,
            ease: "easeInOut",
          }}
        />
      ))}

      {network.stations.map((station) => (
        <g key={station.id}>
          <circle
            cx={station.x}
            cy={station.y}
            r="3.2"
            fill="none"
            stroke="currentColor"
            strokeWidth="0.8"
            strokeOpacity="0.55"
          />
          <line
            x1={station.x}
            y1={station.y}
            x2={station.x + station.strength}
            y2={station.y}
            stroke="#E0A458"
            strokeWidth="0.9"
            strokeOpacity="0.7"
            transform={`rotate(${station.wind} ${station.x} ${station.y})`}
          />
        </g>
      ))}
    </g>
  )
}

// ---------------------------------------------------------------------------
// Wind: streamlines with a barb
// ---------------------------------------------------------------------------

function WindPattern({ reduced }: { reduced: boolean }) {
  const streams = useMemo(
    () =>
      Array.from({ length: 14 }, (_, index) => {
        const y = 60 + index * 40
        const amplitude = 16 + (index % 5) * 7
        const points: string[] = []
        for (let x = -60; x <= W + 60; x += 50) {
          points.push(`${x},${(y + Math.sin(x / 130 + index) * amplitude).toFixed(1)}`)
        }
        return {
          id: `strm-${index}`,
          d: `M${points.join(" L")}`,
          delay: index * 0.45,
          opacity: 0.16 + (index % 4) * 0.06,
        }
      }),
    []
  )

  return (
    <g>
      {streams.map((stream) => (
        <motion.path
          key={stream.id}
          d={stream.d}
          fill="none"
          stroke="currentColor"
          strokeWidth="0.8"
          strokeLinecap="round"
          initial={{ pathLength: 0, opacity: 0 }}
          animate={{ pathLength: [0, 1], opacity: [0, stream.opacity, 0] }}
          transition={{
            duration: 12,
            delay: stream.delay,
            repeat: reduced ? 0 : Infinity,
            ease: "easeInOut",
          }}
        />
      ))}
    </g>
  )
}

// ---------------------------------------------------------------------------
// The cards, drawn as chart annotations
// ---------------------------------------------------------------------------

export interface MarketPreview {
  city: string
  question: string
  yesBps: number
  noBps: number
  closesIn: string
  sourceCount: number
}

export interface SettlementPreview {
  city: string
  outcome: string
  metric: string
  quote: string
  source: string
  publishers: string[]
}

function ChartCard({
  label,
  children,
  className,
}: {
  label: string
  children: ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        "relative rounded-lg border border-white/[0.08] bg-[#0B0F16]/85 p-5 backdrop-blur-md",
        className
      )}
    >
      <span className="absolute left-0 top-0 h-px w-10 bg-[#E0A458]/70" />
      <p className="mb-4 font-mono text-[10px] uppercase tracking-[0.22em] text-slate-500">
        {label}
      </p>
      {children}
    </div>
  )
}

function MarketCard({ market }: { market: MarketPreview }) {
  return (
    <ChartCard label="Live market">
      <div className="mb-3 flex items-center justify-between gap-3">
        <span className="font-mono text-[11px] text-slate-400">{market.city}</span>
        <span className="font-mono text-[10px] uppercase tracking-wider text-slate-600">
          closes {market.closesIn}
        </span>
      </div>

      <p className="mb-4 text-sm font-medium leading-snug text-[#E9E6DF]">
        {market.question}
      </p>

      <div className="space-y-2.5">
        {(
          [
            ["Yes", market.yesBps],
            ["No", market.noBps],
          ] as const
        ).map(([label, bps]) => (
          <div key={label} className="flex items-center gap-3">
            <span className="w-7 font-mono text-[11px] text-slate-500">{label}</span>
            <div className="h-px flex-1 bg-white/10">
              <motion.div
                className={cn(
                  "h-px",
                  label === "Yes" ? "bg-[#E0A458]" : "bg-slate-600"
                )}
                initial={{ width: 0 }}
                animate={{ width: `${Math.max(2, Math.min(100, bps / 100))}%` }}
                transition={{ duration: 1, delay: 0.3, ease: "easeOut" }}
              />
            </div>
            <span className="w-12 text-right font-mono text-[11px] text-slate-300">
              {(bps / 100).toFixed(1)}%
            </span>
          </div>
        ))}
      </div>

      <p className="mt-4 flex items-center gap-2 border-t border-white/[0.06] pt-3 font-mono text-[10px] uppercase tracking-wider text-slate-600">
        <FileSearch className="h-3 w-3" />
        {market.sourceCount} sources locked
      </p>
    </ChartCard>
  )
}

function SettlementCard({ settlement }: { settlement: SettlementPreview }) {
  return (
    <ChartCard label="Settlement">
      <div className="mb-3 flex items-center justify-between gap-3">
        <span className="font-mono text-[11px] text-slate-400">{settlement.city}</span>
        <span className="font-mono text-[10px] uppercase tracking-wider text-emerald-400/80">
          settled {settlement.outcome}
        </span>
      </div>

      <p className="mb-3 font-mono text-lg text-[#E9E6DF]">{settlement.metric}</p>

      <blockquote className="border-l border-[#E0A458]/50 pl-3">
        <p className="font-mono text-[11px] leading-relaxed text-slate-400">
          {settlement.quote}
        </p>
      </blockquote>

      <p className="mt-3 flex items-center gap-2 font-mono text-[10px] uppercase tracking-wider text-slate-600">
        <Quote className="h-3 w-3" />
        {settlement.publishers.join(" + ")}
      </p>
    </ChartCard>
  )
}

// ---------------------------------------------------------------------------
// The component
// ---------------------------------------------------------------------------

export interface ModernBackgroundPathsProps {
  title?: string
  eyebrow?: string
  subtitle?: string
  market?: MarketPreview
  settlement?: SettlementPreview
  ctaLabel?: string
  ctaHref?: string
  className?: string
}

const DEFAULT_MARKET: MarketPreview = {
  city: "Jakarta",
  question: "Will the maximum temperature on 14 December 2026 be at least 33.0 °C?",
  yesBps: 6200,
  noBps: 3800,
  closesIn: "12d",
  sourceCount: 2,
}

const DEFAULT_SETTLEMENT: SettlementPreview = {
  city: "New York",
  outcome: "Yes",
  metric: "24.7 °C",
  quote: '"daily":{"time":["2026-10-14"],"temperature_2m_max":[24.7]}',
  source: "archive-api.open-meteo.com",
  publishers: ["open-meteo", "weather.gov"],
}

export default function ModernBackgroundPaths({
  title = "Cite",
  eyebrow = "Weather markets on GenLayer",
  subtitle = "Settled by evidence, not by assertion. Every settlement cites the web, and the contract checks that the quote is really in the page.",
  market = DEFAULT_MARKET,
  settlement = DEFAULT_SETTLEMENT,
  ctaLabel = "Browse the board",
  ctaHref = "#markets",
  className,
}: ModernBackgroundPathsProps) {
  const reduced = !!useReducedMotion()
  const [currentPattern, setCurrentPattern] = useState<BackgroundPattern>("synoptic")

  useEffect(() => {
    if (reduced) return
    const interval = setInterval(() => {
      setCurrentPattern((previous) => {
        const index = PATTERNS.findIndex((pattern) => pattern.id === previous)
        return PATTERNS[(index + 1) % PATTERNS.length].id
      })
    }, 12000)
    return () => clearInterval(interval)
  }, [reduced])

  const words = title.split(" ")
  const active = PATTERNS.find((pattern) => pattern.id === currentPattern) ?? PATTERNS[0]

  return (
    <section
      className={cn(
        "relative isolate flex min-h-[92vh] w-full items-center justify-center overflow-hidden bg-[#0A0C11]",
        className
      )}
    >
      {/* The chart */}
      <div className="absolute inset-0 text-[#8AA0B4]">
        <svg
          className="h-full w-full"
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="xMidYMid slice"
          aria-hidden
        >
          <Graticule />
          <AnimatePresence mode="wait">
            <motion.g
              key={currentPattern}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 1.4 }}
            >
              {currentPattern === "synoptic" && <SynopticPattern reduced={reduced} />}
              {currentPattern === "radar" && <RadarPattern reduced={reduced} />}
              {currentPattern === "stations" && <StationsPattern reduced={reduced} />}
              {currentPattern === "wind" && <WindPattern reduced={reduced} />}
            </motion.g>
          </AnimatePresence>
        </svg>
      </div>

      {/* The paper, and the light falling on it */}
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_50%_35%,rgba(10,12,17,0)_0%,rgba(10,12,17,0.55)_58%,rgba(10,12,17,0.92)_100%)]" />
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_bottom,rgba(10,12,17,0.7)_0%,transparent_28%,transparent_72%,rgba(10,12,17,0.85)_100%)]" />

      <div className="relative z-10 mx-auto w-full max-w-6xl px-5 py-20 md:px-8">
        <div className="flex flex-col items-center text-center">
          <motion.span
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7 }}
            className="mb-7 font-mono text-[10px] uppercase tracking-[0.34em] text-slate-500"
          >
            {eyebrow}
          </motion.span>

          <h1 className="mb-6 font-sans text-6xl font-semibold leading-none tracking-[-0.045em] [perspective:1000px] sm:text-8xl">
            {words.map((word, wordIndex) => (
              <span key={wordIndex} className="mr-4 inline-block last:mr-0">
                {word.split("").map((letter, letterIndex) => (
                  <motion.span
                    key={`${wordIndex}-${letterIndex}`}
                    initial={{ y: 70, opacity: 0, rotateX: -70 }}
                    animate={{ y: 0, opacity: 1, rotateX: 0 }}
                    transition={{
                      delay: wordIndex * 0.12 + letterIndex * 0.045,
                      type: "spring",
                      stiffness: 120,
                      damping: 19,
                    }}
                    className="inline-block text-[#E9E6DF] transition-colors duration-500 hover:text-[#E0A458]"
                  >
                    {letter}
                  </motion.span>
                ))}
              </span>
            ))}
          </h1>

          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.8, duration: 0.8 }}
            className="mb-10 max-w-xl text-[15px] leading-relaxed text-slate-400"
          >
            {subtitle}
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 1, duration: 0.6 }}
          >
            <Button
              asChild
              size="lg"
              className="group h-11 rounded-lg border border-white/15 bg-transparent px-7 text-sm font-medium tracking-wide text-[#E9E6DF] transition-colors hover:border-[#E0A458]/60 hover:bg-[#E0A458]/5 hover:text-[#F0C88A]"
            >
              <a href={ctaHref}>
                {ctaLabel}
                <ArrowRight className="ml-2 h-3.5 w-3.5 transition-transform duration-300 group-hover:translate-x-1" />
              </a>
            </Button>
          </motion.div>

          <div className="mt-14 grid w-full max-w-3xl grid-cols-1 gap-4 sm:grid-cols-2">
            <MarketCard market={market} />
            <SettlementCard settlement={settlement} />
          </div>
        </div>
      </div>

      {/* Which chart is on screen */}
      <div className="absolute right-6 top-6 z-20 flex items-center gap-3">
        <span className="hidden font-mono text-[10px] uppercase tracking-[0.22em] text-slate-600 sm:inline">
          {active.label}
        </span>
        <div className="flex gap-2">
          {PATTERNS.map((pattern) => (
            <button
              key={pattern.id}
              type="button"
              title={`${pattern.label} — ${pattern.note}`}
              aria-label={`Show the ${pattern.label} chart`}
              aria-current={pattern.id === currentPattern}
              onClick={() => setCurrentPattern(pattern.id)}
              className={cn(
                "h-px w-6 transition-colors duration-300",
                pattern.id === currentPattern
                  ? "bg-[#E0A458]"
                  : "bg-white/15 hover:bg-white/35"
              )}
            />
          ))}
        </div>
      </div>
    </section>
  )
}
