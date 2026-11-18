import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { ArrowRight, CircleAlert, ImagePlus, LoaderCircle, RefreshCw, Sparkles, X } from "lucide-react"
import {
  emptyFilters,
  getOptions,
  recommendFromImages,
  recommendFromVibe,
  type Filters,
  type Options,
  type Product,
  type Recommendation,
} from "@/lib/api"
import { buildOutfits } from "@/lib/outfits"
import { extractPalette } from "@/lib/palette"
import { cn } from "@/lib/utils"
import { FilterBar } from "@/components/mood/FilterBar"
import { OutfitBoard } from "@/components/mood/OutfitBoard"
import { ProductCard } from "@/components/mood/ProductCard"
import { ProductDrawer } from "@/components/mood/ProductDrawer"
import { Section } from "@/components/mood/Section"
import { SiteHeader, type Health } from "@/components/mood/SiteHeader"
import { PaletteStrip, VibeReading, type Preview } from "@/components/mood/VibeReading"

const PRESET_VIBES = [
  "cozy coffee shop on a rainy afternoon",
  "beach at golden hour",
  "misty mountain cabin",
  "vintage bookstore",
  "city street at night",
  "old money",
  "dark academia",
  "summer picnic in the park",
]

const LOADING_STEPS = ["Reading colours and light…", "Interpreting the mood…", "Translating it into fashion…", "Searching the catalogue…", "Styling looks…"]

type Query = { kind: "image"; files: File[]; steer: string } | { kind: "vibe"; text: string }

const TYPE_TABS = [
  { key: "all", label: "All" },
  { key: "upper", label: "Tops" },
  { key: "lower", label: "Bottoms" },
  { key: "full", label: "One-pieces" },
] as const

