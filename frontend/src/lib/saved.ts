import { useEffect, useSyncExternalStore } from "react"
import type { Product } from "./api"
import { deleteSaved, fetchSaved, postSaved } from "./account"
import { useCurrentUser } from "./session"

// Saved ("liked") pieces. Always kept in this browser; when signed in they are also
// stored in Postgres through the Express API, so they follow the account.
const KEY = "mooddrobe.saved.v1"
const listeners = new Set<() => void>()
let cache: Product[] | null = null
let signedIn = false

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
  const isSaved = list.some((x) => x.product_id === p.product_id)
  write(isSaved ? list.filter((x) => x.product_id !== p.product_id) : [p, ...list].slice(0, 200))
  if (signedIn) {
    if (isSaved) deleteSaved(p.product_id)
    else postSaved(p)
  }
}

export function clearSaved() {
  const list = read()
  write([])
  if (signedIn) list.forEach((p) => deleteSaved(p.product_id))
}

/** Merge the account's saved items with this browser's, and upload any the account lacks. */
async function syncWithAccount() {
  const remote = await fetchSaved()
  if (remote === null) return
  const local = read()
  const remoteIds = new Set(remote.map((p) => p.product_id))
  for (const p of local) if (!remoteIds.has(p.product_id)) postSaved(p, "browser")
  const localById = new Map(local.map((p) => [p.product_id, p]))
  // Prefer the richer local copy (it has colours and reasons) when both exist.
  const merged = [...local, ...remote.filter((p) => !localById.has(p.product_id))]
  write(merged.slice(0, 200))
}

/** Mount once near the root: switches saving to the account when someone signs in. */
export function useSavedAccountSync() {
  const user = useCurrentUser()
  const id = user?.id ?? null
  useEffect(() => {
    signedIn = !!id
    if (id) syncWithAccount()
  }, [id])
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
