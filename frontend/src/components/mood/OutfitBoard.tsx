import type { Product } from "@/lib/api"
import { sharedColours, type Outfit } from "@/lib/outfits"
import { ProductImage } from "./ProductCard"

export function OutfitBoard({ outfit, n, onOpen }: { outfit: Outfit; n: number; onOpen: (p: Product) => void }) {
  const colours = sharedColours(outfit.pieces).slice(0, 3)
  const [hero, ...rest] = outfit.pieces
  return (
    <article className="mood-rise flex flex-col gap-3 rounded-3xl border border-[var(--mood-line)] bg-[var(--mood-card)] p-3" style={{ animationDelay: `${n * 80}ms` }}>
      <div className={rest.length ? "grid grid-cols-2 gap-2" : "grid grid-cols-1"}>
        <button type="button" onClick={() => onOpen(hero)} className={rest.length > 1 ? "row-span-2" : ""}>
          <ProductImage product={hero} className="aspect-[3/4] size-full rounded-2xl" />
        </button>
        {rest.map((p) => (
          <button key={p.product_id} type="button" onClick={() => onOpen(p)}>
            <ProductImage product={p} className={`${rest.length > 1 ? "aspect-square" : "aspect-[3/4]"} size-full rounded-2xl`} />
          </button>
        ))}
      </div>
      <div className="px-1 pb-1">
        <p className="text-[11px] font-medium tracking-[0.14em] text-[var(--mood-muted)] uppercase">Look {n + 1}</p>
        <h4 className="font-display text-lg capitalize">{outfit.title}</h4>
        {colours.length > 0 && <p className="text-xs text-[var(--mood-muted)]">Tied together by {colours.join(", ")}</p>}
      </div>
    </article>
  )
}
