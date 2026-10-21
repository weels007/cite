import { cn } from "@/lib/utils"

/**
 * The Cite mark: an instrument dial. A single isobar arc with a needle at a
 * reading. It is a barometer, a compass and a citation marker at once, and it
 * stays legible at sixteen pixels.
 */
export function CiteLogo({
  className,
  size = 32,
}: {
  className?: string
  size?: number
}) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-[9px] border border-white/10 bg-[#0E131C]",
        className
      )}
      style={{ width: size, height: size }}
      aria-hidden
    >
      <svg
        width={size * 0.72}
        height={size * 0.72}
        viewBox="0 0 24 24"
        fill="none"
      >
        {/* The isobar, left open at the bottom like a dial */}
        <circle
          cx="12"
          cy="12.5"
          r="7.4"
          stroke="#7D93A8"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeDasharray="34 12.5"
          transform="rotate(112 12 12.5)"
        />
        {/* The needle */}
        <path
          d="M12 12.5 L16.4 8.1"
          stroke="#E0A458"
          strokeWidth="1.6"
          strokeLinecap="round"
        />
        {/* The pivot */}
        <circle cx="12" cy="12.5" r="1.35" fill="#E0A458" />
      </svg>
    </span>
  )
}
