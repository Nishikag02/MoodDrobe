import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react"
import { ArrowRight, ArrowUpRight, CircleAlert, ImagePlus, LoaderCircle, RefreshCw } from "lucide-react"
import {
  emptyFilters,
  getOptions,
  recommendFromImages,
  recommendFromVibe,
  type Filters,
  type Options,
  type Product,
  type Recommendation,
  type Swatch,
} from "@/lib/api"
import { postHistory } from "@/lib/account"
import { buildOutfits } from "@/lib/outfits"
import { useCurrentUser } from "@/lib/session"
import { useSearchParams } from "react-router-dom"
import { extractPalette, inkOn, themeColour, tint } from "@/lib/palette"
import { cn } from "@/lib/utils"
import { FilterBar } from "@/components/mood/FilterBar"
import { OutfitBoard } from "@/components/mood/OutfitBoard"
import { ProductDrawer } from "@/components/mood/ProductDrawer"
import { ProductTile } from "@/components/mood/ProductTile"
import { SiteHeader, type Health, type SearchMode } from "@/components/mood/SiteHeader"
import { mergeSwatches, type Preview } from "@/components/mood/VibeReading"

const PRESET_VIBES = [
  "cozy coffee shop on a rainy afternoon",
  "beach at golden hour",
  "misty mountain cabin",
  "vintage bookstore",
  "city street at night",
  "old money",
  "dark academia",
]

const OUTER = new Set(["Anorak", "Blazer", "Bomber", "Cardigan", "Jacket", "Parka", "Peacoat", "Poncho", "Cape", "Coat", "Kimono"])
const GROUPS: { title: string; test: (p: Product) => boolean }[] = [
  { title: "Tops", test: (p) => p.garment_type === "upper" && !OUTER.has(p.category_name ?? "") },
  { title: "Bottoms", test: (p) => p.garment_type === "lower" },
  { title: "Layers", test: (p) => OUTER.has(p.category_name ?? "") },
  { title: "Dresses and one-pieces", test: (p) => p.garment_type === "full" && !OUTER.has(p.category_name ?? "") },
]

type Query = { kind: "image"; files: File[]; steer: string; mode: SearchMode } | { kind: "vibe"; text: string }

