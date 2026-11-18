import { Check, RotateCcw, SlidersHorizontal, X } from "lucide-react"
import type { Filters, Options, Product } from "@/lib/api"
import { cn } from "@/lib/utils"

type Props = {
  filters: Filters
  options: Options | null
  results: Product[]
  onChange: (f: Filters) => void
  busy: boolean
}

const toggle = (list: string[], v: string) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v])

export function FilterBar({ filters, options, results, onChange, busy }: Props) {
  // Offer the tags that actually occur in these results, most common first, plus any already chosen.
  const counts = new Map<string, number>()
  for (const p of results) for (const t of p.tags ?? []) counts.set(t, (counts.get(t) ?? 0) + 1)
  const tagList = [
    ...new Set([...filters.tags, ...filters.avoid_tags, ...[...counts.entries()].sort((a, b) => b[1] - a[1]).map(([t]) => t)]),
  ].slice(0, 14)

  const colourCounts = new Map<string, number>()
  for (const p of results) for (const c of p.color_names ?? []) colourCounts.set(c, (colourCounts.get(c) ?? 0) + 1)
  const colours = (options?.colors ?? []).filter((c) => colourCounts.has(c.name) || filters.only_colors.includes(c.name))
  const shownColours = colours.length ? colours : (options?.colors ?? []).slice(0, 12)

  const cycleTag = (t: string) => {
    if (filters.tags.includes(t)) onChange({ ...filters, tags: toggle(filters.tags, t), avoid_tags: [...filters.avoid_tags, t] })
    else if (filters.avoid_tags.includes(t)) onChange({ ...filters, avoid_tags: toggle(filters.avoid_tags, t) })
    else if (filters.tags.length < 5) onChange({ ...filters, tags: [...filters.tags, t] })
  }
  const active = filters.tags.length + filters.avoid_tags.length + filters.only_colors.length > 0 || filters.diversity !== 0.35

  return (
    <div className={cn("space-y-3 rounded-2xl border border-[var(--mood-line)] bg-[var(--mood-card)] p-4", busy && "opacity-70")}>
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
        <span className="flex items-center gap-2 text-sm font-semibold">
          <SlidersHorizontal className="size-4" /> Refine
        </span>
        <label className="flex items-center gap-3 text-xs text-[var(--mood-muted)]">
          Closest
          <input
            type="range"
            min={0}
            max={0.8}
            step={0.05}
            value={filters.diversity}
            onChange={(e) => onChange({ ...filters, diversity: Number(e.target.value) })}
            className="w-32 accent-[var(--mood-accent)]"
            aria-label="Variety"
          />
          More variety
        </label>
        {active && (
          <button
            type="button"
            onClick={() => onChange({ tags: [], avoid_tags: [], only_colors: [], colors: filters.colors, diversity: 0.35 })}
            className="ml-auto flex items-center gap-1 text-xs text-[var(--mood-muted)] hover:text-[var(--mood-ink)]"
          >
            <RotateCcw className="size-3.5" /> Reset filters
          </button>
        )}
      </div>

      {shownColours.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="w-16 text-xs text-[var(--mood-muted)]">Colours</span>
          {shownColours.map((c) => {
            const on = filters.only_colors.includes(c.name)
            return (
              <button
                key={c.name}
                type="button"
                title={c.name}
                onClick={() => (on || filters.only_colors.length < 5) && onChange({ ...filters, only_colors: toggle(filters.only_colors, c.name) })}
                className={cn(
                  "flex items-center gap-1.5 rounded-full border py-0.5 pr-2.5 pl-1 text-xs capitalize transition",
                  on ? "border-[var(--mood-ink)] bg-[var(--mood-ink)] text-[var(--mood-paper)]" : "border-[var(--mood-line)] hover:border-[var(--mood-muted)]",
                )}
              >
                <span className="size-4 rounded-full border border-black/10" style={{ background: c.hex }} />
                {c.name}
              </button>
            )
          })}
        </div>
      )}

      {tagList.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="w-16 text-xs text-[var(--mood-muted)]">Details</span>
          {tagList.map((t) => {
            const inc = filters.tags.includes(t)
            const exc = filters.avoid_tags.includes(t)
            return (
              <button
                key={t}
                type="button"
                onClick={() => cycleTag(t)}
                title={inc ? "Must have — click to exclude" : exc ? "Excluded — click to clear" : "Click to require"}
                className={cn(
                  "flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs transition",
                  inc && "border-[var(--mood-good)] bg-[var(--mood-good)] text-white",
                  exc && "border-[var(--mood-accent)] text-[var(--mood-accent)] line-through",
                  !inc && !exc && "border-[var(--mood-line)] hover:border-[var(--mood-muted)]",
                )}
              >
                {inc && <Check className="size-3" />}
                {exc && <X className="size-3" />}
                {t.replace(/_/g, " ")}
              </button>
            )
          })}
          <span className="text-[11px] text-[var(--mood-muted)]">click: require → exclude → clear</span>
        </div>
      )}
    </div>
  )
}
