// Client for the MoodDrobe ML service (FastAPI, ml-service/recommend_server.py).
// By default the Vite dev server proxies /ml -> http://127.0.0.1:8000 (see vite.config.ts),
// so the browser never needs CORS. Set VITE_API_URL to call another server directly.

export const API_BASE: string = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") || "/ml"

export type Swatch = { hex: string; weight?: number; name?: string }
export type VibeScore = { vibe: string; score: number }

export type Product = {
  product_id: string
  score: number
  category?: string | null
  category_name?: string | null
  garment_type?: "upper" | "lower" | "full" | string | null
  subcategory?: string | null
  color?: string | null
  pattern?: string | null
  tags?: string[] | null
  color_names?: string[] | null
  palette?: string[] | null
  image_url: string
  reason?: string
  why?: string[]
  match?: number
  color_match?: number
}

export type InputReading = {
  file?: string
  kind: "clothing" | "mood"
  clothing_probability?: number
  read_as?: VibeScore[]
  scene?: string
  fashion_reading?: string
  colors?: Swatch[]
}

export type Recommendation = {
  inputs?: InputReading[]
  your_style?: Product[]
  closest_matches?: Product[]
  complete_the_look?: Product[]
  detected?: { garment_type: string; category: string | null; confidence: number } | null
  vibes?: VibeScore[]
  attributes?: { attribute: string; type: string; score: number }[]
  query_colors?: Swatch[]
  timings_ms?: Record<string, number>
}

export type Options = {
  attributes: { name: string; type: string }[]
  colors: { name: string; hex: string }[]
  vibes: string[]
}

export type Filters = {
  tags: string[]
  avoid_tags: string[]
  only_colors: string[]
  colors: string[] // colours to lean towards (soft re-rank)
  diversity: number
}

export const emptyFilters: Filters = { tags: [], avoid_tags: [], only_colors: [], colors: [], diversity: 0.35 }

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function handle<T>(res: Response): Promise<T> {
  if (res.ok) return (await res.json()) as T
  let detail = `Request failed (${res.status})`
  try {
    const body = await res.json()
    if (typeof body?.detail === "string") detail = body.detail
    else if (Array.isArray(body?.detail)) detail = body.detail.map((d: { msg?: string }) => d.msg).join("; ")
  } catch {
    /* not JSON */
  }
  if (res.status === 502 || res.status === 504) detail = "The ML service isn't running. Start it with ml-service\\start_api.ps1 (port 8000)."
  throw new ApiError(detail, res.status)
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, init)
  } catch {
    throw new ApiError("Can't reach the ML service. Is it running on port 8000?", 0)
  }
  return handle<T>(res)
}

export function imageSrc(p: Pick<Product, "image_url" | "product_id">): string {
  const path = p.image_url || `/catalogue/image/${encodeURIComponent(p.product_id)}`
  return path.startsWith("http") ? path : `${API_BASE}${path}`
}

export function getOptions(): Promise<Options> {
  return call<Options>("/recommend/options")
}

export async function health(): Promise<boolean> {
  try {
    await getOptions()
    return true
  } catch {
    return false
  }
}

export function recommendFromImages(files: File[], steer: string, f: Filters, k = 24, mode: "auto" | "clothing" | "mood" = "auto"): Promise<Recommendation> {
  const form = new FormData()
  form.append("mode", mode)
  for (const file of files) form.append("files", file, file.name)
  if (steer.trim()) form.append("steer", steer.trim())
  form.append("k", String(k))
  form.append("diversity", String(f.diversity))
  if (f.tags.length) form.append("tags", f.tags.join(","))
  if (f.avoid_tags.length) form.append("avoid_tags", f.avoid_tags.join(","))
  if (f.only_colors.length) form.append("only_colors", f.only_colors.join(","))
  if (f.colors.length) form.append("colors", f.colors.join(","))
  else form.append("match_colors", "true") // lean towards the photo's own palette
  form.append("color_weight", "0.4")
  return call<Recommendation>("/recommend", { method: "POST", body: form })
}

export function recommendFromVibe(vibe: string, f: Filters, k = 24): Promise<Recommendation> {
  return call<Recommendation>("/recommend/vibe", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      vibe,
      k,
      diversity: f.diversity,
      tags: f.tags,
      avoid_tags: f.avoid_tags,
      only_colors: f.only_colors,
      colors: f.colors,
      color_weight: 0.5,
    }),
  })
}

export function similarTo(productId: string, k = 12): Promise<Recommendation> {
  return call<Recommendation>(`/recommend/similar/${encodeURIComponent(productId)}?k=${k}&match_colors=true&color_weight=0.3`)
}

export function recommendForYou(likedIds: string[], f: Filters, k = 24): Promise<Recommendation> {
  return call<Recommendation>("/recommend/for-you", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      liked_ids: likedIds.slice(0, 200),
      k,
      diversity: f.diversity,
      tags: f.tags,
      avoid_tags: f.avoid_tags,
      only_colors: f.only_colors,
      colors: f.colors,
    }),
  })
}
