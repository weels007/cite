import * as React from "react"

import { cn } from "@/lib/utils"

export type BadgeVariant = "default" | "outline" | "open" | "resolved" | "void"

const variants: Record<BadgeVariant, string> = {
  default: "border-white/10 bg-white/5 text-slate-300",
  outline: "border-white/10 text-slate-400",
  open: "border-cyan-400/30 bg-cyan-400/10 text-cyan-300",
  resolved: "border-emerald-400/30 bg-emerald-400/10 text-emerald-300",
  void: "border-amber-400/30 bg-amber-400/10 text-amber-300",
}

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant
}

export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-medium transition-colors",
        variants[variant],
        className
      )}
      {...props}
    />
  )
}
