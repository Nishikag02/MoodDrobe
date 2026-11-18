import { Heart } from "lucide-react"
import type { Product } from "@/lib/api"
import { toggleSaved, useIsSaved } from "@/lib/saved"
import { cn } from "@/lib/utils"

export function SaveButton({ product, className, label = false }: { product: Product; className?: string; label?: boolean }) {
  const saved = useIsSaved(product.product_id)
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation()
        toggleSaved(product)
      }}
      aria-pressed={saved}
      aria-label={saved ? "Remove from saved" : "Save"}
      className={cn(
        "flex items-center gap-1.5 rounded-full transition",
        label
          ? "border border-[var(--mood-line)] px-3 py-1.5 text-xs font-medium hover:border-[var(--mood-accent)]"
          : "bg-white/85 p-1.5 text-[#1F1A17] shadow-sm backdrop-blur hover:bg-white",
        className,
      )}
    >
      <Heart className={cn("size-4", saved && "fill-[var(--mood-accent)] text-[var(--mood-accent)]")} />
      {label && (saved ? "Saved" : "Save")}
    </button>
  )
}
