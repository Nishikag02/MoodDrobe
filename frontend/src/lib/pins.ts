import { useSyncExternalStore } from "react"

// Pinboard pins, stored in this browser as small JPEG data URLs so the board survives a reload.
export type Pin = { id: string; src: string; name: string; w: number; h: number; selected: boolean; addedAt: number }

const KEY = "mooddrobe.pins.v1"
const MAX_PINS = 40
const listeners = new Set<() => void>()
let cache: Pin[] | null = null

function read(): Pin[] {
  if (cache) return cache
  try {
    cache = JSON.parse(localStorage.getItem(KEY) ?? "[]") as Pin[]
  } catch {
    cache = []
  }
  return cache
}

function write(list: Pin[]) {
  cache = list
  try {
    localStorage.setItem(KEY, JSON.stringify(list))
  } catch {
    // Storage full: keep the newest half persisted, all in memory.
    try {
      localStorage.setItem(KEY, JSON.stringify(list.slice(0, Math.ceil(list.length / 2))))
    } catch {
      /* give up persisting */
    }
  }
  listeners.forEach((l) => l())
}

async function shrink(file: File, max = 640): Promise<{ src: string; w: number; h: number }> {
  const url = URL.createObjectURL(file)
  try {
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const i = new Image()
      i.onload = () => resolve(i)
      i.onerror = reject
      i.src = url
    })
    const scale = Math.min(1, max / Math.max(img.naturalWidth, img.naturalHeight))
    const w = Math.max(1, Math.round(img.naturalWidth * scale))
    const h = Math.max(1, Math.round(img.naturalHeight * scale))
    const c = document.createElement("canvas")
    c.width = w
    c.height = h
    c.getContext("2d")!.drawImage(img, 0, 0, w, h)
    return { src: c.toDataURL("image/jpeg", 0.82), w, h }
  } finally {
    URL.revokeObjectURL(url)
  }
}

export async function addPins(files: File[] | FileList) {
  const images = [...files].filter((f) => f.type.startsWith("image/"))
  const made: Pin[] = []
  for (const f of images) {
    try {
      const s = await shrink(f)
      made.push({ id: crypto.randomUUID?.() ?? String(Date.now() + Math.random()), name: f.name, selected: true, addedAt: Date.now(), ...s })
    } catch {
      /* skip unreadable files */
    }
  }
  write([...made, ...read()].slice(0, MAX_PINS))
}

export const togglePin = (id: string) => write(read().map((p) => (p.id === id ? { ...p, selected: !p.selected } : p)))
export const removePin = (id: string) => write(read().filter((p) => p.id !== id))
export const selectAll = (on: boolean) => write(read().map((p) => ({ ...p, selected: on })))
export const clearPins = () => write([])

export async function pinToFile(p: Pin): Promise<File> {
  const blob = await (await fetch(p.src)).blob()
  return new File([blob], p.name.replace(/\.\w+$/, "") + ".jpg", { type: "image/jpeg" })
}

const subscribe = (l: () => void) => {
  listeners.add(l)
  return () => listeners.delete(l)
}

export function usePins(): Pin[] {
  return useSyncExternalStore(subscribe, read, () => [])
}
