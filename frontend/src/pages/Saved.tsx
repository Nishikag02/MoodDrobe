import { useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { CircleAlert, Heart, LoaderCircle, Sparkles, Trash2 } from "lucide-react"
import { emptyFilters, recommendForYou, type Product, type Recommendation } from "@/lib/api"
import { buildOutfits } from "@/lib/outfits"
import { clearSaved, useSaved } from "@/lib/saved"
import { OutfitBoard } from "@/components/mood/OutfitBoard"
import { ProductTile } from "@/components/mood/ProductTile"
import { ProductDrawer } from "@/components/mood/ProductDrawer"
import { Section } from "@/components/mood/Section"
import { SiteHeader } from "@/components/mood/SiteHeader"

export default function Saved() {
  const saved = useSaved()
  const [open, setOpen] = useState<Product | null>(null)
  const [data, setData] = useState<Recommendation | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const forYou = async () => {
    setLoading(true)
    setError(null)
    try {
      setData(await recommendForYou(saved.map((p) => p.product_id), emptyFilters))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const picks = data?.your_style ?? []
  const outfits = useMemo(() => buildOutfits(picks, 3), [picks])
  const vibes = data?.vibes ?? []

  return (
    <div className="mood min-h-svh">
      <SiteHeader />
      <main className="mx-auto max-w-[1400px] space-y-10 px-5 py-10 sm:px-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-[11px] font-semibold tracking-[0.2em] text-[var(--mood-accent)] uppercase">Your wardrobe board</p>
            <h1 className="font-display text-6xl">Saved pieces</h1>
            <p className="text-[var(--mood-muted)]">
              Tap the heart on any item to keep it here. MoodDrobe learns your taste from what you save.
            </p>
          </div>
          {saved.length > 0 && (
            <div className="flex gap-2">
              <button
                type="button"
                onClick={forYou}
                disabled={loading}
                className="flex items-center gap-2 rounded-xl bg-[var(--mood-ink)] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
              >
                {loading ? <LoaderCircle className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
                Style me from my saves
              </button>
              <button
                type="button"
                onClick={() => {
                  clearSaved()
                  setData(null)
                }}
                className="flex items-center gap-1 rounded-xl border border-[var(--mood-line)] px-3 text-xs text-[var(--mood-muted)] hover:text-[var(--mood-ink)]"
              >
                <Trash2 className="size-3.5" /> Clear
              </button>
            </div>
          )}
        </div>

        {saved.length === 0 ? (
          <div className="flex flex-col items-center gap-3 rounded-3xl border border-dashed border-[var(--mood-line)] py-16 text-center">
            <Heart className="size-8 text-[var(--mood-accent)]" />
            <p className="font-display text-2xl">Nothing saved yet</p>
            <p className="max-w-sm text-sm text-[var(--mood-muted)]">Upload a vibe in the studio and save the pieces you love.</p>
            <Link to="/" className="mt-2 rounded-full bg-[var(--mood-ink)] px-4 py-2 text-sm font-medium text-white">
              Go to the studio
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-6">
            {saved.map((p, i) => (
              <ProductTile key={p.product_id} product={p} onOpen={setOpen} index={i} />
            ))}
          </div>
        )}

        {error && (
          <p className="flex items-center gap-2 rounded-2xl bg-[var(--mood-accent-soft)] p-4 text-sm">
            <CircleAlert className="size-4 text-[var(--mood-accent)]" /> {error}
          </p>
        )}

        {data && (
          <div className="space-y-8 border-t border-[var(--mood-line)] pt-10">
            <div className="space-y-2">
              <h2 className="font-display text-4xl">Picked for you</h2>
              {vibes.length > 0 && (
                <p className="text-[var(--mood-muted)]">
                  Your saves lean{" "}
                  {vibes.map((v, i) => (
                    <span key={v.vibe}>
                      <strong className="text-[var(--mood-ink)] capitalize">{v.vibe}</strong>
                      {i < vibes.length - 2 ? ", " : i === vibes.length - 2 ? " and " : ""}
                    </span>
                  ))}
                  .
                </p>
              )}
            </div>
            {outfits.length > 0 && (
              <Section title="Looks built from your taste">
                <div className="space-y-4">
                  {outfits.map((o, i) => (
                    <OutfitBoard key={o.pieces.map((p) => p.product_id).join()} outfit={o} n={i} onOpen={setOpen} background={["#F7D9E0", "#EEDFCB", "#D7F0EA"][i % 3]} />
                  ))}
                </div>
              </Section>
            )}
            {picks.length > 0 && (
              <Section title="More you'll like">
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-6">
                  {picks.map((p, i) => (
                    <ProductTile key={p.product_id} product={p} onOpen={setOpen} index={i} />
                  ))}
                </div>
              </Section>
            )}
          </div>
        )}
      </main>
      <ProductDrawer product={open} onClose={() => setOpen(null)} onOpen={setOpen} />
    </div>
  )
}