export default function Studio() {
  const [files, setFiles] = useState<File[]>([])
  const [previews, setPreviews] = useState<Preview[]>([])
  const [steer, setSteer] = useState("")
  const [vibe, setVibe] = useState("")
  const [filters, setFilters] = useState<Filters>(emptyFilters)
  const [query, setQuery] = useState<Query | null>(null)
  const [data, setData] = useState<Recommendation | null>(null)
  const [loading, setLoading] = useState(false)
  const [step, setStep] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [health, setHealth] = useState<Health>("checking")
  const [options, setOptions] = useState<Options | null>(null)
  const [open, setOpen] = useState<Product | null>(null)
  const [tab, setTab] = useState<(typeof TYPE_TABS)[number]["key"]>("all")
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const resultsRef = useRef<HTMLDivElement>(null)
  const requestId = useRef(0)

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

  useEffect(() => {
    if (!loading) return
    setStep(0)
    const t = setInterval(() => setStep((s) => Math.min(s + 1, LOADING_STEPS.length - 1)), 1100)
    return () => clearInterval(t)
  }, [loading])

  const addFiles = useCallback(async (incoming: FileList | File[]) => {
    const images = [...incoming].filter((f) => f.type.startsWith("image/")).slice(0, 8)
    if (!images.length) return
    setError(null)
    const next = await Promise.all(
      images.map(async (f) => ({ url: URL.createObjectURL(f), name: f.name, palette: await extractPalette(f) })),
    )
    setFiles((prev) => [...prev, ...images].slice(0, 8))
    setPreviews((prev) => [...prev, ...next].slice(0, 8))
  }, [])

  const removeFile = (i: number) => {
    setFiles((f) => f.filter((_, j) => j !== i))
    setPreviews((p) => {
      URL.revokeObjectURL(p[i].url)
      return p.filter((_, j) => j !== i)
    })
  }

  const run = useCallback(async (q: Query, f: Filters) => {
    const id = ++requestId.current
    setQuery(q)
    setLoading(true)
    setError(null)
    try {
      const res = q.kind === "image" ? await recommendFromImages(q.files, q.steer, f) : await recommendFromVibe(q.text, f)
      if (id !== requestId.current) return
      setData(res)
      setHealth("online")
      setTab("all")
      requestAnimationFrame(() => resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }))
    } catch (e) {
      if (id !== requestId.current) return
      const err = e as Error & { status?: number }
      setError(err.message)
      if (!err.status) setHealth("offline")
    } finally {
      if (id === requestId.current) setLoading(false)
    }
  }, [])

  const submitImages = () => files.length && run({ kind: "image", files, steer }, filters)
  const submitVibe = (text = vibe) => {
    const t = text.trim()
    if (!t) return
    setVibe(t)
    run({ kind: "vibe", text: t }, filters)
  }
  const changeFilters = (f: Filters) => {
    setFilters(f)
    if (query) run(query, f)
  }
  const reset = () => {
    previews.forEach((p) => URL.revokeObjectURL(p.url))
    setFiles([])
    setPreviews([])
    setSteer("")
    setVibe("")
    setData(null)
    setQuery(null)
    setError(null)
    setFilters(emptyFilters)
    window.scrollTo({ top: 0, behavior: "smooth" })
  }

  const yourStyle = data?.your_style ?? []
  const outfits = useMemo(() => buildOutfits(yourStyle, 3), [yourStyle])
  const allResults = useMemo(
    () => [...yourStyle, ...(data?.complete_the_look ?? []), ...(data?.closest_matches ?? [])],
    [yourStyle, data],
  )
  const grid = tab === "all" ? yourStyle : yourStyle.filter((p) => p.garment_type === tab)
  const clientPalette = previews.flatMap((p) => p.palette).slice(0, 6)

  return (
    <div className="mood min-h-svh">
      <SiteHeader health={health} onCheck={checkHealth} onLogo={reset} />

      <main className="mx-auto max-w-6xl space-y-10 px-4 py-8 sm:px-6 sm:py-12">
        {/* Hero + inputs */}
        <section className="grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]">
          <div className="space-y-5 lg:pt-6">
            <p className="text-[11px] font-semibold tracking-[0.2em] text-[var(--mood-accent)] uppercase">Aesthetic-based fashion discovery</p>
            <h1 className="font-display text-5xl leading-[1.02] sm:text-6xl">
              Upload a vibe.
              <br />
              <em className="text-[var(--mood-accent)]">Discover your style.</em>
            </h1>
            <p className="max-w-md text-[var(--mood-muted)]">
              Drop in anything that feels like you — a café, a beach, a moodboard, a film still, or an outfit. MoodDrobe reads its
              colours, mood and texture, and turns them into pieces you can wear.
            </p>
            {health === "offline" && (
              <div className="flex items-start gap-2 rounded-xl border border-[var(--mood-accent)]/40 bg-[var(--mood-accent-soft)] p-3 text-sm">
                <CircleAlert className="mt-0.5 size-4 shrink-0 text-[var(--mood-accent)]" />
                <div>
                  The ML service isn't reachable. Start it in <code>ml-service</code> with{" "}
                  <code className="rounded bg-black/5 px-1">uvicorn recommend_server:app --port 8000</code>, then{" "}
                  <button type="button" className="underline" onClick={checkHealth}>check again</button>.
                </div>
              </div>
            )}
          </div>

          <div className="space-y-4 rounded-3xl border border-[var(--mood-line)] bg-[var(--mood-card)] p-4 shadow-[0_20px_60px_-30px_rgba(60,40,20,0.35)] sm:p-5">
            {/* Dropzone */}
            <div
              onDragOver={(e) => {
                e.preventDefault()
                setDragging(true)
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault()
                setDragging(false)
                addFiles(e.dataTransfer.files)
              }}
              className={cn(
                "rounded-2xl border-2 border-dashed transition",
                dragging ? "border-[var(--mood-accent)] bg-[var(--mood-accent-soft)]" : "border-[var(--mood-line)]",
              )}
            >
              {previews.length === 0 ? (
                <button type="button" onClick={() => inputRef.current?.click()} className="flex w-full flex-col items-center gap-2 px-6 py-12 text-center">
                  <ImagePlus className="size-9 text-[var(--mood-accent)]" />
                  <span className="font-display text-xl">Drop an inspiration image</span>
                  <span className="text-xs text-[var(--mood-muted)]">or click to browse · up to 8 images make a moodboard · JPG, PNG, WebP</span>
                </button>
              ) : (
                <div className="space-y-3 p-3">
                  <div className="grid grid-cols-4 gap-2">
                    {previews.map((p, i) => (
                      <div key={p.url} className="group relative">
                        <img src={p.url} alt={p.name} className="aspect-square w-full rounded-xl object-cover" />
                        <button
                          type="button"
                          onClick={() => removeFile(i)}
                          aria-label={`Remove ${p.name}`}
                          className="absolute top-1 right-1 rounded-full bg-black/60 p-0.5 text-white opacity-0 transition group-hover:opacity-100"
                        >
                          <X className="size-3.5" />
                        </button>
                      </div>
                    ))}
                    {previews.length < 8 && (
                      <button
                        type="button"
                        onClick={() => inputRef.current?.click()}
                        className="flex aspect-square items-center justify-center rounded-xl border border-dashed border-[var(--mood-line)] text-[var(--mood-muted)] hover:border-[var(--mood-muted)]"
                        aria-label="Add another image"
                      >
                        <ImagePlus className="size-5" />
                      </button>
                    )}
                  </div>
                  {clientPalette.length > 0 && <PaletteStrip swatches={clientPalette} />}
                  <input
                    value={steer}
                    onChange={(e) => setSteer(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && submitImages()}
                    placeholder='Optional twist, e.g. "more formal" or "in black"'
                    className="w-full rounded-xl border border-[var(--mood-line)] bg-transparent px-3 py-2 text-sm outline-none focus:border-[var(--mood-accent)]"
                  />
                  <button
                    type="button"
                    disabled={loading}
                    onClick={submitImages}
                    className="flex w-full items-center justify-center gap-2 rounded-xl bg-[var(--mood-ink)] py-3 text-sm font-semibold text-[var(--mood-paper)] transition hover:opacity-90 disabled:opacity-60"
                  >
                    {loading && query?.kind === "image" ? <LoaderCircle className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
                    {previews.length > 1 ? "Style this moodboard" : "Find my style"}
                  </button>
                </div>
              )}
              <input
                ref={inputRef}
                type="file"
                accept="image/*"
                multiple
                hidden
                onChange={(e) => {
                  if (e.target.files) addFiles(e.target.files)
                  e.target.value = ""
                }}
              />
            </div>

            {/* Vibe text */}
            <div className="flex items-center gap-3 text-xs text-[var(--mood-muted)]">
              <span className="h-px flex-1 bg-[var(--mood-line)]" /> or describe a vibe <span className="h-px flex-1 bg-[var(--mood-line)]" />
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault()
                submitVibe()
              }}
              className="flex gap-2"
            >
              <input
                value={vibe}
                onChange={(e) => setVibe(e.target.value)}
                placeholder="e.g. rainy day in Paris"
                maxLength={200}
                className="min-w-0 flex-1 rounded-xl border border-[var(--mood-line)] bg-transparent px-3 py-2.5 text-sm outline-none focus:border-[var(--mood-accent)]"
              />
              <button
                type="submit"
                disabled={loading || !vibe.trim()}
                className="flex items-center gap-1 rounded-xl bg-[var(--mood-accent)] px-4 text-sm font-semibold text-white disabled:opacity-50"
              >
                {loading && query?.kind === "vibe" ? <LoaderCircle className="size-4 animate-spin" /> : <ArrowRight className="size-4" />}
                Go
              </button>
            </form>
            <div className="flex flex-wrap gap-1.5">
              {PRESET_VIBES.map((v) => (
                <button
                  key={v}
                  type="button"
                  onClick={() => submitVibe(v)}
                  disabled={loading}
                  className="rounded-full border border-[var(--mood-line)] px-2.5 py-1 text-xs hover:border-[var(--mood-accent)] hover:text-[var(--mood-accent)] disabled:opacity-50"
                >
                  {v}
                </button>
              ))}
            </div>
          </div>
        </section>

        {/* Results */}
        <div ref={resultsRef} className="scroll-mt-20 space-y-8">
          {error && (
            <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-[var(--mood-accent)]/40 bg-[var(--mood-accent-soft)] p-4 text-sm">
              <CircleAlert className="size-4 text-[var(--mood-accent)]" />
              <span className="flex-1">{error}</span>
              {query && (
                <button type="button" onClick={() => run(query, filters)} className="flex items-center gap-1 font-medium underline">
                  <RefreshCw className="size-3.5" /> Try again
                </button>
              )}
            </div>
          )}

          {loading && !data && <LoadingState step={LOADING_STEPS[step]} />}

          {data && (
            <div className={cn("space-y-8 transition-opacity", loading && "opacity-50")}>
              <VibeReading data={data} previews={query?.kind === "image" ? previews : []} vibeText={query?.kind === "vibe" ? query.text : undefined} />

              <FilterBar filters={filters} options={options} results={allResults} onChange={changeFilters} busy={loading} />
              {loading && (
                <p className="flex items-center gap-2 text-sm text-[var(--mood-muted)]">
                  <LoaderCircle className="size-4 animate-spin" /> {LOADING_STEPS[step]}
                </p>
              )}

              {yourStyle.length === 0 && !loading && (
                <p className="rounded-2xl border border-[var(--mood-line)] p-6 text-center text-sm text-[var(--mood-muted)]">
                  Nothing matches all of those filters. Try removing one.
                </p>
              )}

              {(data.complete_the_look?.length ?? 0) > 0 && (
                <Section title="Complete the look" subtitle={`Pieces that pair with your ${data.detected?.category?.toLowerCase() ?? "item"}, ranked by an outfit-compatibility model.`}>
                  <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                    {data.complete_the_look!.slice(0, 8).map((p, i) => (
                      <ProductCard key={p.product_id} product={p} onOpen={setOpen} index={i} />
                    ))}
                  </div>
                </Section>
              )}

              {outfits.length > 0 && (
                <Section title="Outfits for this vibe" subtitle="Looks assembled from your top matches — tap any piece for more like it.">
                  <div className="grid gap-4 md:grid-cols-3">
                    {outfits.map((o, i) => (
                      <OutfitBoard key={o.pieces.map((p) => p.product_id).join()} outfit={o} n={i} onOpen={setOpen} />
                    ))}
                  </div>
                </Section>
              )}

              {yourStyle.length > 0 && (
                <Section
                  title="Your style"
                  subtitle="Pieces that share the look of your inspiration, varied across categories."
                  aside={
                    <div className="flex gap-1 rounded-full border border-[var(--mood-line)] p-0.5 text-xs">
                      {TYPE_TABS.map((t) => (
                        <button
                          key={t.key}
                          type="button"
                          onClick={() => setTab(t.key)}
                          className={cn("rounded-full px-3 py-1", tab === t.key ? "bg-[var(--mood-ink)] text-[var(--mood-paper)]" : "hover:bg-[var(--mood-line)]")}
                        >
                          {t.label}
                        </button>
                      ))}
                    </div>
                  }
                >
                  {grid.length ? (
                    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
                      {grid.map((p, i) => (
                        <ProductCard key={p.product_id} product={p} onOpen={setOpen} index={i} />
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-[var(--mood-muted)]">No pieces of this type in the results.</p>
                  )}
                </Section>
              )}

              {(data.closest_matches?.length ?? 0) > 0 && (
                <Section title="Closest matches" subtitle="The nearest items in the embedding space, without any re-ranking.">
                  <div className="grid grid-cols-3 gap-3 sm:grid-cols-6">
                    {data.closest_matches!.map((p, i) => (
                      <ProductCard key={p.product_id} product={p} onOpen={setOpen} compact index={i} />
                    ))}
                  </div>
                </Section>
              )}

              {data.timings_ms && (
                <p className="text-right text-[11px] text-[var(--mood-muted)]">
                  {Object.entries(data.timings_ms)
                    .map(([k, v]) => `${k} ${Math.round(v)} ms`)
                    .join(" · ")}
                </p>
              )}
            </div>
          )}
        </div>

        {!data && !loading && <HowItWorks />}
        {data && <HowItWorks />}
      </main>

      <footer className="border-t border-[var(--mood-line)] py-6 text-center text-xs text-[var(--mood-muted)]">
        MoodDrobe · FashionCLIP + Qdrant over the DeepFashion catalogue
      </footer>

      <ProductDrawer product={open} onClose={() => setOpen(null)} onOpen={setOpen} />
    </div>
  )
}

function LoadingState({ step }: { step: string }) {
  return (
    <div className="space-y-5">
      <p className="flex items-center gap-2 font-display text-xl">
        <LoaderCircle className="size-5 animate-spin text-[var(--mood-accent)]" /> {step}
      </p>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="space-y-2">
            <div className="mood-shimmer aspect-[3/4] rounded-2xl" />
            <div className="mood-shimmer h-3 w-2/3 rounded" />
          </div>
        ))}
      </div>
    </div>
  )
}

function HowItWorks() {
  const steps = [
    ["Upload anything", "A scene, a room, a moodboard or an outfit. Several images are blended into one moodboard."],
    ["Read the vibe", "FashionCLIP embeds the image. Mood photos are translated into fashion vibes; colours are extracted from the pixels."],
    ["Search the catalogue", "The vibe vector is matched against FashionCLIP embeddings of the DeepFashion catalogue in Qdrant."],
    ["Style the results", "Results are diversified, re-ranked towards your palette, explained, and assembled into outfits."],
  ]
  return (
    <section id="how" className="scroll-mt-20 space-y-5 border-t border-[var(--mood-line)] pt-10">
      <h2 className="font-display text-3xl">How it works</h2>
      <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {steps.map(([t, d], i) => (
          <li key={t} className="space-y-1.5 rounded-2xl border border-[var(--mood-line)] bg-[var(--mood-card)] p-4">
            <span className="font-display text-3xl text-[var(--mood-accent)]">{i + 1}</span>
            <h3 className="font-semibold">{t}</h3>
            <p className="text-sm text-[var(--mood-muted)]">{d}</p>
          </li>
        ))}
      </ol>
    </section>
  )
}