export default function Studio() {
  const [mode, setMode] = useState<SearchMode>("vibe")
  const [files, setFiles] = useState<File[]>([])
  const [previews, setPreviews] = useState<Preview[]>([])
  const [steer, setSteer] = useState("")
  const [vibe, setVibe] = useState("")
  const [filters, setFilters] = useState<Filters>(emptyFilters)
  const [query, setQuery] = useState<Query | null>(null)
  const [data, setData] = useState<Recommendation | null>(null)
  const [elapsed, setElapsed] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [health, setHealth] = useState<Health>("checking")
  const [options, setOptions] = useState<Options | null>(null)
  const [open, setOpen] = useState<Product | null>(null)
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const requestId = useRef(0)
  const user = useCurrentUser()
  const signedIn = useRef(false)
  signedIn.current = !!user
  const [params, setParams] = useSearchParams()

  const checkHealth = useCallback(() => {
    setHealth("checking")
    getOptions()
      .then((o) => {
        setOptions(o)
        setHealth("online")
      })
      .catch(() => setHealth("offline"))
  }, [])
  useEffect(checkHealth, [checkHealth])


  const run = useCallback(async (q: Query, f: Filters) => {
    const id = ++requestId.current
    setQuery(q)
    setLoading(true)
    setError(null)
    const t0 = performance.now()
    try {
      const res =
        q.kind === "image"
          ? await recommendFromImages(q.files, q.steer, f, 24, q.mode === "lookalike" ? "clothing" : "auto")
          : await recommendFromVibe(q.text, f)
      if (id !== requestId.current) return
      setData(res)
      setElapsed((performance.now() - t0) / 1000)
      if (signedIn.current) {
        const scene = res.inputs?.[0]?.scene ?? res.vibes?.[0]?.vibe ?? null
        postHistory(q.kind === "vibe" ? { kind: "vibe", text: q.text, scene: null } : { kind: "photo", text: q.files.map((f) => f.name).join(", "), scene })
      }
      setHealth("online")
      window.scrollTo({ top: 0, behavior: "smooth" })
    } catch (e) {
      if (id !== requestId.current) return
      const err = e as Error & { status?: number }
      setError(err.message)
      if (!err.status) setHealth("offline")
    } finally {
      if (id === requestId.current) setLoading(false)
    }
  }, [])

  // /?vibe=... (from the dashboard's recent vibes) runs that vibe straight away.
  useEffect(() => {
    const v = params.get("vibe")
    if (!v) return
    setParams({}, { replace: true })
    setVibe(v)
    run({ kind: "vibe", text: v }, emptyFilters)
  }, [params, setParams, run])

  // Dropping or pasting images starts the search straight away.
  const addFiles = useCallback(
    async (incoming: FileList | File[], replace = false) => {
      const images = [...incoming].filter((f) => f.type.startsWith("image/")).slice(0, 8)
      if (!images.length) return
      const next = await Promise.all(images.map(async (f) => ({ url: URL.createObjectURL(f), name: f.name, palette: await extractPalette(f) })))
      const all = (replace ? images : [...files, ...images]).slice(0, 8)
      if (replace) previews.forEach((p) => URL.revokeObjectURL(p.url))
      setPreviews((prev) => (replace ? next : [...prev, ...next]).slice(0, 8))
      setFiles(all)
      setData(null)
      setVibe("")
      run({ kind: "image", files: all, steer, mode }, filters)
    },
    [files, previews, steer, mode, filters, run],
  )

  useEffect(() => {
    const onPaste = (e: ClipboardEvent) => {
      const target = e.target as HTMLElement | null
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA")) return
      const pasted = [...(e.clipboardData?.files ?? [])]
      if (pasted.length) addFiles(pasted, true)
    }
    window.addEventListener("paste", onPaste)
    return () => window.removeEventListener("paste", onPaste)
  }, [addFiles])

  const submitVibe = (text = vibe) => {
    const t = text.trim()
    if (!t) return
    previews.forEach((p) => URL.revokeObjectURL(p.url))
    setPreviews([])
    setFiles([])
    setVibe(t)
    setData(null)
    run({ kind: "vibe", text: t }, filters)
  }
  const restyle = () => files.length && run({ kind: "image", files, steer, mode }, filters)
  const changeFilters = (f: Filters) => {
    setFilters(f)
    if (query) run(query, f)
  }
  const changeMode = (m: SearchMode) => {
    setMode(m)
    if (query?.kind === "image") run({ ...query, mode: m }, filters)
  }
  const reset = () => {
    requestId.current++
    previews.forEach((p) => URL.revokeObjectURL(p.url))
    setFiles([])
    setPreviews([])
    setSteer("")
    setVibe("")
    setData(null)
    setQuery(null)
    setError(null)
    setLoading(false)
    setFilters(emptyFilters)
    window.scrollTo({ top: 0, behavior: "smooth" })
  }

  // ----- derived view data -----
  const yourStyle = useMemo(() => data?.your_style ?? [], [data])
  const outfits = useMemo(() => buildOutfits(yourStyle, 3), [yourStyle])
  const allResults = useMemo(() => [...yourStyle, ...(data?.complete_the_look ?? []), ...(data?.closest_matches ?? [])], [yourStyle, data])
  const palette: Swatch[] = useMemo(() => {
    const server = (data?.inputs ?? []).flatMap((i) => i.colors ?? [])
    if (server.length) return mergeSwatches(server).slice(0, 4)
    if (data?.query_colors?.length) return data.query_colors.slice(0, 4)
    if (query?.kind === "vibe" && yourStyle.length) {
      // For a typed vibe, show the colours the results share.
      const counts = new Map<string, Swatch>()
      for (const p of yourStyle.slice(0, 12))
        (p.palette ?? []).slice(0, 2).forEach((hex, i) => {
          const name = p.color_names?.[i] ?? hex
          const s = counts.get(name) ?? { hex, name, weight: 0 }
          s.weight = (s.weight ?? 0) + 1
          counts.set(name, s)
        })
      const list = [...counts.values()].sort((a, b) => (b.weight ?? 0) - (a.weight ?? 0)).slice(0, 4)
      const total = list.reduce((s, c) => s + (c.weight ?? 0), 0) || 1
      return list.map((c) => ({ ...c, weight: (c.weight ?? 0) / total }))
    }
    return previews.flatMap((p) => p.palette).slice(0, 4)
  }, [data, query, yourStyle, previews])

  const theme = themeColour(palette)
  const themeStyle = {
    "--mood-tint": theme ? tint(theme, 0.35) : undefined,
    "--mood-tint-soft": theme && data ? tint(theme, 0.88) : undefined,
  } as CSSProperties
  const cardColours = theme ? [tint(theme, 0.62), "#EEDFCB", "#D7F0EA"] : ["#F7D9E0", "#EEDFCB", "#D7F0EA"]

  const firstInput = data?.inputs?.[0]
  const headline =
    query?.kind === "vibe"
      ? query.text
      : firstInput?.scene ?? (data?.detected && data.detected.confidence >= 0.5 && firstInput?.kind === "clothing" ? `a ${data.detected.category?.toLowerCase() ?? "garment"}` : data?.vibes?.[0]?.vibe)
  const showStudio = query !== null

  return (
    <div className="mood min-h-svh" style={themeStyle}>
      <SiteHeader health={health} onCheck={checkHealth} onLogo={reset} mode={mode} onMode={changeMode} />
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        multiple
        hidden
        onChange={(e) => {
          if (e.target.files) addFiles(e.target.files, true)
          e.target.value = ""
        }}
      />

      {!showStudio ? (
        <Landing
          mode={mode}
          dragging={dragging}
          setDragging={setDragging}
          onBrowse={() => inputRef.current?.click()}
          onDrop={(f) => addFiles(f, true)}
          vibe={vibe}
          setVibe={setVibe}
          submitVibe={submitVibe}
          health={health}
          checkHealth={checkHealth}
        />
      ) : (
        <main className="mx-auto grid max-w-[1400px] gap-8 px-5 pt-4 pb-16 sm:px-8 lg:grid-cols-[300px_minmax(0,1fr)] lg:gap-12">
          {/* Left: the inspiration, its palette and controls */}
          <aside className="space-y-5 lg:sticky lg:top-24 lg:self-start">
            <div className="relative mr-4 mb-4 max-w-[280px] sm:max-w-none">
              <div className="mood-arch absolute inset-0 translate-x-3 translate-y-3 bg-[var(--mood-tint)] transition-colors duration-700" />
              <div className="mood-arch absolute inset-0 translate-x-1.5 translate-y-1.5 bg-[var(--mood-sun)]" />
              {query?.kind === "image" && previews[0] ? (
                <button type="button" onClick={() => inputRef.current?.click()} className="mood-arch group relative block aspect-[4/5] w-full overflow-hidden" title="Try another photo">
                  <img src={previews[0].url} alt="Your inspiration" className="size-full object-cover" />
                  <span className="absolute right-3 bottom-3 rounded-md bg-black/45 p-1.5 text-white backdrop-blur transition group-hover:bg-black/70">
                    <ArrowUpRight className="size-4" />
                  </span>
                </button>
              ) : (
                <div
                  className="mood-arch relative flex aspect-[4/5] w-full items-end p-6"
                  style={{ background: palette.length ? `linear-gradient(160deg, ${palette.map((p) => p.hex).join(", ")})` : "var(--mood-arch)" }}
                >
                  <p className="font-display text-4xl capitalize" style={{ color: palette[0] ? inkOn(palette[palette.length - 1].hex) : undefined }}>
                    {query?.kind === "vibe" ? query.text : ""}
                  </p>
                </div>
              )}
            </div>
            {previews.length > 1 && (
              <div className="flex gap-1.5">
                {previews.slice(1).map((p) => (
                  <img key={p.url} src={p.url} alt={p.name} className="size-11 rounded-md object-cover" />
                ))}
                <span className="self-center text-xs text-[var(--mood-muted)]">moodboard</span>
              </div>
            )}

            {palette.length > 0 && (
              <div className="grid grid-cols-4 gap-2">
                {palette.map((c) => (
                  <div key={c.hex + c.name} className="text-center">
                    <span className="block h-9 rounded-full" style={{ background: c.hex }} title={c.hex} />
                    <span className="mt-1 block truncate text-[11px] text-[var(--mood-muted)]">
                      {c.name ?? c.hex}
                      {c.weight ? ` ${Math.round(c.weight * 100)}%` : ""}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {(data?.vibes?.length ?? 0) > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {data!.vibes!.map((v, i) => (
                  <span key={v.vibe} className="rounded-full px-2.5 py-1 text-xs font-medium capitalize" style={{ background: i === 0 ? "var(--mood-tint)" : cardColours[i % 3] }}>
                    {v.vibe} {Math.round(v.score * 100)}%
                  </span>
                ))}
              </div>
            )}

            {query?.kind === "image" ? (
              <div className="space-y-2">
                <label className="block text-xs font-semibold" htmlFor="steer">Style hint</label>
                <input
                  id="steer"
                  value={steer}
                  onChange={(e) => setSteer(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && restyle()}
                  placeholder="more formal, oversized, pastel"
                  className="w-full rounded-lg border border-[var(--mood-line)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--mood-ink)]"
                />
              </div>
            ) : (
              <form
                onSubmit={(e) => {
                  e.preventDefault()
                  submitVibe()
                }}
                className="space-y-2"
              >
                <label className="block text-xs font-semibold" htmlFor="vibe2">Vibe</label>
                <input
                  id="vibe2"
                  value={vibe}
                  onChange={(e) => setVibe(e.target.value)}
                  placeholder="rainy day in Paris"
                  className="w-full rounded-lg border border-[var(--mood-line)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--mood-ink)]"
                />
              </form>
            )}
            <div className="flex gap-2">
              <button
                type="button"
                disabled={loading}
                onClick={() => (query?.kind === "image" ? restyle() : submitVibe())}
                className="flex flex-1 items-center justify-center gap-2 rounded-lg py-2.5 text-sm font-semibold text-white shadow-[3px_3px_0_var(--mood-tint)] transition hover:translate-y-px disabled:opacity-60"
                style={{ background: theme && data ? deepen(theme) : "var(--mood-ink)" }}
              >
                {loading && <LoaderCircle className="size-4 animate-spin" />}
                Find my style
              </button>
              <button type="button" onClick={reset} className="rounded-lg border border-[var(--mood-ink)] px-3 text-sm font-medium hover:bg-white">
                Start over
              </button>
            </div>
          </aside>

          {/* Right: the reading and the results */}
          <section className="min-w-0 space-y-10">
            {error && (
              <div className="flex flex-wrap items-center gap-3 rounded-2xl bg-[var(--mood-accent-soft)] p-4 text-sm">
                <CircleAlert className="size-4 text-[var(--mood-accent)]" />
                <span className="flex-1">{error}</span>
                {query && (
                  <button type="button" onClick={() => run(query, filters)} className="flex items-center gap-1 font-medium underline">
                    <RefreshCw className="size-3.5" /> Try again
                  </button>
                )}
              </div>
            )}

            {loading && !data && (
              <div className="space-y-4">
                <h1 className="font-display text-5xl">Reading the mood</h1>
                {[0, 1, 2].map((i) => (
                  <div key={i} className="mood-shimmer h-40 rounded-[28px]" style={{ animationDelay: `${i * 150}ms` }} />
                ))}
              </div>
            )}

            {data && (
              <div className={cn("space-y-10 transition-opacity", loading && "opacity-50")}>
                <div className="mood-rise space-y-3">
                  <h1 className="font-display text-5xl sm:text-6xl" style={{ color: theme ? deepen(theme) : undefined }}>
                    This reads as <span className="capitalize">{headline ?? "your vibe"}</span>.
                  </h1>
                  <div className="flex flex-wrap gap-2 text-xs">
                    {firstInput && (
                      <span className="rounded-full bg-[var(--mood-tint)] px-2.5 py-1">{firstInput.kind === "mood" ? "Mood photo" : "Clothing photo"}</span>
                    )}
                    {previews.length > 1 && <span className="rounded-full bg-white/70 px-2.5 py-1">Moodboard of {previews.length}</span>}
                    {elapsed !== null && <span className="rounded-full bg-white/70 px-2.5 py-1">Matched in {elapsed.toFixed(1)} seconds</span>}
                    {data.detected && data.detected.confidence >= 0.5 && (
                      <span className="rounded-full bg-white/70 px-2.5 py-1">
                        Detected <span className="capitalize">{data.detected.category ?? data.detected.garment_type}</span>
                      </span>
                    )}
                    {(data.attributes ?? []).slice(0, 3).map((a) => (
                      <span key={a.attribute} className="rounded-full bg-white/70 px-2.5 py-1">{a.attribute.replace(/_/g, " ")}</span>
                    ))}
                  </div>
                  {data.inputs?.map((i, idx) =>
                    i.fashion_reading ? (
                      <p key={idx} className="max-w-2xl text-lg leading-snug">{i.fashion_reading}</p>
                    ) : null,
                  )}
                </div>

                {loading && (
                  <p className="flex items-center gap-2 text-sm text-[var(--mood-muted)]">
                    <LoaderCircle className="size-4 animate-spin" /> Restyling…
                  </p>
                )}

                {(data.complete_the_look?.length ?? 0) > 0 && (
                  <Group title="Complete the look" note={`Pairs with your ${data.detected?.category?.toLowerCase() ?? "piece"}`}>
                    <TileRow items={data.complete_the_look!.slice(0, 6)} onOpen={setOpen} />
                  </Group>
                )}

                {outfits.length > 0 && (
                  <Group title="Outfit ideas">
                    <div className="space-y-4">
                      {outfits.map((o, i) => (
                        <OutfitBoard key={o.pieces.map((p) => p.product_id).join()} outfit={o} n={i} onOpen={setOpen} background={cardColours[i % 3]} />
                      ))}
                    </div>
                  </Group>
                )}

                <FilterBar filters={filters} options={options} results={allResults} onChange={changeFilters} busy={loading} />

                {yourStyle.length === 0 && !loading && (
                  <p className="rounded-2xl bg-white/60 p-6 text-center text-sm text-[var(--mood-muted)]">Nothing matches all of those filters. Try removing one.</p>
                )}

                {GROUPS.map((g) => {
                  const items = yourStyle.filter(g.test)
                  return items.length ? (
                    <Group key={g.title} title={g.title}>
                      <TileRow items={items.slice(0, 12)} onOpen={setOpen} />
                    </Group>
                  ) : null
                })}

                {(data.closest_matches?.length ?? 0) > 0 && (
                  <Group title="Closest matches" note="Nearest items in FashionCLIP space, before any re-ranking">
                    <TileRow items={data.closest_matches!} onOpen={setOpen} />
                  </Group>
                )}
              </div>
            )}
          </section>
        </main>
      )}

      <ProductDrawer product={open} onClose={() => setOpen(null)} onOpen={setOpen} />
    </div>
  )
}

/** A darker, readable version of the theme colour for headings and buttons. */
function deepen(hex: string): string {
  const n = parseInt(hex.replace("#", ""), 16)
  const ch = [(n >> 16) & 255, (n >> 8) & 255, n & 255]
  const lum = 0.299 * ch[0] + 0.587 * ch[1] + 0.114 * ch[2]
  const f = Math.min(1, 70 / Math.max(lum, 1))
  return "#" + ch.map((c) => Math.round(c * f).toString(16).padStart(2, "0")).join("")
}

function Group({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-baseline gap-x-3">
        <h2 className="mood-underline text-xl font-bold">{title}</h2>
        {note && <span className="text-xs text-[var(--mood-muted)]">{note}</span>}
      </div>
      {children}
    </section>
  )
}

function TileRow({ items, onOpen }: { items: Product[]; onOpen: (p: Product) => void }) {
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-6">
      {items.map((p, i) => (
        <ProductTile key={p.product_id} product={p} onOpen={onOpen} index={i} />
      ))}
    </div>
  )
}

function Landing(props: {
  mode: SearchMode
  dragging: boolean
  setDragging: (v: boolean) => void
  onBrowse: () => void
  onDrop: (f: FileList) => void
  vibe: string
  setVibe: (v: string) => void
  submitVibe: (v?: string) => void
  health: Health
  checkHealth: () => void
}) {
  const { mode, dragging, setDragging, onBrowse, onDrop, vibe, setVibe, submitVibe, health, checkHealth } = props
  return (
    <main className="mx-auto max-w-[1400px] px-5 pb-16 sm:px-8">
      <section className="grid min-h-[calc(100svh-90px)] items-center gap-10 py-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="mood-rise space-y-6">
          <h1 className="font-display text-[clamp(3.2rem,7.4vw,6.4rem)]">
            {mode === "vibe" ? (
              <>
                Upload a vibe.
                <br />
                Discover your style.
              </>
            ) : (
              <>
                Love a look?
                <br />
                Find its look-alikes.
              </>
            )}
          </h1>
          <p className="max-w-sm text-lg leading-snug text-[var(--mood-muted)]">
            {mode === "vibe"
              ? "Drop in a café, a beach, a street at night, a moodboard or an outfit. MoodDrobe reads the mood and builds looks from it."
              : "Drop in a photo of an outfit or a single piece. MoodDrobe finds similar pieces in the catalogue and what to wear with them."}
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault()
              submitVibe()
            }}
            className="flex max-w-md gap-2"
          >
            <input
              value={vibe}
              onChange={(e) => setVibe(e.target.value)}
              placeholder="…or type a vibe: rainy day in Paris"
              maxLength={200}
              className="min-w-0 flex-1 rounded-full border border-[var(--mood-line)] bg-white px-4 py-2.5 text-sm outline-none focus:border-[var(--mood-ink)]"
            />
            <button type="submit" disabled={!vibe.trim()} className="flex items-center rounded-full bg-[var(--mood-ink)] px-4 text-white disabled:opacity-40" aria-label="Search this vibe">
              <ArrowRight className="size-4" />
            </button>
          </form>
          <div className="flex max-w-lg flex-wrap gap-1.5">
            {PRESET_VIBES.map((v) => (
              <button key={v} type="button" onClick={() => submitVibe(v)} className="rounded-full bg-white/70 px-3 py-1 text-xs hover:bg-[var(--mood-arch)]">
                {v}
              </button>
            ))}
          </div>
          {health === "offline" && (
            <div className="flex max-w-md items-start gap-2 rounded-xl bg-[var(--mood-accent-soft)] p-3 text-sm">
              <CircleAlert className="mt-0.5 size-4 shrink-0 text-[var(--mood-accent)]" />
              <div>
                The ML service isn't reachable. Start it with <code className="rounded bg-black/5 px-1">ml-service\start_api.ps1</code> (port 8000), then{" "}
                <button type="button" className="underline" onClick={checkHealth}>check again</button>.
              </div>
            </div>
          )}
        </div>

        {/* The arch dropzone between two pills */}
        <div className="flex h-[min(62vh,520px)] items-end justify-center gap-3 sm:gap-4">
          <div className="mood-pill mood-bob h-[64%] w-[16%] max-w-24 bg-[var(--mood-accent)]" style={{ animationDelay: "-1.5s" }} />
          <button
            type="button"
            onClick={onBrowse}
            onDragOver={(e) => {
              e.preventDefault()
              setDragging(true)
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault()
              setDragging(false)
              onDrop(e.dataTransfer.files)
            }}
            className={cn(
              "mood-arch flex h-full w-[58%] max-w-[380px] flex-col items-center justify-center gap-2 border-2 border-dashed border-[var(--mood-ink)]/70 px-8 text-center transition",
              dragging ? "scale-[1.02] bg-[#CDB0F7]" : "bg-[var(--mood-arch)] hover:bg-[#D5BCF8]",
            )}
          >
            <ImagePlus className="mb-1 size-7 opacity-70" />
            <span className="text-xl font-bold">{dragging ? "Let it go" : "Drop a photo here"}</span>
            <span className="max-w-[220px] text-sm text-[var(--mood-muted)]">or click to choose one. You can also paste an image, or drop several for a moodboard.</span>
          </button>
          <div className="mood-pill mood-bob h-[82%] w-[16%] max-w-24 bg-[var(--mood-sun)]" />
        </div>
      </section>

      <HowItWorks />
    </main>
  )
}

function HowItWorks() {
  const steps = [
    ["Upload anything", "A scene, a room, a moodboard or an outfit. Several images blend into one moodboard.", "var(--mood-arch)"],
    ["Read the vibe", "FashionCLIP embeds the image. Mood photos are translated into fashion vibes; colours come from the pixels.", "#F7D9E0"],
    ["Search 289k pieces", "The vibe vector is matched against FashionCLIP embeddings of the DeepFashion catalogue in Qdrant.", "#EEDFCB"],
    ["Style the results", "Results are diversified, re-ranked towards your palette, explained, and assembled into outfits.", "#D7F0EA"],
  ]
  return (
    <section id="how" className="space-y-6 pt-6">
      <h2 className="font-display text-5xl">How it works</h2>
      <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {steps.map(([t, d, bg], i) => (
          <li key={t} className="space-y-2 rounded-[28px] p-6" style={{ background: bg }}>
            <span className="font-display text-5xl">{i + 1}</span>
            <h3 className="text-lg font-bold">{t}</h3>
            <p className="text-sm text-[var(--mood-muted)]">{d}</p>
          </li>
        ))}
      </ol>
    </section>
  )
}
