import type { Product } from "./api"

// Layers that go over another garment (mirrors ml-service/vectordb/garments.py OUTER_LAYERS).
const OUTER = new Set(["Anorak", "Blazer", "Bomber", "Cardigan", "Jacket", "Parka", "Peacoat", "Poncho", "Cape", "Coat", "Kimono"])

export type Outfit = { title: string; pieces: Product[] }

const isOuter = (p: Product) => OUTER.has(p.category_name ?? "")
const typeOf = (p: Product) => (isOuter(p) ? "outer" : p.garment_type ?? "unknown")

/**
 * Assemble wearable looks from a ranked list of items:
 * top + bottom (+ layer), or dress/jumpsuit (+ layer). Items are used once, best-ranked first.
 */
export function buildOutfits(items: Product[], max = 3): Outfit[] {
  const pools: Record<string, Product[]> = { upper: [], lower: [], full: [], outer: [] }
  for (const p of items) pools[typeOf(p)]?.push(p)
  const take = (t: string) => pools[t].shift()

  const looks: Outfit[] = []
  for (let i = 0; i < max; i++) {
    // Alternate separates and one-pieces so the boards don't all look the same.
    const preferFull = i % 2 === 1
    let pieces: Product[] = []
    const separates = pools.upper.length > 0 && pools.lower.length > 0
    const onePiece = pools.full.length > 0
    if ((preferFull && onePiece) || (!separates && onePiece)) {
      pieces = [take("full")!]
    } else if (separates) {
      pieces = [take("upper")!, take("lower")!]
    } else {
      break
    }
    const layer = take("outer")
    if (layer) pieces.unshift(layer)
    looks.push({ title: describe(pieces), pieces })
  }
  return looks
}

function describe(pieces: Product[]): string {
  const names = pieces.map((p) => (p.category_name ?? "piece").toLowerCase())
  if (names.length === 1) return `The ${names[0]}`
  return names.slice(0, -1).join(", ") + " & " + names[names.length - 1]
}

/** Shared colour names across a set of products, most common first. */
export function sharedColours(pieces: Product[]): string[] {
  const counts = new Map<string, number>()
  for (const p of pieces) for (const c of p.color_names ?? []) counts.set(c, (counts.get(c) ?? 0) + 1)
  return [...counts.entries()].sort((a, b) => b[1] - a[1]).map(([c]) => c)
}
