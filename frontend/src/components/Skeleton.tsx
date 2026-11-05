import type { CSSProperties } from 'react'

/** Bloque gris animado que ocupa el lugar del contenido mientras carga (evita saltos y pantallas vacías). */
export function Skeleton({ width = '100%', height = 14, radius = 8, style }: {
  width?: number | string; height?: number | string; radius?: number; style?: CSSProperties
}) {
  return <span className="skeleton" aria-hidden="true" style={{ width, height, borderRadius: radius, ...style }} />
}

export function PageSkeleton() {
  return (
    <div className="page-skeleton" role="status" aria-live="polite" aria-label="Cargando">
      <Skeleton width={110} height={10} />
      <Skeleton width="42%" height={28} />
      <Skeleton width="58%" height={12} />
      <div className="skeleton-grid">
        {[0, 1, 2, 3].map((item) => <Skeleton key={item} height={74} radius={10} />)}
      </div>
      <Skeleton height={260} radius={11} />
    </div>
  )
}

export function ChartSkeleton({ bars = 6 }: { bars?: number }) {
  return (
    <div className="chart-skeleton" role="status" aria-live="polite" aria-label="Cargando gráfico">
      {Array.from({ length: bars }, (_, index) => (
        <Skeleton key={index} width={`${88 - index * 11}%`} height={22} radius={6} />
      ))}
    </div>
  )
}

export function TableSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div className="chart-skeleton" role="status" aria-live="polite" aria-label="Cargando tabla">
      {Array.from({ length: rows }, (_, index) => <Skeleton key={index} height={18} radius={5} />)}
    </div>
  )
}
