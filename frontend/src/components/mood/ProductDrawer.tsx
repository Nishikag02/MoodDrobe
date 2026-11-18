import { useEffect, useState } from "react"
import { LoaderCircle, X } from "lucide-react"
import { similarTo, type Product, type Recommendation } from "@/lib/api"
import { ProductImage } from "./ProductCard"
import { ProductTile } from "./ProductTile"
import { SaveButton } from "./SaveButton"

export function ProductDrawer({ product, onClose, onOpen }: {
  product: Product | null
  onClose: () => void
  onOpen: (p: Product) => void
}) {
  const [data, setData] = useState<Recommendation | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!product) return
    let alive = true
    setData(null)
    setError(null)
    similarTo(product.product_id)
      .then((d) => alive && setData(d))
      .catch((e: Error) => alive && setError(e.message))
    return () => {
      alive = false
    }
  }, [product])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose()
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose])

  if (!product) return null
  const pairs = data?.complete_the_look ?? []
  const similar = (data?.your_style ?? []).slice(0, 8)
  const why = product.why?.length ? product.why : product.reason ? [product.reason] : []

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-label="Product details">
      <button type="button" aria-label="Close" className="absolute inset-0 bg-black/40 backdrop-blur-[2px]" onClick={onClose} />
      <aside className="mood relative flex h-full w-full max-w-2xl flex-col overflow-y-auto border-l border-[var(--mood-line)] shadow-2xl">
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-[var(--mood-line)] bg-[var(--mood-paper)]/95 px-5 py-3 backdrop-blur">
          <span className="font-display text-xl capitalize">{product.category_name ?? "Piece"}</span>
          <button type="button" onClick={onClose} className="rounded-full p-1.5 hover:bg-[var(--mood-line)]" aria-label="Close">
            <X className="size-5" />
          </button>
        </div>

        <div className="grid gap-5 p-5 sm:grid-cols-[220px_1fr]">
          <ProductImage product={product} className="aspect-[3/4] w-full rounded-2xl" />
          <div className="space-y-3 text-sm">
            <SaveButton product={product} label className="w-fit" />
            {why.length > 0 && (
              <div>
                <h3 className="mb-1 text-[11px] font-semibold tracking-[0.14em] text-[var(--mood-muted)] uppercase">Why it's here</h3>
                <ul className="space-y-1">
                  {why.map((w) => (
                    <li key={w}>· {w}</li>
                  ))}
                </ul>
              </div>
            )}
            {(product.palette?.length ?? 0) > 0 && (
              <div>
                <h3 className="mb-1 text-[11px] font-semibold tracking-[0.14em] text-[var(--mood-muted)] uppercase">Colours</h3>
                <div className="flex flex-wrap gap-2">
                  {product.palette!.slice(0, 5).map((h, i) => (
                    <span key={h} className="flex items-center gap-1.5 text-xs">
                      <span className="size-5 rounded-md border border-black/10" style={{ background: h }} />
                      {product.color_names?.[i] ?? h}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {(product.tags?.length ?? 0) > 0 && (
              <div>
                <h3 className="mb-1 text-[11px] font-semibold tracking-[0.14em] text-[var(--mood-muted)] uppercase">Attributes</h3>
                <div className="flex flex-wrap gap-1">
                  {product.tags!.map((t) => (
                    <span key={t} className="rounded-full bg-[var(--mood-accent-soft)] px-2 py-0.5 text-xs">{t.replace(/_/g, " ")}</span>
                  ))}
                </div>
              </div>
            )}
            <p className="text-xs text-[var(--mood-muted)]">
              Item {product.product_id}
              {typeof product.score === "number" && <> · similarity {product.score.toFixed(3)}</>}
            </p>
          </div>
        </div>

        <div className="space-y-6 px-5 pb-8">
          {!data && !error && (
            <p className="flex items-center gap-2 text-sm text-[var(--mood-muted)]">
              <LoaderCircle className="size-4 animate-spin" /> Finding pieces that go with it…
            </p>
          )}
          {error && <p className="text-sm text-[var(--mood-accent)]">{error}</p>}
          {pairs.length > 0 && (
            <section>
              <h3 className="font-display mb-2 text-lg">Complete the look</h3>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {pairs.slice(0, 8).map((p, i) => (
                  <ProductTile key={p.product_id} product={p} onOpen={onOpen} index={i} />
                ))}
              </div>
            </section>
          )}
          {similar.length > 0 && (
            <section>
              <h3 className="font-display mb-2 text-lg">More like this</h3>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {similar.map((p, i) => (
                  <ProductTile key={p.product_id} product={p} onOpen={onOpen} index={i} />
                ))}
              </div>
            </section>
          )}
        </div>
      </aside>
    </div>
  )
}
