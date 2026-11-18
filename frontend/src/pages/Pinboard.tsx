import { useEffect, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import { Check, ImagePlus, LoaderCircle, Sparkles, Trash2, X } from "lucide-react"
import { handOffImages } from "@/lib/handoff"
import { addPins, clearPins, pinToFile, removePin, selectAll, togglePin, usePins } from "@/lib/pins"
import { cn } from "@/lib/utils"
import { SiteHeader } from "@/components/mood/SiteHeader"

const MAX_BLEND = 8

export default function Pinboard() {
  const pins = usePins()
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [adding, setAdding] = useState(false)
  const [starting, setStarting] = useState(false)
  const selected = pins.filter((p) => p.selected)

  const add = async (files: FileList | File[]) => {
    setAdding(true)
    await addPins(files)
    setAdding(false)
  }

  useEffect(() => {
    const onPaste = (e: ClipboardEvent) => {
      const files = [...(e.clipboardData?.files ?? [])]
      if (files.length) add(files)
    }
    window.addEventListener("paste", onPaste)
    return () => window.removeEventListener("paste", onPaste)
  }, [])

  const styleBoard = async () => {
    if (!selected.length) return
    setStarting(true)
    const files = await Promise.all(selected.slice(0, MAX_BLEND).map(pinToFile))
    handOffImages(files)
    navigate("/?from=pinboard")
  }

  return (
    <div
      className="mood min-h-svh"
      onDragOver={(e) => {
        e.preventDefault()
        setDragging(true)
      }}
      onDragLeave={(e) => e.currentTarget === e.target && setDragging(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDragging(false)
        add(e.dataTransfer.files)
      }}
    >
      <SiteHeader />
      <input ref={inputRef} type="file" accept="image/*" multiple hidden onChange={(e) => e.target.files && add(e.target.files)} />

      <main className="mx-auto max-w-[1400px] space-y-8 px-5 pt-6 pb-32 sm:px-8">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div className="max-w-2xl space-y-3">
            <h1 className="font-display text-[clamp(3rem,6vw,5.2rem)]">Pin your vibe.</h1>
            <p className="text-lg leading-snug text-[var(--mood-muted)]">
              Collect everything that feels like you, like a Pinterest board: rooms, places, colours, outfits. Pick the pins that belong together and
              MoodDrobe blends them into one vibe and styles outfits from it.
            </p>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className="flex items-center gap-2 rounded-full bg-[var(--mood-ink)] px-4 py-2.5 text-sm font-semibold text-white"
            >
              {adding ? <LoaderCircle className="size-4 animate-spin" /> : <ImagePlus className="size-4" />} Add pins
            </button>
            {pins.length > 0 && (
              <button type="button" onClick={clearPins} className="flex items-center gap-1 rounded-full border border-[var(--mood-ink)] px-3 text-sm hover:bg-white">
                <Trash2 className="size-4" /> Clear board
              </button>
            )}
          </div>
        </div>

        {pins.length === 0 ? (
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            className={cn(
              "flex w-full flex-col items-center justify-center gap-2 rounded-[32px] border-2 border-dashed border-[var(--mood-ink)]/60 py-24 text-center transition",
              dragging ? "bg-[#CDB0F7]" : "bg-[var(--mood-arch)] hover:bg-[#D5BCF8]",
            )}
          >
            <ImagePlus className="size-8 opacity-70" />
            <span className="text-2xl font-bold">Start your board</span>
            <span className="max-w-sm text-sm text-[var(--mood-muted)]">Drop in several photos, choose files, or paste images. They stay in this browser.</span>
          </button>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <span>
                <strong>{selected.length}</strong> of {pins.length} pins selected
                {selected.length > MAX_BLEND && <span className="text-[var(--mood-muted)]"> (the first {MAX_BLEND} are blended)</span>}
              </span>
              <button type="button" className="underline underline-offset-4" onClick={() => selectAll(true)}>Select all</button>
              <button type="button" className="underline underline-offset-4" onClick={() => selectAll(false)}>Clear selection</button>
              {dragging && <span className="font-semibold text-[var(--mood-accent)]">Drop to pin</span>}
            </div>

            {/* Masonry board */}
            <div className="columns-2 gap-4 sm:columns-3 lg:columns-4 xl:columns-5">
              {pins.map((p, i) => (
                <figure key={p.id} className="mood-rise group relative mb-4 break-inside-avoid" style={{ animationDelay: `${Math.min(i, 10) * 30}ms` }}>
                  <button
                    type="button"
                    onClick={() => togglePin(p.id)}
                    aria-pressed={p.selected}
                    aria-label={p.selected ? `Unselect ${p.name}` : `Select ${p.name}`}
                    className={cn(
                      "block w-full overflow-hidden rounded-2xl transition",
                      p.selected ? "ring-4 ring-[var(--mood-ink)] ring-offset-2 ring-offset-[var(--mood-tint-soft)]" : "opacity-60 hover:opacity-100",
                    )}
                  >
                    <img src={p.src} alt={p.name} className="w-full" style={{ aspectRatio: `${p.w} / ${p.h}` }} />
                  </button>
                  <span
                    className={cn(
                      "pointer-events-none absolute top-2 left-2 flex size-7 items-center justify-center rounded-full border-2 transition",
                      p.selected ? "border-[var(--mood-ink)] bg-[var(--mood-ink)] text-white" : "border-white bg-black/20 text-transparent",
                    )}
                  >
                    <Check className="size-4" />
                  </span>
                  <button
                    type="button"
                    onClick={() => removePin(p.id)}
                    aria-label={`Remove ${p.name}`}
                    className="absolute top-2 right-2 rounded-full bg-white/90 p-1 opacity-0 shadow transition group-hover:opacity-100"
                  >
                    <X className="size-4" />
                  </button>
                </figure>
              ))}
              <button
                type="button"
                onClick={() => inputRef.current?.click()}
                className="mb-4 flex aspect-[3/4] w-full break-inside-avoid flex-col items-center justify-center gap-1 rounded-2xl border-2 border-dashed border-[var(--mood-line)] text-sm text-[var(--mood-muted)] hover:border-[var(--mood-ink)]"
              >
                <ImagePlus className="size-6" /> Add more
              </button>
            </div>
          </>
        )}
      </main>

      {/* Floating action bar */}
      {pins.length > 0 && (
        <div className="fixed inset-x-0 bottom-5 z-30 flex justify-center px-4">
          <div className="flex items-center gap-3 rounded-full bg-[var(--mood-ink)] py-2 pr-2 pl-3 text-white shadow-[0_18px_40px_-12px_rgba(42,11,48,0.6)]">
            <div className="flex -space-x-3">
              {selected.slice(0, 5).map((p) => (
                <img key={p.id} src={p.src} alt="" className="size-9 rounded-full border-2 border-[var(--mood-ink)] object-cover" />
              ))}
            </div>
            <span className="text-sm">{selected.length ? `${Math.min(selected.length, MAX_BLEND)} pins in this vibe` : "Select some pins"}</span>
            <button
              type="button"
              onClick={styleBoard}
              disabled={!selected.length || starting}
              className="flex items-center gap-2 rounded-full bg-[var(--mood-sun)] px-4 py-2 text-sm font-bold text-[var(--mood-ink)] disabled:opacity-50"
            >
              {starting ? <LoaderCircle className="size-4 animate-spin" /> : <Sparkles className="size-4" />} Style this board
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
