/**
 * Velocidad real de los usuarios (Core Web Vitals) sin librerías externas.
 * Envía LCP, CLS, INP aproximado, FCP y TTFB una vez, cuando la pestaña se oculta.
 * El backend solo los escribe en los logs (logger «insights.vitals»).
 */
type VitalName = 'LCP' | 'CLS' | 'INP' | 'FCP' | 'TTFB'

const THRESHOLDS: Record<VitalName, [number, number]> = {
  LCP: [2500, 4000], CLS: [0.1, 0.25], INP: [200, 500], FCP: [1800, 3000], TTFB: [800, 1800],
}

let currentPage = 'inicio'
export function setVitalsPage(page: string) { currentPage = page.slice(0, 40) }

function rating(name: VitalName, value: number) {
  const [good, poor] = THRESHOLDS[name]
  return value <= good ? 'good' : value <= poor ? 'needs-improvement' : 'poor'
}

function send(name: VitalName, value: number) {
  const body = JSON.stringify({
    name, value: Math.round(value * 1000) / 1000, rating: rating(name, value), page: currentPage,
    connection: String((navigator as any).connection?.effectiveType || '').slice(0, 12),
  })
  const sent = navigator.sendBeacon?.('/api/telemetry/vitals', new Blob([body], { type: 'application/json' }))
  if (!sent) fetch('/api/telemetry/vitals', { method: 'POST', body, headers: { 'Content-Type': 'application/json' }, keepalive: true }).catch(() => {})
}

export function reportWebVitals() {
  if (import.meta.env.DEV || typeof PerformanceObserver === 'undefined') return
  const values: Partial<Record<VitalName, number>> = {}
  let layoutShift = 0
  let flushed = false

  const observe = (type: string, handler: (entries: any[]) => void, extra: object = {}) => {
    try {
      new PerformanceObserver((list) => handler(list.getEntries() as any[])).observe({ type, buffered: true, ...extra } as any)
    } catch { /* el navegador no soporta esta métrica */ }
  }

  const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming | undefined
  if (navigation) values.TTFB = navigation.responseStart
  observe('paint', (entries) => { const fcp = entries.find((entry) => entry.name === 'first-contentful-paint'); if (fcp) values.FCP = fcp.startTime })
  observe('largest-contentful-paint', (entries) => { const last = entries[entries.length - 1]; if (last) values.LCP = last.startTime })
  observe('layout-shift', (entries) => {
    for (const entry of entries) if (!entry.hadRecentInput) layoutShift += entry.value
    values.CLS = layoutShift
  })
  observe('event', (entries) => {
    for (const entry of entries) if (entry.interactionId > 0) values.INP = Math.max(values.INP || 0, entry.duration)
  }, { durationThreshold: 40 })

  const flush = () => {
    if (flushed) return
    flushed = true
    for (const [name, value] of Object.entries(values)) if (typeof value === 'number') send(name as VitalName, value)
  }
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') flush() })
  window.addEventListener('pagehide', flush)
}
