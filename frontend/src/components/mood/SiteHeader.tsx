import { Link, NavLink } from "react-router-dom"
import { Heart } from "lucide-react"
import { authClient } from "@/lib/auth-client"
import { useSaved } from "@/lib/saved"
import { cn } from "@/lib/utils"

export type Health = "checking" | "online" | "offline"

export function SiteHeader({ health, onCheck, onLogo }: { health?: Health; onCheck?: () => void; onLogo?: () => void }) {
  const saved = useSaved()
  const { data: session } = authClient.useSession()
  const nav = ({ isActive }: { isActive: boolean }) =>
    cn("rounded-full px-3 py-1 transition", isActive ? "bg-[var(--mood-ink)] text-[var(--mood-paper)]" : "hover:bg-[var(--mood-line)]")

  return (
    <header className="sticky top-0 z-40 border-b border-[var(--mood-line)] bg-[var(--mood-paper)]/90 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3 sm:px-6">
        <Link to="/" onClick={onLogo} className="font-display text-2xl font-semibold tracking-tight">
          Mood<span className="text-[var(--mood-accent)]">Drobe</span>
        </Link>
        <nav className="ml-2 flex items-center gap-1 text-sm">
          <NavLink to="/" end className={nav}>
            Studio
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
          {session?.user ? (
            <Link to="/dashboard" className="max-w-32 truncate text-xs font-medium">
              {session.user.name || session.user.email}
            </Link>
          ) : (
            <Link
              to="/login"
              className="rounded-full border border-[var(--mood-ink)] px-3 py-1 text-xs font-medium hover:bg-[var(--mood-ink)] hover:text-[var(--mood-paper)]"
            >
              Sign in
            </Link>
          )}
        </div>
      </div>
    </header>
  )
}
