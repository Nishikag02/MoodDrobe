import type { Product } from "@/lib/api"
import { sharedColours, type Outfit } from "@/lib/outfits"
import { ProductImage } from "./ProductCard"

const TILTS = ["-rotate-3", "rotate-2", "-rotate-1", "rotate-3"]
const OFFSETS = ["", "-ml-6 mt-4", "-ml-5 -mt-2", "-ml-6 mt-6"]

/** One look as a collage card: label on the left, slightly tilted photos overlapping on the right. */
export function OutfitBoard({ outfit, n, onOpen, background }: {
  outfit: Outfit
  n: number
  onOpen: (p: Product) => void
  background?: string
}) {
  const colours = sharedColours(outfit.pieces).slice(0, 3)
  return (
    <article
      className="mood-rise flex flex-col gap-4 rounded-[28px] p-5 sm:flex-row sm:items-center sm:gap-8 sm:p-6"
      style={{ animationDelay: `${n * 90}ms`, background: background ?? "var(--mood-card)" }}
    >
      <div className="w-32 shrink-0">
        <p className="text-lg font-bold">Look {n + 1}</p>
        <p className="text-sm text-[var(--mood-muted)] capitalize">{outfit.pieces.map((p) => p.category_name ?? "piece").join(", ")}</p>
        {colours.length > 0 && <p className="mt-1 text-xs text-[var(--mood-muted)]">in {colours.join(", ")}</p>}
      </div>
      <div className="flex items-start py-2 pl-1">
        {outfit.pieces.map((p, i) => (
          <button
            key={p.product_id}
            type="button"
            onClick={() => onOpen(p)}
            title={p.category_name ?? "Open"}
            className={`${TILTS[i % 4]} ${i ? OFFSETS[i % 4] : ""} relative w-28 shrink-0 bg-white p-1.5 shadow-[0_8px_24px_-8px_rgba(42,11,48,0.45)] transition hover:z-10 hover:scale-105 hover:rotate-0 sm:w-36`}
            style={{ zIndex: outfit.pieces.length - i }}
          >
            <ProductImage product={p} className="aspect-[3/4] w-full" />
          </button>
        ))}
      </div>
    </article>
  )
}
