import { Link } from "react-router-dom"

const NotFound = () => {
  return (
    <div className="mood flex min-h-svh flex-col items-center justify-center gap-3 p-6 text-center">
      <p className="font-display text-7xl text-[var(--mood-accent)]">404</p>
      <p className="font-display text-2xl">This page isn't in the wardrobe.</p>
      <Link to="/" className="rounded-full bg-[var(--mood-ink)] px-4 py-2 text-sm font-medium text-[var(--mood-paper)]">
        Back to the studio
      </Link>
    </div>
  )
}

export default NotFound
