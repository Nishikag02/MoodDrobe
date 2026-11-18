import { Link, NavLink } from "react-router-dom"
import { Heart } from "lucide-react"
import { useSaved, useSavedAccountSync } from "@/lib/saved"
import { useCurrentUser } from "@/lib/session"
import { cn } from "@/lib/utils"

export type Health = "checking" | "online" | "offline"

export type SearchMode = "vibe" | "lookalike"

export function SiteHeader({ health, onCheck, onLogo, mode, onMode }: {
  health?: Health
  onCheck?: () => void
  onLogo?: () => void
  mode?: SearchMode
  onMode?: (m: SearchMode) => void
}) {
  const saved = useSaved()
  const user = useCurrentUser()
  useSavedAccountSync()
  const nav = ({ isActive }: { isActive: boolean }) =>
    cn("rounded-full px-3 py-1 transition", isActive ? "underline decoration-[3px] underline-offset-[6px] decoration-[var(--mood-accent)]" : "hover:bg-[var(--mood-line)]")

  return (
    <header className="sticky top-0 z-40 bg-[var(--mood-tint-soft)]/85 backdrop-blur transition-colors duration-700">
      <div className="mx-auto flex max-w-[1400px] flex-wrap items-center gap-3 px-5 py-4 sm:px-8">
        <Link to="/" onClick={onLogo} className="font-display text-[26px] !tracking-[-0.02em]">
          MoodDrobe
        </Link>
        <nav className="ml-2 flex items-center gap-1 text-sm">
          <NavLink to="/" end className={nav}>
            Studio
          </NavLink>
          <NavLink to="/pinboard" className={nav}>
            Pinboard
          </NavLink>
          <NavLink to="/saved" className={nav}>
            <span className="flex items-center gap-1">
              <Heart className="size-3.5" /> Saved{saved.length > 0 && <span className="text-xs opacity-70">{saved.length}</span>}
            </span>
          </NavLink>
        </nav>
        <div className="ml-auto flex items-center gap-4 text-sm">
          {health && (
            <button type="button" onClick={onCheck} className="hidden items-center gap-1.5 text-xs text-[var(--mood-muted)] sm:flex" title="ML service status — click to re-check">
              <span
                className={cn(
                  "size-2 rounded-full",
                  health === "online" && "bg-[var(--mood-good)]",
                  health === "offline" && "bg-[var(--mood-accent)]",
                  health === "checking" && "animate-pulse bg-[var(--mood-muted)]",
                )}
              />
              {health === "online" ? "Model online" : health === "offline" ? "Model offline" : "Connecting…"}
            </button>
          )}
          {mode && onMode && (
            <div className="flex rounded-full bg-[var(--mood-line)] p-1 text-sm" role="tablist" aria-label="Search mode">
              {(["vibe", "lookalike"] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  role="tab"
                  aria-selected={mode === m}
                  onClick={() => onMode(m)}
                  title={m === "vibe" ? "Any picture: read its mood and style it" : "A clothing photo: find pieces that look like it"}
                  className={cn("rounded-full px-3.5 py-1 font-medium transition", mode === m ? "bg-[var(--mood-ink)] text-white" : "hover:bg-white/60")}
                >
                  {m === "vibe" ? "Vibe" : "Look-alike"}
                </button>
              ))}
            </div>
          )}
          {user ? (
            <Link to="/dashboard" className="max-w-32 truncate text-xs font-medium">
              {user.name || user.email}
            </Link>
          ) : (
            <Link
              to="/login"
              className="rounded-full border border-[var(--mood-ink)] px-3 py-1 text-xs font-medium hover:bg-[var(--mood-ink)] hover:text-white"
            >
              Sign in
            </Link>
          )}
        </div>
      </div>
    </header>
  )
}
