import type { Product } from "@/lib/api"
import { ProductImage } from "./ProductCard"
import { SaveButton } from "./SaveButton"

/** Minimal catalogue tile: photo, category and the first reason it was picked. */
export function ProductTile({ product, onOpen, index = 0 }: { product: Product; onOpen: (p: Product) => void; index?: number }) {
  const why = (product.why ?? []).find((w) => w && w !== product.reason) ?? product.reason
  return (
    <div className="mood-rise group relative" style={{ animationDelay: `${Math.min(index, 12) * 30}ms` }}>
      <SaveButton product={product} className="absolute top-2 right-2 z-10 opacity-0 transition group-hover:opacity-100 focus-visible:opacity-100 [&[aria-pressed=true]]:opacity-100" />
      <button type="button" onClick={() => onOpen(product)} className="block w-full text-left">
        <span className="block overflow-hidden rounded-md shadow-[0_6px_18px_-10px_rgba(42,11,48,0.5)]">
          <ProductImage product={product} className="aspect-[3/4] w-full transition duration-500 group-hover:scale-[1.04]" />
        </span>
        <span className="mt-1.5 block text-sm font-medium capitalize">{product.category_name ?? "Piece"}</span>
        {why && <span className="line-clamp-1 block text-xs text-[var(--mood-muted)]">{why}</span>}
      </button>
    </div>
  )
}
