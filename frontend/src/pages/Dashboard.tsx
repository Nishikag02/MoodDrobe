import { useEffect, useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { Camera, Heart, LogOut, Sparkles, Type } from "lucide-react"
import type { Product } from "@/lib/api"
import { fetchHistory, type HistoryRow } from "@/lib/account"
import { authClient } from "@/lib/auth-client"
import { useSaved } from "@/lib/saved"
import { useCurrentUser } from "@/lib/session"
import { ProductDrawer } from "@/components/mood/ProductDrawer"
import { ProductTile } from "@/components/mood/ProductTile"
import { SiteHeader } from "@/components/mood/SiteHeader"

const CARD = ["var(--mood-arch)", "#F7D9E0", "#EEDFCB", "#D7F0EA"]

export default function Dashboard() {
  const user = useCurrentUser()
  const saved = useSaved()
  const navigate = useNavigate()
  const [history, setHistory] = useState<HistoryRow[] | null>(null)
  const [open, setOpen] = useState<Product | null>(null)

  useEffect(() => {
    fetchHistory().then(setHistory)
  }, [])

  const signOut = async () => {
    await authClient.signOut().catch(() => undefined)
    navigate("/")
  }

  const first = (user?.name || user?.email || "there").split(/[\s@]/)[0]
  const recent = (history ?? []).slice(0, 8)

  return (
    <div className="mood min-h-svh">
      <SiteHeader />
      <main className="mx-auto max-w-[1400px] space-y-12 px-5 py-10 sm:px-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-sm font-semibold text-[var(--mood-accent)]">Your wardrobe</p>
            <h1 className="font-display text-6xl capitalize">Hi, {first}.</h1>
          </div>
          <div className="flex gap-2">
            <Link to="/" className="flex items-center gap-2 rounded-full bg-[var(--mood-ink)] px-4 py-2.5 text-sm font-semibold text-white">
              <Sparkles className="size-4" /> New vibe
            </Link>
            <button type="button" onClick={signOut} className="flex items-center gap-1.5 rounded-full border border-[var(--mood-ink)] px-4 text-sm font-medium hover:bg-white">
              <LogOut className="size-4" /> Sign out
            </button>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <Stat label="Saved pieces" value={saved.length} bg={CARD[0]} />
          <Stat label="Vibes explored" value={history?.length ?? "–"} bg={CARD[1]} />
          <Stat label="Catalogue searched" value="289k" bg={CARD[3]} />
        </div>

        <section className="space-y-4">
          <h2 className="mood-underline text-xl font-bold">Recent vibes</h2>
          {recent.length ? (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {recent.map((h, i) => {
                const label = h.scene || h.text
                const canReplay = h.kind === "vibe" && h.text
                const body = (
                  <>
                    <span className="flex items-center gap-1.5 text-xs text-[var(--mood-muted)]">
                      {h.kind === "photo" ? <Camera className="size-3.5" /> : <Type className="size-3.5" />}
                      {h.kind === "photo" ? "Photo" : "Typed vibe"}
                      {when(h) && <> · {when(h)}</>}
                    </span>
                    <span className="font-display mt-2 block text-2xl capitalize">{label}</span>
                  </>
                )
                return canReplay ? (
                  <Link key={i} to={`/?vibe=${encodeURIComponent(h.text)}`} className="block rounded-[24px] p-5 transition hover:-translate-y-0.5" style={{ background: CARD[i % 4] }}>
                    {body}
                  </Link>
                ) : (
                  <div key={i} className="rounded-[24px] p-5" style={{ background: CARD[i % 4] }}>
                    {body}
                  </div>
                )
              })}
            </div>
          ) : (
            <p className="text-sm text-[var(--mood-muted)]">
              {history === null ? "Loading…" : "Your searches will show up here. Try one in the studio."}
            </p>
          )}
        </section>

        <section className="space-y-4">
          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <h2 className="mood-underline text-xl font-bold">Saved picks</h2>
            {saved.length > 0 && (
              <Link to="/saved" className="text-sm font-medium underline underline-offset-4">
                Style me from my saves →
              </Link>
            )}
          </div>
          {saved.length ? (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-6">
              {saved.slice(0, 12).map((p, i) => (
                <ProductTile key={p.product_id} product={p} onOpen={setOpen} index={i} />
              ))}
            </div>
          ) : (
            <p className="flex items-center gap-2 text-sm text-[var(--mood-muted)]">
              <Heart className="size-4" /> Tap the heart on any piece to save it to your account.
            </p>
          )}
        </section>
      </main>
      <ProductDrawer product={open} onClose={() => setOpen(null)} onOpen={setOpen} />
    </div>
  )
}

function Stat({ label, value, bg }: { label: string; value: string | number; bg: string }) {
  return (
    <div className="rounded-[24px] p-5" style={{ background: bg }}>
      <p className="font-display text-5xl">{value}</p>
      <p className="text-sm text-[var(--mood-muted)]">{label}</p>
    </div>
  )
}

function when(h: HistoryRow): string | null {
  const t = h.created_at ?? h.createdAt
  if (!t) return null
  const d = new Date(t)
  if (Number.isNaN(d.getTime())) return null
  const mins = Math.round((Date.now() - d.getTime()) / 60000)
  if (mins < 1) return "just now"
  if (mins < 60) return `${mins} min ago`
  if (mins < 1440) return `${Math.round(mins / 60)} h ago`
  return d.toLocaleDateString()
}
