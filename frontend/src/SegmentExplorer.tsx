import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, LoaderCircle } from 'lucide-react'
import { getJson } from './http'

type Freq = { Categoría: string; Menciones: number; '%': number }
type SegmentRow = { segment: string; base: number; [category: string]: number | string }
type Props = {
  classification: { id: string; question: string; categories: string[] }
  columns: string[]
  freq: Freq[]
  onNotice: (n: { text: string; error?: boolean }) => void
}

const MAX_CATEGORIES = 8
const MAX_SEGMENTS = 12
const LOW_BASE = 30      // por debajo de esta base la lectura es orientativa
const DIFF_POINTS = 0.1  // 10 puntos de diferencia frente al total

const pct = (value: number) => `${Math.round(value * 100)}%`

/** Mapa de calor: filas = grupos, columnas = categorías, color = % del grupo. */
export default function SegmentExplorer({ classification, columns, freq, onNotice }: Props) {
  const [column, setColumn] = useState('')
  const [rows, setRows] = useState<SegmentRow[]>([])
  const [loadedColumn, setLoadedColumn] = useState('')
  const [loading, setLoading] = useState(false)
  const [allCategories, setAllCategories] = useState(false)
  const [allSegments, setAllSegments] = useState(false)

  useEffect(() => { setRows([]); setLoadedColumn(''); setAllCategories(false); setAllSegments(false) }, [classification.id])

  async function calculate() {
    if (!column) return
    setLoading(true)
    try {
      const result = await getJson<{ segments: SegmentRow[] }>(`/api/classifications/${classification.id}/segments?column=${encodeURIComponent(column)}`)
      setRows(result.segments); setLoadedColumn(column); setAllSegments(false)
    } catch (err) { onNotice({ text: (err as Error).message, error: true }) }
    finally { setLoading(false) }
  }

  const overall = useMemo(() => Object.fromEntries(freq.map((item) => [item.Categoría, item['%']])) as Record<string, number>, [freq])
  const categories = useMemo(
    () => [...classification.categories].sort((a, b) => (overall[b] ?? 0) - (overall[a] ?? 0)),
    [classification.categories, overall],
  )
  const shownCategories = allCategories ? categories : categories.slice(0, MAX_CATEGORIES)
  const withAnswers = useMemo(() => rows.filter((row) => row.base > 0).sort((a, b) => b.base - a.base), [rows])
  const shownSegments = allSegments ? withAnswers : withAnswers.slice(0, MAX_SEGMENTS)
  const emptyGroups = rows.length - withAnswers.length

  const example = useMemo(() => {
    const row = withAnswers[0]
    const category = shownCategories[0]
    if (!row || !category) return ''
    return `Ejemplo: en el grupo «${row.segment}» el ${pct(Number(row[category] || 0))} respondió «${category}» (en el total del estudio, ${pct(overall[category] ?? 0)}).`
  }, [withAnswers, shownCategories, overall])

  const cellStyle = (value: number) => ({
    background: `rgba(49, 91, 219, ${(0.06 + 0.84 * Math.min(Math.max(value, 0), 1)).toFixed(2)})`,
    color: value > 0.5 ? '#fff' : '#243049',
  })

  return (
    <section className="card segment-explorer">
      <div className="card-label">COMPARACIÓN POR GRUPOS</div>
      <h3>¿Cambian las respuestas según el tipo de persona?</h3>
      <p className="seg-explainer">
        Elige una variable del estudio (por ejemplo sexo, edad, ciudad o nivel socioeconómico). Cada <b>fila</b> es un grupo de personas y
        cada <b>columna</b> una categoría de la pregunta «{classification.question}». La celda muestra qué porcentaje <b>de ese grupo</b> dio esa respuesta.
      </p>
      <div className="seg-controls">
        <label>Agrupar personas por
          <select value={column} onChange={(e) => { setColumn(e.target.value); setRows([]); setLoadedColumn('') }}>
            <option value="">Selecciona una variable</option>
            {columns.filter((c) => c !== classification.question).map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
        <button className="button-primary" disabled={!column || loading} onClick={calculate}>
          {loading ? <><LoaderCircle className="spin" size={15} /> Calculando…</> : <>Comparar grupos <ArrowRight size={15} /></>}
        </button>
      </div>

      {withAnswers.length > 0 && (
        <div className="seg-results">
          <div className="seg-title">Resultados por «{loadedColumn}»</div>
          {example && <div className="seg-example">{example}</div>}
          <div className="seg-scroll">
            <table className="seg-table">
              <thead>
                <tr>
                  <th className="seg-sticky">Grupo <small>(personas con respuesta)</small></th>
                  {shownCategories.map((category) => <th key={category}>{category}</th>)}
                </tr>
              </thead>
              <tbody>
                <tr className="seg-total">
                  <th className="seg-sticky">Total del estudio</th>
                  {shownCategories.map((category) => <td key={category}><span className="seg-cell" style={cellStyle(overall[category] ?? 0)}>{pct(overall[category] ?? 0)}</span></td>)}
                </tr>
                {shownSegments.map((row) => (
                  <tr key={row.segment}>
                    <th className="seg-sticky">
                      <span className="seg-name">{row.segment}</span>
                      <small className={row.base < LOW_BASE ? 'seg-low' : ''} title={row.base < LOW_BASE ? 'Base baja: interpreta con cautela' : undefined}>
                        n={row.base.toLocaleString()}{row.base < LOW_BASE ? ' · base baja' : ''}
                      </small>
                    </th>
                    {shownCategories.map((category) => {
                      const value = Number(row[category] || 0)
                      const diff = value - (overall[category] ?? 0)
                      const mark = row.base >= LOW_BASE && Math.abs(diff) >= DIFF_POINTS ? (diff > 0 ? '▲' : '▼') : ''
                      return <td key={category}><span className="seg-cell" style={cellStyle(value)}>{pct(value)}{mark && <i className={diff > 0 ? 'seg-up' : 'seg-down'}>{mark}</i>}</span></td>
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="seg-legend">
            <span className="seg-legend-scale"><b>0%</b><i /><b>100%</b></span>
            <span>Más oscuro = más personas del grupo.</span>
            <span><i className="seg-up">▲</i>/<i className="seg-down">▼</i> = 10 puntos o más por encima/debajo del total (solo grupos con n ≥ {LOW_BASE}).</span>
          </div>
          <div className="seg-notes">
            {categories.length > MAX_CATEGORIES && <button className="button-text" onClick={() => setAllCategories(!allCategories)}>{allCategories ? `Mostrar solo las ${MAX_CATEGORIES} categorías principales` : `Ver las ${categories.length} categorías`}</button>}
            {withAnswers.length > MAX_SEGMENTS && <button className="button-text" onClick={() => setAllSegments(!allSegments)}>{allSegments ? `Mostrar solo los ${MAX_SEGMENTS} grupos más grandes` : `Ver los ${withAnswers.length} grupos`}</button>}
            {withAnswers.length > MAX_SEGMENTS && !allSegments && <small>Esta variable tiene muchos valores distintos; suele ser más útil agrupar por sexo, edad, ciudad o nivel socioeconómico.</small>}
            {emptyGroups > 0 && <small>{emptyGroups} grupo(s) sin respuestas válidas no se muestran.</small>}
            <small>Un grupo con pocas personas (n bajo) puede variar mucho: interpreta con cautela.</small>
          </div>
        </div>
      )}
      {loadedColumn && !loading && withAnswers.length === 0 && <div className="empty-inline">Ese grupo no tiene respuestas válidas para esta pregunta.</div>}
    </section>
  )
}
