// Account features backed by the Express API (/api/saved, /api/history) when the user is signed in.
// Every call is best-effort: if Express or Postgres is down the app keeps working locally.
import type { Product } from "./api"

const opts: RequestInit = { credentials: "include" }

type SavedRow = { product_id: string; image_url?: string | null; category_name?: string | null }
export type HistoryRow = { kind: "vibe" | "photo"; text: string; scene?: string | null; created_at?: string; createdAt?: string }

function rows<T>(body: unknown, ...keys: string[]): T[] {
  if (Array.isArray(body)) return body as T[]
  if (body && typeof body === "object") {
    for (const k of keys) {
      const v = (body as Record<string, unknown>)[k]
      if (Array.isArray(v)) return v as T[]
    }
  }
  return []
}

export async function fetchSaved(): Promise<Product[] | null> {
  try {
    const res = await fetch("/api/saved", opts)
    if (!res.ok) return null
    return rows<SavedRow>(await res.json(), "items", "saved", "data").map((r) => ({
      product_id: String(r.product_id),
      score: 0,
      image_url: r.image_url || `/catalogue/image/${encodeURIComponent(r.product_id)}`,
      category_name: r.category_name ?? null,
    }))
  } catch {
    return null
  }
}

export function postSaved(p: Product, source = "studio") {
  return fetch("/api/saved", {
    ...opts,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ product_id: p.product_id, image_url: p.image_url, category_name: p.category_name ?? null, source }),
  }).catch(() => undefined)
}

export function deleteSaved(id: string) {
  return fetch(`/api/saved/${encodeURIComponent(id)}`, { ...opts, method: "DELETE" }).catch(() => undefined)
}

export async function fetchHistory(): Promise<HistoryRow[]> {
  try {
    const res = await fetch("/api/history?limit=20", opts)
    if (!res.ok) return []
    return rows<HistoryRow>(await res.json(), "items", "history", "data")
  } catch {
    return []
  }
}

export function postHistory(row: HistoryRow) {
  return fetch("/api/history", {
    ...opts,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(row),
  }).catch(() => undefined)
}
