import { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowDownToLine, BarChart3, Check, FileSpreadsheet, LoaderCircle, UploadCloud } from 'lucide-react'
import {
  Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

/**
 * Awareness INDEPENDIENTE: carga un CSV/XLSX propio y descarga el Excel de resultados.
 * No necesita estudio, categorización ni Streamlit: usa la API del mismo backend
 * (/api/awareness-flex/*), así que funciona igual en local, Docker, Render y Vercel.
 */

type Analysis = { name: string; tom: string; esp: string; ayu: string }
type Preset = {
  label: string; entities: string[]; aliases: Record<string, string[]>; normalizations: unknown[]
  demographics: Record<string, string>; analyses: Analysis[]; expected_raw_cols: number
}
type Inspect = { filename: string; sheets: string[]; columns: string[]; row_count: number }
type ValidationRow = { tipo: string; campo: string; columnas: string }
type PreviewRow = {
  Entidad: string
  'TOM %': number
  'Espontaneo %': number
  'Ayudado %': number
  'AWA %': number
}
type Coverage = { question: string; role: string; answers: number; recognized: number; unrecognized: { respuesta: string; n: number }[] }
type Preview = {
  base: number
  analyses: { name: string; rows: PreviewRow[]; coverage?: Coverage | null }[]
  learned_variants?: { variante: string; marca: string; n: number }[]
  ignored_entities?: string[]
}

function rankPreviewRows(rows: PreviewRow[]): PreviewRow[] {
  return [...rows].sort((a, b) =>
    (b['AWA %'] - a['AWA %']) || a.Entidad.localeCompare(b.Entidad, 'es')
  )
}

const DEMO_LABELS: Record<string, string> = {
  sexo: 'Sexo', edad: 'Edad', departamento: 'Departamento / Ciudad', estrato: 'Estrato', ingreso: 'Ingreso / Rangos',
}

async function call<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  const token = sessionStorage.getItem('insights-token')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  const response = await fetch(path, { ...options, headers })
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(typeof body.detail === 'string' ? body.detail : 'Ocurrió un error al consultar el servidor.')
  }
  return response as unknown as T
}
const callJson = async <T,>(path: string, options: RequestInit = {}) => (await call<Response>(path, options)).json() as Promise<T>

