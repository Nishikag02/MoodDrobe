// Quick in-browser palette so the user sees colours the moment they drop an image,
// before the ML service answers. The service's own palette replaces it when it arrives.
export type ClientSwatch = { hex: string; weight: number }

export async function extractPalette(file: File, count = 5): Promise<ClientSwatch[]> {
  const url = URL.createObjectURL(file)
  try {
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const i = new Image()
      i.onload = () => resolve(i)
      i.onerror = reject
      i.src = url
    })
    const size = 64
    const canvas = document.createElement("canvas")
    canvas.width = size
    canvas.height = size
    const ctx = canvas.getContext("2d", { willReadFrequently: true })
    if (!ctx) return []
    ctx.drawImage(img, 0, 0, size, size)
    const data = ctx.getImageData(0, 0, size, size).data
    // Bucket colours (4 bits per channel), then merge near neighbours.
    const buckets = new Map<number, { r: number; g: number; b: number; n: number }>()
    for (let i = 0; i < data.length; i += 4) {
      const r = data[i], g = data[i + 1], b = data[i + 2]
      const key = ((r >> 4) << 8) | ((g >> 4) << 4) | (b >> 4)
      const e = buckets.get(key) ?? { r: 0, g: 0, b: 0, n: 0 }
      e.r += r; e.g += g; e.b += b; e.n++
      buckets.set(key, e)
    }
    const total = size * size
    const sorted = [...buckets.values()].sort((a, b) => b.n - a.n)
    const picked: { r: number; g: number; b: number; n: number }[] = []
    for (const e of sorted) {
      const c = { r: e.r / e.n, g: e.g / e.n, b: e.b / e.n, n: e.n }
      const near = picked.find((p) => Math.hypot(p.r - c.r, p.g - c.g, p.b - c.b) < 40)
      if (near) near.n += c.n
      else picked.push(c)
      if (picked.length >= count * 3) break
    }
    return picked
      .sort((a, b) => b.n - a.n)
      .slice(0, count)
      .map((c) => ({ hex: toHex(c.r, c.g, c.b), weight: c.n / total }))
  } catch {
    return []
  } finally {
    URL.revokeObjectURL(url)
  }
}

const toHex = (r: number, g: number, b: number) =>
  "#" + [r, g, b].map((v) => Math.round(v).toString(16).padStart(2, "0")).join("").toUpperCase()

/** Black or white text, whichever reads better on this background. */
export function inkOn(hex: string): string {
  const n = parseInt(hex.replace("#", ""), 16)
  const r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255
  return 0.299 * r + 0.587 * g + 0.114 * b > 150 ? "#1F1A17" : "#FFFFFF"
}
