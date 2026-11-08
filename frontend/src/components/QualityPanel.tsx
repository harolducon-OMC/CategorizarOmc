import { useCallback, useEffect, useState } from 'react'
import { ClipboardCheck } from 'lucide-react'
import { api } from '../api'
import type { Classification } from '../types'
import { TableSkeleton } from './Skeleton'
import './quality.css'

type CategoryStat = { category: string; support: number; predicted: number; precision: number | null; recall: number | null; f1: number | null }
type Quality = {
  reviewed: number; agreement: number | null; interval: [number, number] | null; level: 'alto' | 'medio' | 'bajo' | null
  reliable: boolean; kappa: number | null; micro_f1: number | null; categories: CategoryStat[]; weakest: CategoryStat[]
  min_sample: number; baseline_available: boolean
}
type SampleRow = { row_index: number; response: string; ai_labels: string[]; labels: string[] }
type Sample = { rows: SampleRow[]; categories: string[]; baseline_available: boolean; pending: number }

const SAMPLE_SIZE = 20
const pct = (value: number | null | undefined) => (value == null ? '—' : `${Math.round(value * 100)}%`)

/** Mide qué tanto coincide la IA con tu criterio: tomas una muestra al azar y confirmas o corriges cada etiqueta. */
export function QualityPanel({ classification, onNotice, onChanged }: {
  classification: Classification
  onNotice: (notice: { text: string; error?: boolean }) => void
  onChanged: () => void
}) {
  const [quality, setQuality] = useState<Quality | null>(null)
  const [sample, setSample] = useState<Sample | null>(null)
  const [picks, setPicks] = useState<Record<number, string[]>>({})
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    api<Quality>(`/api/classifications/${classification.id}/quality`)
      .then(setQuality)
      .catch((error) => onNotice({ text: error.message, error: true }))
      .finally(() => setLoading(false))
  }, [classification.id, onNotice])

  useEffect(() => { setSample(null); setPicks({}); load() }, [classification.id, classification.updated_at, load])

  async function takeSample() {
    setBusy(true)
    try {
      const result = await api<Sample>(`/api/classifications/${classification.id}/quality/sample?n=${SAMPLE_SIZE}`)
      if (!result.rows.length) { onNotice({ text: 'No quedan respuestas por revisar en esta pregunta.' }); return }
      setSample(result)
      setPicks(Object.fromEntries(result.rows.map((row) => [row.row_index, row.labels])))
    } catch (error) {
      onNotice({ text: (error as Error).message, error: true })
    } finally {
      setBusy(false)
    }
  }

  function toggle(rowIndex: number, label: string) {
    setPicks((current) => {
      const selected = current[rowIndex] || []
      return { ...current, [rowIndex]: selected.includes(label) ? selected.filter((item) => item !== label) : [...selected, label] }
    })
  }

  async function saveSample() {
    if (!sample) return
    setBusy(true)
    try {
      const reviews = sample.rows.map((row) => ({ row_index: row.row_index, labels: picks[row.row_index] || [] }))
      const result = await api<Quality & { saved: number }>(`/api/classifications/${classification.id}/quality/reviews`, {
        method: 'PUT', body: JSON.stringify({ reviews }),
      })
      setQuality(result)
      setSample(null)
      onChanged()
      onNotice({ text: `Revisión guardada (${result.saved} respuestas). Las etiquetas corregidas ya se aplicaron.` })
    } catch (error) {
      onNotice({ text: (error as Error).message, error: true })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card quality-card">
      <div className="quality-head">
        <div>
          <div className="card-label">CALIDAD DE LA CATEGORIZACIÓN</div>
          <p className="quality-sub">Revisa una muestra al azar y mide cuánto coincide la IA con tu criterio.</p>
        </div>
        {!sample && <button className="button-secondary" disabled={busy || loading} onClick={() => void takeSample()}><ClipboardCheck size={14} /> Revisar {SAMPLE_SIZE} al azar</button>}
      </div>

      {loading && !quality ? <TableSkeleton rows={3} /> : quality && quality.reviewed === 0 && !sample && (
        <p className="quality-empty">Aún no has revisado ninguna muestra. Con 50 respuestas revisadas o más la cifra es más estable.</p>
      )}

      {quality && quality.reviewed > 0 && !sample && (
        <>
          <div className="quality-stats">
            <div className={`quality-main ${quality.level || ''}`}>
              <b>{pct(quality.agreement)}</b>
              <span>acuerdo con la IA</span>
              {quality.interval && <small>IC 95 %: {pct(quality.interval[0])} a {pct(quality.interval[1])}</small>}
            </div>
            <div><b>{quality.reviewed}</b><span>respuestas revisadas</span></div>
            <div><b>{pct(quality.micro_f1)}</b><span>F1 global</span></div>
            {quality.kappa != null && <div><b>{quality.kappa.toFixed(2)}</b><span>kappa de Cohen</span></div>}
          </div>
          {!quality.reliable && <p className="awa-base-warning">Con menos de {quality.min_sample} respuestas revisadas la cifra es orientativa. Revisa otra muestra para afinarla.</p>}
          {!quality.baseline_available && <p className="awa-base-warning">Esta clasificación se hizo antes de activar el panel: se compara con las etiquetas actuales. Vuelve a clasificar para medir con exactitud.</p>}
          {quality.weakest.length > 0 && <p className="awa-base-warning"><b>Categorías a afinar:</b> {quality.weakest.map((item) => `${item.category} (F1 ${pct(item.f1)})`).join(', ')}. Revisa su descripción o agrega palabras clave al diccionario.</p>}
          <div className="table-scroll"><table><thead><tr><th>Categoría</th><th>Revisadas</th><th>Precisión</th><th>Cobertura</th><th>F1</th></tr></thead><tbody>
            {quality.categories.map((item) => <tr key={item.category}><td>{item.category}</td><td>{item.support}</td><td>{pct(item.precision)}</td><td>{pct(item.recall)}</td><td><b>{pct(item.f1)}</b></td></tr>)}
          </tbody></table></div>
        </>
      )}

      {sample && (
        <div className="quality-sample">
          <p className="quality-sub">Marca las etiquetas correctas de cada respuesta. Al guardar, tus correcciones se aplican a la clasificación.</p>
          {!sample.baseline_available && <p className="awa-base-warning">Se compara con las etiquetas actuales porque esta clasificación no guardó la propuesta original de la IA.</p>}
          {sample.rows.map((row) => (
            <div className="quality-row" key={row.row_index}>
              <div className="quality-text">{row.response}</div>
              <div className="quality-ai">IA propuso: {row.ai_labels.length ? row.ai_labels.join(', ') : 'sin etiqueta'}</div>
              <div className="quality-chips">
                {sample.categories.map((label) => (
                  <button key={label} type="button" className={`quality-chip ${(picks[row.row_index] || []).includes(label) ? 'on' : ''}`} onClick={() => toggle(row.row_index, label)}>{label}</button>
                ))}
              </div>
            </div>
          ))}
          <div className="quality-actions">
            <button className="button-primary" disabled={busy} onClick={() => void saveSample()}>Guardar revisión ({sample.rows.length})</button>
            <button className="button-secondary" disabled={busy} onClick={() => setSample(null)}>Cancelar</button>
            {sample.pending > 0 && <small>{sample.pending} respuestas más por revisar</small>}
          </div>
        </div>
      )}
    </div>
  )
}
