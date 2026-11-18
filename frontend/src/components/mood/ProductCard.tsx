import { useState } from "react"
import { Shirt } from "lucide-react"
import { imageSrc, type Product } from "@/lib/api"
import { cn } from "@/lib/utils"
import { SaveButton } from "./SaveButton"

export function ProductImage({ product, className }: { product: Product; className?: string }) {
  const [failed, setFailed] = useState(false)
  if (failed) {
    return (
      <div className={cn("flex items-center justify-center bg-[var(--mood-line)] text-[var(--mood-muted)]", className)}>
        <Shirt className="size-8" />
      </div>
    )
  }
  return (
    <img
      src={imageSrc(product)}
      alt={product.category_name ?? "Catalogue item"}
      loading="lazy"
      onError={() => setFailed(true)}
      className={cn("object-cover", className)}
    />
  )
}

export function ColourDots({ product, max = 4 }: { product: Product; max?: number }) {
  const hexes = (product.palette ?? []).slice(0, max)
  if (!hexes.length) return null
  return (
    <div className="flex -space-x-1">
      {hexes.map((h) => (
        <span key={h} title={h} className="size-3.5 rounded-full ring-2 ring-[var(--mood-card)]" style={{ background: h }} />
      ))}
    </div>
  )
}

export function ProductCard({ product, onOpen, compact = false, index = 0 }: {
  product: Product
  onOpen: (p: Product) => void
  compact?: boolean
  index?: number
}) {
  const why = (product.why ?? []).filter((w) => w && w !== product.reason)
  const lines = why.length ? why : product.reason ? [product.reason] : []
  return (
    <div
      className="mood-rise group relative flex flex-col overflow-hidden rounded-2xl border border-[var(--mood-line)] bg-[var(--mood-card)] transition hover:-translate-y-0.5 hover:shadow-[0_10px_30px_-12px_rgba(60,40,20,0.35)]"
      style={{ animationDelay: `${Math.min(index, 12) * 35}ms` }}
    >
    <SaveButton product={product} className="absolute top-2 right-2 z-10" />
    <button
      type="button"
      onClick={() => onOpen(product)}
      className="flex flex-col flex-1 flex-col text-left focus-visible:outline-2 focus-visible:outline-[var(--mood-accent)]"
    >
      <div className="relative aspect-[3/4] w-full overflow-hidden bg-[var(--mood-line)]">
        <ProductImage product={product} className="size-full transition duration-500 group-hover:scale-[1.03]" />
      </div>
      <div className={cn("flex flex-1 flex-col gap-1.5 p-3", compact && "p-2.5")}>
        <div className="flex items-center justify-between gap-2">
          <span className="truncate text-sm font-semibold capitalize">{product.category_name ?? "Piece"}</span>
          <ColourDots product={product} />
        </div>
        {!compact && lines.length > 0 && (
          <ul className="space-y-0.5 text-xs leading-snug text-[var(--mood-muted)]">
            {lines.slice(0, 2).map((l) => (
              <li key={l} className="line-clamp-2">· {l}</li>
            ))}
          </ul>
        )}
        {!compact && (product.tags?.length ?? 0) > 0 && (
          <div className="mt-auto flex flex-wrap gap-1 pt-1">
            {product.tags!.slice(0, 3).map((t) => (
              <span key={t} className="rounded-full bg-[var(--mood-accent-soft)] px-2 py-0.5 text-[10px] text-[var(--mood-ink)]">
                {t.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        )}
      </div>
    </button>
    </div>
  )
}
