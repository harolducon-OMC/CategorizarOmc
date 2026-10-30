import { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowDownToLine, Check, FileSpreadsheet, LoaderCircle, UploadCloud } from 'lucide-react'

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
  const [expectedCols, setExpectedCols] = useState(0)
  const [validation, setValidation] = useState<ValidationRow[]>([])
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
      return { config: { entities: entitiesText.split('\n').map((l) => l.trim()).filter(Boolean), aliases, normalizations, demographics, analyses, max_rows: maxRows, expected_raw_cols: expectedCols }, error: '' }
    } catch (err) { return { config: null, error: `Error en el JSON de alias o normalizaciones: ${(err as Error).message}` } }
  }, [entitiesText, aliasesText, normText, demographics, analyses, maxRows, expectedCols])

  useEffect(() => {
    if (!info || !parsed.config) { setValidation([]); return }
    const timer = window.setTimeout(() => {
      callJson<{ rows: ValidationRow[] }>('/api/awareness-flex/validate', {
        method: 'POST', body: JSON.stringify({ columns: info.columns, config: parsed.config }),
      }).then((data) => setValidation(data.rows)).catch(() => setValidation([]))
    }, 350)
    return () => window.clearTimeout(timer)
  }, [info, parsed])

  const hasAnalysis = analyses.some((a) => [a.tom, a.esp, a.ayu].some((v) => v.trim() !== '' && v.trim() !== '0'))

  async function generate() {
    if (!file || !parsed.config) return
    setBusy(true); setDone(false)
    try {
      const form = new FormData()
      form.append('file', file); form.append('sheet', sheet); form.append('config', JSON.stringify(parsed.config))
      const response = await call<Response>('/api/awareness-flex/report', { method: 'POST', body: form })
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
          {busy ? <><LoaderCircle className="spin" size={16} /> Generando…</> : <><ArrowDownToLine size={16} /> Generar reporte Excel</>}
        </button>
        {file && !hasAnalysis && <small className="field-help">Configura al menos un análisis (TOM, Espontáneo o Ayudado) para habilitar el reporte.</small>}
        {done && <div className="info-callout"><Check size={16} /><span>Reporte generado. Revisa tu carpeta de descargas.</span></div>}
      </section>
    </div>
  )
}
