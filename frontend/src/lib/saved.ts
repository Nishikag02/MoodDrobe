import { useSyncExternalStore } from "react"
import type { Product } from "./api"

// Saved ("liked") pieces, kept in this browser. They also drive the "For you" recommendations.
const KEY = "mooddrobe.saved.v1"
const listeners = new Set<() => void>()
let cache: Product[] | null = null

function read(): Product[] {
  if (cache) return cache
  try {
    cache = JSON.parse(localStorage.getItem(KEY) ?? "[]") as Product[]
  } catch {
    cache = []
  }
  return cache
}

function write(list: Product[]) {
  cache = list
  try {
    localStorage.setItem(KEY, JSON.stringify(list))
  } catch {
    /* storage full or blocked: keep in memory */
  }
  listeners.forEach((l) => l())
}

export function toggleSaved(p: Product) {
  const list = read()
  write(list.some((x) => x.product_id === p.product_id) ? list.filter((x) => x.product_id !== p.product_id) : [p, ...list].slice(0, 200))
}

export function clearSaved() {
  write([])
}

const subscribe = (l: () => void) => {
  listeners.add(l)
  const onStorage = (e: StorageEvent) => {
    if (e.key === KEY) {
      cache = null
      l()
    }
  }
  window.addEventListener("storage", onStorage)
  return () => {
    listeners.delete(l)
    window.removeEventListener("storage", onStorage)
  }
}

export function useSaved(): Product[] {
  return useSyncExternalStore(subscribe, read, () => [])
}

export function useIsSaved(id: string): boolean {
  return useSaved().some((p) => p.product_id === id)
}
