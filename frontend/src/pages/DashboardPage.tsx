import { useEffect, useState } from 'react'
import { ArrowDownToLine, Check, Search, Sparkles, UsersRound } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api'
import { PageHeading, EmptyState } from '../components/common'
import { COLORS } from '../constants'
import type { Classification, Frequency, ReviewRow } from '../types'
import SegmentExplorer from '../SegmentExplorer'

export function DashboardPage({ study, apiKey, provider, model, onNotice }: any) {
  const classes: Classification[] = study?.classifications || []
  const [selectedId, setSelectedId] = useState('')
  const [freq, setFreq] = useState<Frequency[]>([])
  const [base, setBase] = useState(0)
  const [insight, setInsight] = useState<any>(null)
  const [reviewRows, setReviewRows] = useState<ReviewRow[]>([])
  const [reviewOffset, setReviewOffset] = useState(0)
  const [edits, setEdits] = useState<Record<number, string[]>>({})
  const [subBusy, setSubBusy] = useState(false)
  const selected = classes.find((item) => item.id === selectedId) || classes[0]
  useEffect(() => { if (classes.length && !classes.some((item) => item.id === selectedId)) setSelectedId(classes[0].id) }, [study?.id, classes.length])
  useEffect(() => {
    if (!selected) return
    setInsight(null); setReviewRows([]); setReviewOffset(0); setEdits({})
    api<{ base: number; rows: Frequency[] }>(`/api/classifications/${selected.id}/frequencies`).then((r) => { setFreq(r.rows); setBase(r.base) }).catch((e) => onNotice({ text: e.message, error: true }))
    api<any>(`/api/classifications/${selected.id}/rows?offset=0&limit=100`).then((r) => setReviewRows(r.rows)).catch(() => {})
  }, [selected?.id])
  async function loadMore() {
    if (!selected) return
    const next = reviewOffset + 100
    try { const result = await api<any>(`/api/classifications/${selected.id}/rows?offset=${next}&limit=100`); setReviewRows([...reviewRows, ...result.rows]); setReviewOffset(next) }
    catch (err) { onNotice({ text: (err as Error).message, error: true }) }
  }
  async function saveEdits() {
    if (!selected) return
    const changes = Object.entries(edits).map(([row_index, labels]) => ({ row_index: Number(row_index), labels }))
    if (!changes.length) { onNotice({ text: 'No hay cambios pendientes por guardar.' }); return }
    setSubBusy(true)
    try { await api(`/api/classifications/${selected.id}/labels`, { method: 'PATCH', body: JSON.stringify({ changes }) }); setReviewRows(reviewRows.map((row) => edits[row.row_index] ? { ...row, labels: edits[row.row_index] } : row)); setEdits({}); onNotice({ text: `Se guardaron ${changes.length} correcciones.` }); const result = await api<any>(`/api/classifications/${selected.id}/frequencies`); setFreq(result.rows); setBase(result.base) }
    catch (err) { onNotice({ text: (err as Error).message, error: true }) }
    finally { setSubBusy(false) }
  }
  async function generate() {
    if (!selected) return
    const form = new FormData(); form.append('provider', provider); form.append('model', model)
    setSubBusy(true)
    try { setInsight(await api<any>(`/api/classifications/${selected.id}/insights`, { method: 'POST', body: form }, apiKey)); onNotice({ text: 'Insights generados.' }) }
    catch (err) { onNotice({ text: (err as Error).message, error: true }) }
    finally { setSubBusy(false) }
  }
  async function downloadExcel() {
    if (!study) return
    setSubBusy(true)
    try {
      const token = sessionStorage.getItem('insights-token')
      const response = await fetch(`/api/studies/${study.id}/export-categorizations`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!response.ok) {
        const body = await response.json().catch(() => ({ detail: response.statusText }))
        throw new Error(body.detail || 'No se pudo descargar el Excel consolidado.')
      }
      const blob = await response.blob()
      const filename = (response.headers.get('Content-Disposition') || '').match(/filename="?([^";]+)"?/i)?.[1]
        || 'estudio_categorizaciones.xlsx'
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url; anchor.download = filename; document.body.appendChild(anchor); anchor.click(); anchor.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
      onNotice({ text: `Excel consolidado descargado: ${filename}` })
    } catch (err) { onNotice({ text: (err as Error).message, error: true }) }
    finally { setSubBusy(false) }
  }
  if (!study) return <EmptyState title="Carga o selecciona un estudio" text="El dashboard necesita datos para mostrar resultados." action="Ir a Inicio" />
  if (!classes.length) return <EmptyState title="Aún no hay clasificaciones" text="Clasifica una pregunta para habilitar frecuencias, cruces, insights y revisión manual." action="Ir a Categorización" />
  const chartData = freq.filter((item) => item.Menciones > 0).map((item) => ({ name: item.Categoría, pct: item['%'], n: item.Menciones }))
  return <>
    <PageHeading eyebrow="LECTURA DE RESULTADOS" title="Dashboard" text="Frecuencias, cortes por segmento y control de calidad de la codificación." action={<button className="button-secondary" disabled={subBusy} onClick={downloadExcel}><ArrowDownToLine size={16} /> Exportar Excel consolidado</button>} />
    <div className="dashboard-toolbar"><div className="select-icon"><Search size={15} /><select value={selected?.id || ''} onChange={(e) => setSelectedId(e.target.value)}>{classes.map((item) => <option key={item.id} value={item.id}>{item.question} · {item.kind === 'brands' ? 'Marcas' : item.kind === 'sentiment' ? 'Sentimiento' : 'Temas'}</option>)}</select></div><span className="base-chip"><UsersRound size={15} /> Base válida: <b>{base.toLocaleString()}</b></span></div>
    <div className="dashboard-grid dashboard-grid-single">
      <section className="card chart-card"><div className="card-heading"><div><div className="card-label">DISTRIBUCIÓN</div><h3>Frecuencia por categoría</h3></div><span className="soft-badge">{chartData.length} categorías</span></div>
        {chartData.length ? <div className="chart-wrap"><ResponsiveContainer width="100%" height={Math.max(300, chartData.length * 48)}><BarChart data={chartData} layout="vertical" margin={{ top: 8, right: 32, left: 16, bottom: 8 }}><CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e9edf3" /><XAxis type="number" tickFormatter={(v) => `${Math.round(v * 100)}%`} axisLine={false} tickLine={false} tick={{ fill: '#8b94a7', fontSize: 11 }} /><YAxis type="category" dataKey="name" width={140} axisLine={false} tickLine={false} tick={{ fill: '#4b566b', fontSize: 12 }} /><Tooltip formatter={(value: any, _name: any, props: any) => [`${(Number(value) * 100).toFixed(1)}% · ${props.payload.n} menciones`, 'Frecuencia']} contentStyle={{ border: '1px solid #e7eaf0', borderRadius: 10, fontSize: 12 }} /><Bar dataKey="pct" radius={[0, 5, 5, 0]} barSize={21}>{chartData.map((_item, index) => <Cell key={index} fill={COLORS[index % COLORS.length]} />)}<LabelList dataKey="pct" position="right" formatter={(v: any) => `${Math.round(Number(v) * 100)}%`} style={{ fill: '#647086', fontSize: 11 }} /></Bar></BarChart></ResponsiveContainer></div> : <div className="empty-inline">No hay respuestas válidas para graficar.</div>}
        <div className="frequency-table"><div className="table-scroll"><table><thead><tr><th>Categoría</th><th>Personas</th><th>Porcentaje</th></tr></thead><tbody>{freq.map((row) => <tr key={row.Categoría}><td><span className="color-dot" style={{ background: COLORS[freq.indexOf(row) % COLORS.length] }} />{row.Categoría}</td><td>{row.Menciones.toLocaleString()}</td><td>{(row['%'] * 100).toFixed(1)}%</td></tr>)}</tbody></table></div></div>
      </section>
    </div>
    {selected && <SegmentExplorer classification={selected} columns={study.columns || []} freq={freq} onNotice={onNotice} />}
    <div className="section-title-row mt-28"><div><h2>Insights cualitativos</h2><p>La IA redacta a partir de respuestas reales; cifras y citas se controlan desde el código.</p></div><button className="button-secondary" disabled={subBusy} onClick={generate}><Sparkles size={16} /> {subBusy ? 'Generando…' : 'Generar insights'}</button></div>
    {insight?.categorias?.length ? <div className="insight-grid">{insight.resumen && <div className="summary-insight"><div className="insight-kicker"><Sparkles size={15} /> LECTURA GENERAL</div><p>{insight.resumen}</p></div>}{insight.categorias.map((item: any) => <article className="card insight-card" key={item.categoria}><div className="insight-top"><span className="insight-dot" /> <b>{item.categoria}</b><span>{item.n} respuestas · {(item.pct * 100).toFixed(0)}%</span></div><p>{item.explicacion}</p>{item.citas?.map((quote: string, i: number) => <blockquote key={i}>“{quote}”</blockquote>)}</article>)}</div> : <div className="empty-panel"><div className="empty-icon"><Sparkles size={19} /></div><b>¿Qué está diciendo tu audiencia?</b><span>Genera una síntesis temática con citas verificables de las respuestas.</span></div>}
    <div className="section-title-row mt-32"><div><h2>Revisión y edición manual</h2><p>Corrige una etiqueta por fila; el cambio se guarda directamente en PostgreSQL.</p></div><button className="button-primary" onClick={saveEdits} disabled={subBusy || !Object.keys(edits).length}><Check size={15} /> Guardar {Object.keys(edits).length ? `(${Object.keys(edits).length})` : 'cambios'}</button></div>
    <div className="card review-card"><div className="review-toolbar"><div className="card-label">RESPUESTAS · MUESTRA DE {reviewRows.length}</div><span className="muted">{study.row_count.toLocaleString()} filas · Ctrl/Cmd para elegir varias etiquetas</span></div><div className="table-scroll"><table><thead><tr><th>Fila</th><th>Respuesta</th><th>Etiqueta actual</th><th>Editar etiquetas</th></tr></thead><tbody>{reviewRows.map((row) => { const options = [...selected.categories, ...['Ninguna', 'NS/NR'].filter((value) => (value !== 'Ninguna' || selected.kind === 'brands') && !selected.categories.includes(value))]; return <tr key={row.row_index}><td className="row-number">{row.row_index + 1}</td><td className="response-cell">{row.response || <span className="muted">(vacía)</span>}</td><td><span className="label-chip">{row.labels.join(' · ')}</span></td><td><select multiple disabled={!String(row.response ?? '').trim()} size={2} value={edits[row.row_index] ?? row.labels} onChange={(e) => { let values = Array.from(e.target.selectedOptions).map((option) => option.value); const exclusive = values.find((value) => value === 'Ninguna' || value === 'NS/NR'); if (exclusive) values = [exclusive]; setEdits({ ...edits, [row.row_index]: values }) }}>{options.map((c: string) => <option key={c} value={c}>{c}</option>)}</select></td></tr> })}</tbody></table></div>{reviewRows.length < study.row_count && <button className="button-secondary load-more" onClick={loadMore}>Cargar más respuestas</button>}</div>
  </>
}
