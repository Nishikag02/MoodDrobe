import type { Recommendation, Swatch, VibeScore } from "@/lib/api"
import { inkOn } from "@/lib/palette"

export type Preview = { url: string; name: string; palette: Swatch[] }

function Bars({ items }: { items: VibeScore[] }) {
  const top = Math.max(...items.map((v) => v.score), 0.0001)
  return (
    <ul className="space-y-1.5">
      {items.map((v) => (
        <li key={v.vibe} className="grid grid-cols-[110px_1fr_38px] items-center gap-2 text-sm">
          <span className="truncate capitalize">{v.vibe}</span>
          <span className="h-1.5 overflow-hidden rounded-full bg-[var(--mood-line)]">
            <span className="block h-full rounded-full bg-[var(--mood-accent)]" style={{ width: `${(v.score / top) * 100}%` }} />
          </span>
          <span className="text-right text-xs text-[var(--mood-muted)] tabular-nums">{Math.round(v.score * 100)}%</span>
        </li>
      ))}
    </ul>
  )
}

export function PaletteStrip({ swatches, tall = false }: { swatches: Swatch[]; tall?: boolean }) {
  if (!swatches.length) return null
  const total = swatches.reduce((s, c) => s + (c.weight ?? 1), 0) || 1
  return (
    <div className={`flex w-full overflow-hidden rounded-xl ${tall ? "h-16" : "h-9"}`}>
      {swatches.map((c, i) => (
        <div
          key={c.hex + i}
          title={`${c.name ?? ""} ${c.hex}`}
          className="flex min-w-8 items-end px-1.5 pb-1 text-[10px] font-medium"
          style={{ background: c.hex, color: inkOn(c.hex), flexGrow: Math.max((c.weight ?? 1) / total, 0.06) }}
        >
          {tall && <span className="truncate">{c.name ?? c.hex}</span>}
        </div>
      ))}
    </div>
  )
}

export function VibeReading({ data, previews, vibeText }: { data: Recommendation; previews: Preview[]; vibeText?: string }) {
  const inputs = data.inputs ?? []
  const allColours: Swatch[] = inputs.length
    ? inputs.flatMap((i) => i.colors ?? [])
    : data.query_colors ?? previews.flatMap((p) => p.palette)
  const palette = mergeSwatches(allColours).slice(0, 6)
  const overall = data.vibes ?? []

  return (
    <section className="mood-rise grid gap-5 rounded-3xl border border-[var(--mood-line)] bg-[var(--mood-card)] p-5 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
      <div className="space-y-4">
        <p className="text-[11px] font-semibold tracking-[0.16em] text-[var(--mood-muted)] uppercase">How MoodDrobe read your vibe</p>
        {vibeText && <h2 className="font-display text-3xl leading-tight capitalize">“{vibeText}”</h2>}
        {previews.length > 0 && (
          <div className="flex flex-wrap gap-3">
            {previews.map((p, idx) => {
              const reading = inputs[idx]
              return (
                <figure key={p.url} className="w-36 space-y-1.5">
                  <img src={p.url} alt={p.name} className="aspect-[4/5] w-full rounded-xl object-cover" />
                  {reading && (
                    <figcaption className="space-y-1 text-xs">
                      <span className={`inline-block rounded-full px-2 py-0.5 font-medium ${reading.kind === "mood" ? "bg-[var(--mood-accent-soft)]" : "bg-[var(--mood-line)]"}`}>
                        {reading.kind === "mood" ? "Mood photo" : "Clothing photo"}
                      </span>
                      {reading.scene && <p className="text-[var(--mood-muted)] capitalize">{reading.scene}</p>}
                    </figcaption>
                  )}
                </figure>
              )
            })}
          </div>
        )}
        {inputs.map((i, idx) =>
          i.fashion_reading ? (
            <blockquote key={idx} className="font-display border-l-2 border-[var(--mood-accent)] pl-3 text-lg leading-snug">
              {i.fashion_reading}
            </blockquote>
          ) : null,
        )}
        {inputs.some((i) => i.kind === "mood") && !inputs.some((i) => i.fashion_reading) && (
          <p className="text-sm text-[var(--mood-muted)]">
            This isn't a clothing photo, so MoodDrobe translated its mood into fashion vibes and searched the catalogue for
            those, keeping a little of the image's own colour and texture.
          </p>
        )}
        {data.detected && data.detected.confidence >= 0.5 && (
          <p className="text-sm">
            Detected a <strong className="capitalize">{data.detected.category ?? data.detected.garment_type}</strong>{" "}
            <span className="text-[var(--mood-muted)]">({Math.round(data.detected.confidence * 100)}% sure), so we also built looks around it.</span>
          </p>
        )}
      </div>

      <div className="space-y-4">
        {palette.length > 0 && (
          <div className="space-y-2">
            <h3 className="text-[11px] font-semibold tracking-[0.16em] text-[var(--mood-muted)] uppercase">Palette</h3>
            <PaletteStrip swatches={palette} tall />
          </div>
        )}
        {overall.length > 0 && (
          <div className="space-y-2">
            <h3 className="text-[11px] font-semibold tracking-[0.16em] text-[var(--mood-muted)] uppercase">Aesthetic</h3>
            <Bars items={overall} />
          </div>
        )}
        {(data.attributes?.length ?? 0) > 0 && (
          <div className="space-y-2">
            <h3 className="text-[11px] font-semibold tracking-[0.16em] text-[var(--mood-muted)] uppercase">Texture & detail cues</h3>
            <div className="flex flex-wrap gap-1.5">
              {data.attributes!.map((a) => (
                <span key={a.attribute} className="rounded-full border border-[var(--mood-line)] px-2.5 py-0.5 text-xs">
                  {a.attribute.replace(/_/g, " ")} <span className="text-[var(--mood-muted)]">· {a.type}</span>
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  )
}

/** Merge swatches that share a colour name, adding their weights. */
export function mergeSwatches(list: Swatch[]): Swatch[] {
  const out = new Map<string, Swatch>()
  for (const s of list) {
    const key = s.name ?? s.hex
    const prev = out.get(key)
    if (prev) prev.weight = (prev.weight ?? 0) + (s.weight ?? 0)
    else out.set(key, { ...s })
  }
  return [...out.values()].sort((a, b) => (b.weight ?? 0) - (a.weight ?? 0))
}