export default function AwarenessStandalone({ onNotice }: { onNotice: (n: { text: string; error?: boolean }) => void }) {
  const [presets, setPresets] = useState<Record<string, Preset>>({})
  const [mode, setMode] = useState('personalizado')
  const [file, setFile] = useState<File | null>(null)
  const [sheet, setSheet] = useState('')
  const [info, setInfo] = useState<Inspect | null>(null)
  const [entitiesText, setEntitiesText] = useState('')
  const [aliasesText, setAliasesText] = useState('{}')
  const [normText, setNormText] = useState('[]')
  const [demographics, setDemographics] = useState<Record<string, string>>({ sexo: '', edad: '', departamento: '', estrato: '', ingreso: '' })
  const [analyses, setAnalyses] = useState<Analysis[]>([
    { name: 'Análisis 1', tom: '0', esp: '0', ayu: '0' }, { name: 'Análisis 2', tom: '0', esp: '0', ayu: '0' },
  ])
  const [maxRows, setMaxRows] = useState(0)
  const [fuzzy, setFuzzy] = useState(true)
  const [tomFirstOnly, setTomFirstOnly] = useState(true)
  const [suggesting, setSuggesting] = useState(false)
  const [expectedCols, setExpectedCols] = useState(0)
  const [validation, setValidation] = useState<ValidationRow[]>([])
  const [preview, setPreview] = useState<Preview | null>(null)
  const [reading, setReading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  function applyPreset(key: string, source: Record<string, Preset> = presets) {
    const preset = source[key]
    if (!preset) return
    setMode(key)
    setEntitiesText(preset.entities.join('\n'))
    setAliasesText(JSON.stringify(preset.aliases, null, 2))
    setNormText(JSON.stringify(preset.normalizations, null, 2))
    setDemographics({ sexo: '', edad: '', departamento: '', estrato: '', ingreso: '', ...preset.demographics })
    setAnalyses(preset.analyses.map((item) => ({ ...item })))
    setExpectedCols(preset.expected_raw_cols)
    setDone(false)
  }

  useEffect(() => {
    callJson<Record<string, Preset>>('/api/awareness-flex/presets')
      .then((data) => { setPresets(data); applyPreset('personalizado', data) })
      .catch((err) => onNotice({ text: `No se pudieron cargar los presets: ${(err as Error).message}`, error: true }))
  }, [])

  async function inspect(nextFile: File, nextSheet = '') {
    setReading(true); setDone(false)
    try {
      const form = new FormData(); form.append('file', nextFile); form.append('sheet', nextSheet)
      const data = await callJson<Inspect>('/api/awareness-flex/inspect', { method: 'POST', body: form })
      setInfo(data)
      setSheet(nextSheet || data.sheets[0] || '')
    } catch (err) {
      setInfo(null); setValidation([])
      onNotice({ text: (err as Error).message, error: true })
    } finally { setReading(false) }
  }

  function chooseFile(next: File | null) {
    setFile(next); setInfo(null); setValidation([]); setSheet('')
    if (next) inspect(next)
  }

  const parsed = useMemo(() => {
    try {
      const aliases = JSON.parse(aliasesText || '{}')
      const normalizations = JSON.parse(normText || '[]')
      return { config: { entities: entitiesText.split('\n').map((l) => l.trim()).filter(Boolean), aliases, normalizations, demographics, analyses, max_rows: maxRows, expected_raw_cols: expectedCols, fuzzy, tom_first_only: tomFirstOnly }, error: '' }
    } catch (err) { return { config: null, error: `Error en el JSON de alias o normalizaciones: ${(err as Error).message}` } }
  }, [entitiesText, aliasesText, normText, demographics, analyses, maxRows, expectedCols, fuzzy, tomFirstOnly])

  useEffect(() => {
    setPreview(null)
    setDone(false)
  }, [file, sheet, parsed])

  useEffect(() => {
    if (!info || !parsed.config) { setValidation([]); return }
    const timer = window.setTimeout(() => {
      callJson<{ rows: ValidationRow[] }>('/api/awareness-flex/validate', {
        method: 'POST', body: JSON.stringify({ columns: info.columns, config: parsed.config }),
      }).then((data) => setValidation(data.rows)).catch(() => setValidation([]))
    }, 350)
    return () => window.clearTimeout(timer)
  }, [info, parsed])

  async function suggestBrands() {
    if (!file || !parsed.config) return
    setSuggesting(true)
    try {
      const form = new FormData()
      form.append('file', file); form.append('sheet', sheet); form.append('config', JSON.stringify(parsed.config))
      const result = await callJson<{ entities: string[]; aliases: Record<string, string[]>; counts: Record<string, number>; distinct: number }>('/api/awareness-flex/suggest', { method: 'POST', body: form })
      setEntitiesText(result.entities.join('\n'))
      setAliasesText(JSON.stringify(result.aliases, null, 2))
      setMode('personalizado')
      onNotice({ text: `Se propusieron ${result.entities.length} marcas (de ${result.distinct} respuestas distintas) agrupando las escritas parecido. Revísalas y ajusta la lista.` })
    } catch (err) { onNotice({ text: (err as Error).message, error: true }) }
    finally { setSuggesting(false) }
  }

  function addBrand(name: string) {
    const current = entitiesText.split('\n').map((l) => l.trim()).filter(Boolean)
    if (current.some((item) => item.toLowerCase() === name.toLowerCase())) return
    setEntitiesText([...current, name].join('\n'))
  }

  const hasAnalysis = analyses.some((a) => [a.tom, a.esp, a.ayu].some((v) => v.trim() !== '' && v.trim() !== '0'))

  async function generate() {
    if (!file || !parsed.config) return
    setBusy(true); setDone(false); setPreview(null)
    try {
      const previewForm = new FormData()
      previewForm.append('file', file); previewForm.append('sheet', sheet); previewForm.append('config', JSON.stringify(parsed.config))
      const previewData = await callJson<Preview>('/api/awareness-flex/preview', { method: 'POST', body: previewForm })
      setPreview({
        ...previewData,
        analyses: previewData.analyses.map((analysis) => ({ ...analysis, rows: rankPreviewRows(analysis.rows) })),
      })

      const reportForm = new FormData()
      reportForm.append('file', file); reportForm.append('sheet', sheet); reportForm.append('config', JSON.stringify(parsed.config))
      const response = await call<Response>('/api/awareness-flex/report', { method: 'POST', body: reportForm })
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url; anchor.download = 'Reporte_Awareness_Estructural.xlsx'
      document.body.appendChild(anchor); anchor.click(); anchor.remove()
      URL.revokeObjectURL(url)
      setDone(true)
      onNotice({ text: 'Reporte de Awareness generado y descargado.' })
    } catch (err) { onNotice({ text: (err as Error).message, error: true }) }
    finally { setBusy(false) }
  }

  const setAnalysis = (index: number, patch: Partial<Analysis>) =>
    setAnalyses((current) => current.map((item, i) => (i === index ? { ...item, ...patch } : item)))

  return (
    <div className="awa-flex-stack">
      <section className="card form-card">
        <div className="card-label">PASO 1 · ARCHIVO</div>
        <h3>Carga tu base (CSV o Excel)</h3>
        <div className="awa-file-row">
          <button className="button-secondary" onClick={() => inputRef.current?.click()} disabled={reading}>
            {reading ? <><LoaderCircle className="spin" size={15} /> Leyendo…</> : <><UploadCloud size={15} /> {file ? 'Cambiar archivo' : 'Elegir archivo'}</>}
          </button>
          <input ref={inputRef} type="file" accept=".csv,.xlsx" hidden onChange={(e) => { chooseFile(e.target.files?.[0] || null); e.target.value = '' }} />
          {file && <span className="awa-file-name"><FileSpreadsheet size={15} /> {file.name}</span>}
          {info && <span className="base-chip">Base: <b>{info.row_count.toLocaleString()}</b> filas · <b>{info.columns.length}</b> columnas</span>}
        </div>
        {info && info.sheets.length > 1 && (
          <label>Hoja del Excel
            <select value={sheet} onChange={(e) => { setSheet(e.target.value); if (file) inspect(file, e.target.value) }}>
              {info.sheets.map((name) => <option key={name}>{name}</option>)}
            </select>
          </label>
        )}
        {!file && <small className="field-help">Este módulo es independiente: no necesita estudio ni categorización previa. Máximo 25 MB.</small>}
      </section>

      <section className="card form-card">
        <div className="card-label">PASO 2 · ENTIDADES</div>
        <h3>Marcas, alias y normalizaciones</h3>
        <div className="segmented">
          {Object.entries(presets).map(([key, item]) => (
            <button key={key} className={mode === key ? 'selected' : ''} onClick={() => applyPreset(key)}>{item.label}</button>
          ))}
        </div>
        <label>Entidades a evaluar, una por línea
          <textarea rows={7} value={entitiesText} onChange={(e) => setEntitiesText(e.target.value)} />
        </label>
        <div className="form-grid-two">
          <label>Alias / condiciones (JSON)
            <textarea className="awa-code" rows={9} value={aliasesText} onChange={(e) => setAliasesText(e.target.value)} spellCheck={false} />
          </label>
          <label>Normalizaciones opcionales (JSON)
            <textarea className="awa-code" rows={9} value={normText} onChange={(e) => setNormText(e.target.value)} spellCheck={false} />
          </label>
        </div>
        <div className="awa-brand-tools">
          <button className="button-secondary" disabled={!file || !parsed.config || suggesting} onClick={suggestBrands} title="Lee las respuestas del archivo y arma la lista de marcas">
            {suggesting ? <><LoaderCircle className="spin" size={14} /> Leyendo respuestas…</> : <>Detectar marcas desde las respuestas</>}
          </button>
          <label className="check-row"><input type="checkbox" checked={fuzzy} onChange={(e) => setFuzzy(e.target.checked)} /><span>Agrupar respuestas escritas parecido (p. ej. “Decatlon” = “Decathlon”)</span></label>
          <label className="check-row"><input type="checkbox" checked={tomFirstOnly} onChange={(e) => setTomFirstOnly(e.target.checked)} /><span>TOM = solo la primera marca mencionada</span></label>
        </div>
        {parsed.error && <div className="auth-error" role="alert">{parsed.error}</div>}
      </section>

      <section className="card form-card">
        <div className="card-label">PASO 3 · PREGUNTAS Y DEMOGRÁFICOS</div>
        <h3>Prefijos de columnas</h3>
        <small className="field-help">Escribe el inicio del nombre de la columna (p. ej. P1, P1A). Varias columnas: una por línea. Usa 0 para desactivar.</small>
        <div className="form-grid-two mt-12">
          {Object.entries(DEMO_LABELS).map(([key, label]) => (
            <label key={key}>{label}
              <input value={demographics[key] ?? ''} onChange={(e) => setDemographics({ ...demographics, [key]: e.target.value })} />
            </label>
          ))}
        </div>
        <div className="form-grid-two">
          {analyses.map((item, index) => (
            <div key={index} className="awa-analysis-box">
              <label>Nombre análisis {index + 1}<input value={item.name} onChange={(e) => setAnalysis(index, { name: e.target.value })} /></label>
              <label>TOM<input value={item.tom} onChange={(e) => setAnalysis(index, { tom: e.target.value })} /></label>
              <label>Espontáneo<textarea rows={3} value={item.esp} onChange={(e) => setAnalysis(index, { esp: e.target.value })} /></label>
              <label>Ayudado<textarea rows={3} value={item.ayu} onChange={(e) => setAnalysis(index, { ayu: e.target.value })} /></label>
            </div>
          ))}
        </div>
        <div className="form-grid-two">
          <label>Filas a evaluar (0 = todas)<input type="number" min={0} value={maxRows} onChange={(e) => setMaxRows(Math.max(0, Number(e.target.value) || 0))} /></label>
          <label>Columnas crudas esperadas (0 = no validar)<input type="number" min={0} value={expectedCols} onChange={(e) => setExpectedCols(Math.max(0, Number(e.target.value) || 0))} /></label>
        </div>
      </section>

      <section className="card form-card">
        <div className="card-label">PASO 4 · VALIDAR Y DESCARGAR</div>
        <h3>Validación de columnas</h3>
        {validation.length ? (
          <div className="table-scroll awa-validation">
            <table>
              <thead><tr><th>Tipo</th><th>Campo</th><th>Columna detectada</th></tr></thead>
              <tbody>{validation.map((row, i) => <tr key={i}><td>{row.tipo}</td><td>{row.campo}</td><td>{row.columnas || <span className="awa-missing">No detectada</span>}</td></tr>)}</tbody>
            </table>
          </div>
        ) : <div className="info-callout"><Check size={16} /><span>Carga un archivo para ver qué columnas detecta cada prefijo.</span></div>}
        <button className="button-primary full-width mt-12" onClick={generate} disabled={busy || !file || !parsed.config || !hasAnalysis}>
          {busy ? <><LoaderCircle className="spin" size={16} /> Calculando…</> : <><ArrowDownToLine size={16} /> Calcular y descargar Excel</>}
        </button>
        {file && !hasAnalysis && <small className="field-help">Configura al menos un análisis (TOM, Espontáneo o Ayudado) para habilitar el reporte.</small>}
        {done && <div className="info-callout"><Check size={16} /><span>Reporte generado. Revisa tu carpeta de descargas.</span></div>}
        {preview ? (
          <section className="awa-preview-panel">
            <div className="awa-preview-heading">
              <div><div className="card-label">RESULTADO</div><h3>Vista previa de Awareness</h3><p>Porcentaje de la base que recuerda cada entidad en cada nivel.</p></div>
              <span className="base-chip">Base: <b>{preview.base.toLocaleString()}</b> respuestas</span>
            </div>
            {(preview.learned_variants?.length || preview.ignored_entities?.length) ? <div className="awa-notes">
              {preview.learned_variants && preview.learned_variants.length > 0 && <div><b>Respuestas agrupadas con su marca:</b> {preview.learned_variants.slice(0, 10).map((item) => `${item.variante} → ${item.marca} (${item.n})`).join(' · ')}{preview.learned_variants.length > 10 ? ` · y ${preview.learned_variants.length - 10} más` : ''}</div>}
              {preview.ignored_entities && preview.ignored_entities.length > 0 && <div><b>No se grafican:</b> {preview.ignored_entities.join(', ')} (no son marcas).</div>}
            </div> : null}
            <div className="awa-preview-grid">
              {preview.analyses.map((analysis) => (
                <article className="awa-preview-analysis" key={analysis.name}>
                  <div className="awa-preview-analysis-title"><h4>{analysis.name}</h4><span>{analysis.rows.length} marcas</span></div>
                  {analysis.coverage && analysis.coverage.answers > 0 && (() => {
                    const cov = analysis.coverage as Coverage
                    const share = cov.recognized / cov.answers
                    return <div className={`awa-coverage ${share < 0.6 ? 'low' : 'ok'}`}>
                      <b>{Math.round(share * 100)}% de las respuestas {cov.role} coincide con tu lista de marcas</b>
                      <span>{cov.recognized.toLocaleString()} de {cov.answers.toLocaleString()} respuestas con marca en «{cov.question}».</span>
                      {cov.unrecognized.length > 0 && <div className="awa-chips">
                        <small>{share < 0.6 ? 'Estas respuestas frecuentes no están en tu lista (clic para agregarlas):' : 'Respuestas sin reconocer:'}</small>
                        {cov.unrecognized.map((item) => <button key={item.respuesta} className="awa-chip" onClick={() => addBrand(item.respuesta)} title="Agregar a la lista de marcas">+ {item.respuesta} <i>{item.n}</i></button>)}
                      </div>}
                    </div>
                  })()}
                  {analysis.rows.length ? <>
                    <div className="chart-wrap awa-preview-chart">
                      <ResponsiveContainer width="100%" height={Math.max(230, analysis.rows.length * 38)}>
                        <BarChart data={analysis.rows} layout="vertical" margin={{ top: 6, right: 18, left: 8, bottom: 4 }}>
                          <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e9edf3" />
                          <XAxis type="number" domain={[0, 1]} tickFormatter={(value) => `${Math.round(value * 100)}%`} axisLine={false} tickLine={false} tick={{ fill: '#8b94a7', fontSize: 10 }} />
                          <YAxis type="category" dataKey="Entidad" width={126} reversed axisLine={false} tickLine={false} tick={{ fill: '#4b566b', fontSize: 10 }} />
                          <Tooltip formatter={(value: any, name: any) => [`${(Number(value) * 100).toFixed(1)}%`, name]} contentStyle={{ border: '1px solid #e7eaf0', borderRadius: 9, fontSize: 11 }} />
                          <Legend wrapperStyle={{ fontSize: 10, paddingTop: 8 }} />
                          <Bar dataKey="TOM %" name="TOM" stackId="awareness" fill="#315bdb" />
                          <Bar dataKey="Espontaneo %" name="Espontáneo" stackId="awareness" fill="#18a994" />
                          <Bar dataKey="Ayudado %" name="Ayudado" stackId="awareness" fill="#ef9b46" />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="table-scroll awa-preview-table">
                      <table><thead><tr><th>Marca</th><th>TOM</th><th>Espontáneo</th><th>Ayudado</th><th>AWA</th></tr></thead>
                        <tbody>{analysis.rows.map((row) => <tr key={row.Entidad}>
                          <td>{row.Entidad}</td><td>{(row['TOM %'] * 100).toFixed(1)}%</td><td>{(row['Espontaneo %'] * 100).toFixed(1)}%</td><td>{(row['Ayudado %'] * 100).toFixed(1)}%</td><td><b>{(row['AWA %'] * 100).toFixed(1)}%</b></td>
                        </tr>)}</tbody>
                      </table>
                    </div>
                  </> : <div className="empty-inline">No hay marcas para graficar en este análisis.</div>}
                </article>
              ))}
            </div>
          </section>
        ) : <div className="awa-preview-placeholder"><BarChart3 size={17} /><span>Al calcular el Awareness, aquí aparecerán los gráficos de ambos análisis.</span></div>}
      </section>
    </div>
  )
}
