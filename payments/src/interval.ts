/** ISO 8601 repeating interval `R<n>/<start>/<period>`. Soporta períodos P<n>D y P<n>W (suficiente para el MVP). */
export type Interval = { repeats: number | null; start: Date; periodMs: number }

const DAY = 86_400_000

export function parseInterval(s: string): Interval | null {
  const m = /^R(\d*)\/([^/]+)\/P(?:(\d+)W)?(?:(\d+)D)?$/.exec(s)
  if (!m) return null
  const start = new Date(m[2]!)
  const periodMs = (Number(m[3] ?? 0) * 7 + Number(m[4] ?? 0)) * DAY
  if (Number.isNaN(start.getTime()) || periodMs <= 0) return null
  return { repeats: m[1] ? Number(m[1]) : null, start, periodMs }
}

/** Período vigente en `now`: inicio (inclusive) y fin; `expired` si ya pasaron las repeticiones. */
export function currentPeriod(iv: Interval, now: Date) {
  const t = now.getTime() - iv.start.getTime()
  if (t < 0) return { from: iv.start, to: new Date(iv.start.getTime() + iv.periodMs), expired: false }
  const k = Math.floor(t / iv.periodMs)
  const expired = iv.repeats !== null && k >= iv.repeats
  return {
    from: new Date(iv.start.getTime() + k * iv.periodMs),
    to: new Date(iv.start.getTime() + (k + 1) * iv.periodMs),
    expired,
  }
}
