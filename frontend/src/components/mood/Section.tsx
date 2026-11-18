export function Section({ title, subtitle, aside, children }: { title: string; subtitle?: string; aside?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="font-display text-3xl">{title}</h2>
          {subtitle && <p className="text-sm text-[var(--mood-muted)]">{subtitle}</p>}
        </div>
        {aside}
      </div>
      {children}
    </section>
  )
}
