import { useEffect, useState } from 'react'
import { ArrowDownToLine, BarChart3, Check, LoaderCircle, UsersRound } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api'
import { PageHeading, EmptyState } from '../components/common'
import type { Classification, AwarenessProfile, AwarenessValidationRow } from '../types'
import { splitQuestionCodes } from '../utils'
import { downloadAwarenessChartImage, downloadAwarenessTableImage, toAwarenessImageRows } from '../downloads'

export function AwarenessPage({ study, onNotice }: any) {
  const brandClasses: Classification[] = (study?.classifications || []).filter((item: Classification) => item.kind === 'brands')
  const [classIds, setClassIds] = useState<string[]>([])
  const [analyses, setAnalyses] = useState<AwarenessProfile[]>([
    { name: 'AWA Marca', tom_code: '', spontaneous_codes: '', aided_codes: '' },
    { name: 'AWA Publicitario', tom_code: '', spontaneous_codes: '', aided_codes: '' },
  ])
  const [demographics, setDemographics] = useState<Record<string, string>>({ sexo: '', edad: '', departamento: '', estrato: '', ingreso: '' })
  const [segment, setSegment] = useState('')
  const [segmentValue, setSegmentValue] = useState('')
  const [segmentValues, setSegmentValues] = useState<string[]>([])
  const [validation, setValidation] = useState<AwarenessValidationRow[]>([])
  const [validationBusy, setValidationBusy] = useState(false)
  const [validationError, setValidationError] = useState('')
  const [result, setResult] = useState<any>(null)
  const [busy, setBusy] = useState(false)
  const brandClass = brandClasses.find((item) => item.id === classIds[0]) || brandClasses[0]
  const studyColumns = study?.columns || []
  const studyColumnsKey = studyColumns.join('\u0000')
  const analysesReady = analyses.every((item) =>
    [item.tom_code, item.spontaneous_codes, item.aided_codes].some((value) => splitQuestionCodes(value).length > 0)
  )
  function updateAnalysis(index: number, changes: Partial<AwarenessProfile>) {
    setAnalyses((current) => current.map((item, currentIndex) => currentIndex === index ? { ...item, ...changes } : item))
  }
  useEffect(() => {
    const validIds = classIds.filter((id) => brandClasses.some((item) => item.id === id))
    if (!validIds.length && brandClasses.length) setClassIds(brandClasses.map((item) => item.id))
    else if (validIds.length !== classIds.length) setClassIds(validIds)
  }, [study?.id, brandClasses.map((item) => item.id).join('|')])
  useEffect(() => {
    if (!study || !segment) { setSegmentValues([]); setSegmentValue(''); return }
    api<{ values: string[] }>(`/api/studies/${study.id}/values?column=${encodeURIComponent(segment)}`).then((result) => {
      setSegmentValues(result.values)
      setSegmentValue((current) => result.values.includes(current) ? current : (result.values[0] || ''))
    }).catch((err) => onNotice({ text: err.message, error: true }))
  }, [study?.id, segment])
  useEffect(() => {
    if (!study?.id || !studyColumns.length) {
      setValidation([])
      setValidationBusy(false)
      setValidationError('')
      return
    }
    let current = true
    setValidationBusy(true)
    setValidationError('')
    const timer = window.setTimeout(() => {
      const config = {
        entities: ['Validación'],
        aliases: {},
        normalizations: [],
        demographics,
        analyses: analyses.map((item) => ({
          name: item.name,
          tom: item.tom_code,
          esp: item.spontaneous_codes,
          ayu: item.aided_codes,
        })),
        max_rows: 0,
        expected_raw_cols: 0,
      }
      api<{ rows: AwarenessValidationRow[] }>('/api/awareness-flex/validate', {
        method: 'POST',
        body: JSON.stringify({ columns: studyColumns, config }),
      }).then((response) => {
        if (current) setValidation(response.rows)
      }).catch((err) => {
        if (current) setValidationError((err as Error).message)
      }).finally(() => {
        if (current) setValidationBusy(false)
      })
    }, 300)
    return () => {
      current = false
      window.clearTimeout(timer)
    }
  }, [study?.id, studyColumnsKey, analyses, demographics])
  async function calculate() {
    if (!study || !brandClass || !classIds.length || !analysesReady) return
    setBusy(true)
    try {
      setResult(await api<any>(`/api/studies/${study.id}/awareness`, {
        method: 'POST', body: JSON.stringify({
          classification_id: classIds[0],
          classification_ids: classIds,
          analyses: analyses.map((item) => ({
            name: item.name,
            tom_column: splitQuestionCodes(item.tom_code).join('\n') || '0',
            spontaneous_columns: splitQuestionCodes(item.spontaneous_codes),
            aided_columns: splitQuestionCodes(item.aided_codes),
          })),
          demographics, segment_column: segment, segment_value: segmentValue,
        }),
      }))
    } catch (err) { onNotice({ text: (err as Error).message, error: true }) }
    finally { setBusy(false) }
  }
  if (!study) return <EmptyState title="Carga o selecciona un estudio" text="Awareness utiliza las columnas de una encuesta y una lista de marcas." action="Ir a Inicio" />
  if (!brandClasses.length) return <EmptyState title="Primero detecta marcas" text="Clasifica una pregunta de tipo Marcas para reutilizar sus marcas y alias en Awareness." action="Ir a Categorización" />
  const validationRows = validation.filter((row) => {
    if (row.tipo === 'Demográfico') return splitQuestionCodes(demographics[row.campo] || '').length > 0
    const profile = analyses.find((item) => row.tipo.endsWith(item.name))
    if (!profile) return false
    const code = row.campo === 'TOM' ? profile.tom_code
      : row.campo === 'Espontáneo' ? profile.spontaneous_codes : profile.aided_codes
    return splitQuestionCodes(code).length > 0
  })
  const resultAnalyses = result?.analyses || (result ? [{ name: 'Awareness', rows: result.rows || [] }] : [])
  return <>
    <PageHeading eyebrow="RECORDACIÓN DE MARCA" title="Awareness" text="Configura Top of Mind, recordación espontánea y ayudada a partir de las marcas detectadas." />
    <div className="awareness-layout">
      <section className="card form-card awareness-config-card">
        <div className="card-label">CONFIGURACIÓN</div>
        <div className="awareness-config-heading"><div><h3>Configura los dos análisis</h3><p>Escribe los códigos de pregunta, como en Awareness independiente.</p></div><span className="base-chip">{study.row_count.toLocaleString()} respuestas</span></div>
        <div className="awareness-config-grid">
          <div className="awareness-config-context">
            <div className="awareness-source-picker">
              <div className="awareness-source-heading"><b>Preguntas categorizadas para consolidar las marcas</b><button className="button-text" onClick={() => setClassIds(classIds.length === brandClasses.length ? [] : brandClasses.map((item) => item.id))}>{classIds.length === brandClasses.length ? 'Desmarcar todas' : 'Seleccionar todas'}</button></div>
              <div className="awareness-source-list">{brandClasses.map((item) => <label key={item.id}><input type="checkbox" checked={classIds.includes(item.id)} onChange={(event) => setClassIds((current) => event.target.checked ? [...current, item.id] : current.filter((id) => id !== item.id))} /><span>{item.question}</span></label>)}</div>
              <small className="field-help">Las respuestas categorizadas y corregidas se usan para consolidar las marcas.</small>
            </div>
            <div className="awareness-context-section">
              <div className="awareness-options-grid">
                <label>Segmento opcional
                  <select value={segment} onChange={(e) => { setSegment(e.target.value); setSegmentValue('') }}><option value="">Total</option>{studyColumns.map((column: string) => <option key={column}>{column}</option>)}</select>
                </label>
                {segment && <label>Valor del segmento
                  <select value={segmentValue} onChange={(e) => setSegmentValue(e.target.value)}>{segmentValues.map((value) => <option key={value} value={value}>{value}</option>)}</select>
                </label>}
              </div>
              <div className="awareness-demographics-heading"><div className="card-label">VARIABLES DEMOGRÁFICAS</div><span>Opcionales</span></div>
              <div className="awareness-demographics-grid">{Object.entries(demographics).map(([key, value]) => <label key={key}>{key[0].toUpperCase() + key.slice(1)}<select value={value} onChange={(e) => setDemographics({ ...demographics, [key]: e.target.value })}><option value="">No usar</option>{studyColumns.map((column: string) => <option key={column}>{column}</option>)}</select></label>)}</div>
            </div>
          </div>

          <div className="awareness-config-analysis">
            <div className="awareness-profiles-grid">
              {analyses.map((analysis, index) => <section className="awareness-profile" key={analysis.name}>
                <div className="awareness-profile-heading"><span className="card-label">{index === 0 ? 'ANÁLISIS 1' : 'ANÁLISIS 2'}</span><h4>{analysis.name}</h4></div>
                <div className="awareness-profile-fields">
                  <label>TOM · código de pregunta
                    <input className="awareness-code-input" value={analysis.tom_code} onChange={(e) => updateAnalysis(index, { tom_code: e.target.value })} placeholder="Ej. CE1" />
                  </label>
                  <label>Espontáneo · código(s)
                    <textarea className="awareness-code-input" rows={2} value={analysis.spontaneous_codes} onChange={(e) => updateAnalysis(index, { spontaneous_codes: e.target.value })} placeholder={'Ej. CE2\nCE3'} />
                  </label>
                  <label>Ayudado · código(s)
                    <textarea className="awareness-code-input" rows={2} value={analysis.aided_codes} onChange={(e) => updateAnalysis(index, { aided_codes: e.target.value })} placeholder={'Ej. CE4\nCE5'} />
                  </label>
                </div>
                <small className="field-help">Separa códigos con comas o saltos de línea. Se agrupan sufijos como `_1` y `_2`, sin incluir `CE10` al escribir `CE1`.</small>
              </section>)}
            </div>
            {!analysesReady && <div className="info-callout awareness-hint"><Check size={16} /><span>Completa al menos un código en cada perfil para calcular AWA Marca y AWA Publicitario.</span></div>}
            <section className="awareness-validation">
              <div className="awareness-validation-heading"><div><div className="card-label">REVISIÓN DE CÓDIGOS</div><h4>Validación de columnas</h4></div><span className="base-chip">{validationBusy ? 'Validando…' : `${validationRows.length} campos`}</span></div>
              {validationError ? <div className="auth-error" role="alert">{validationError}</div> : validationRows.length ? (
                <div className="table-scroll awa-validation awareness-flow-validation">
                  <table><thead><tr><th>Tipo</th><th>Campo</th><th>Columna detectada</th></tr></thead>
                    <tbody>{validationRows.map((row, index) => <tr key={`${row.tipo}-${row.campo}-${index}`}><td>{row.tipo}</td><td>{row.campo}</td><td>{row.columnas || <span className="awa-missing">No detectada</span>}</td></tr>)}</tbody>
                  </table>
                </div>
              ) : <div className="info-callout"><Check size={16} /><span>Escribe códigos de pregunta para ver las columnas detectadas.</span></div>}
            </section>
            <button className="button-primary full-width" onClick={calculate} disabled={busy || !classIds.length || !analysesReady}>{busy ? <><LoaderCircle className="spin" size={16} /> Calculando…</> : <><BarChart3 size={16} /> Calcular ambos análisis</>}</button>
          </div>
        </div>
      </section>
      <section className="card awareness-result">
        <div className="card-heading"><div><div className="card-label">RESULTADOS</div><h3>Awareness por tipo</h3></div>{result && <span className="base-chip">Base: <b>{Number(result.base).toLocaleString('es-CO')}</b> encuestados{result.rows_total && result.rows_total !== result.base ? <> de <b>{Number(result.rows_total).toLocaleString('es-CO')}</b> del estudio{result.segment_column ? ` · segmento «${result.segment_value}»` : ''}</> : null}</span>}</div>
        {resultAnalyses.length ? resultAnalyses.map((analysis: any, analysisIndex: number) => {
          const rankedRows = [...analysis.rows].sort((a: any, b: any) =>
            (Number(b['AWA %']) - Number(a['AWA %'])) || String(a.Entidad).localeCompare(String(b.Entidad), 'es')
          )
          const chartRows = rankedRows.map((r: any) => ({ name: r.Entidad, tom: r['TOM %'], espontaneo: r['Espontaneo %'], ayudado: r['Ayudado %'] }))
          const imageRows = toAwarenessImageRows(rankedRows)
          const baseText = `Base: ${Number(result?.base || 0).toLocaleString('es-CO')} encuestados${result?.rows_total && result.rows_total !== result.base ? ` de ${Number(result.rows_total).toLocaleString('es-CO')} del estudio` : ''}${result?.segment_column ? ` · Segmento: ${result.segment_value}` : ''}`
          const filePart = String(analysis.name || 'awareness').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-zA-Z0-9_-]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 50) || 'awareness'
          return <div className="awareness-analysis-result" key={analysis.name}>
            <div className="awa-result-toolbar">
              <h4>{analysis.name}</h4>
              <div className="awa-export-actions">
                <button className="button-secondary" disabled={!imageRows.length} onClick={() => downloadAwarenessChartImage(imageRows, { title: `Awareness · ${analysis.name}`, subtitle: baseText, filename: `${filePart}_grafico.png` }).catch((err) => onNotice({ text: (err as Error).message, error: true }))}><BarChart3 size={14} /> Descargar gráfico</button>
                <button className="button-secondary" disabled={!imageRows.length} onClick={() => downloadAwarenessTableImage(imageRows, { title: `Awareness · ${analysis.name}`, subtitle: baseText, filename: `${filePart}_tabla.png` }).catch((err) => onNotice({ text: (err as Error).message, error: true }))}><ArrowDownToLine size={14} /> Descargar tabla</button>
              </div>
            </div>
            <div id={`integrated-awareness-chart-${analysisIndex}`} className="chart-wrap"><ResponsiveContainer width="100%" height={Math.max(260, chartRows.length * 40)}><BarChart data={chartRows} layout="vertical" margin={{ left: 18, right: 26 }}><CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e9edf3" /><XAxis type="number" tickFormatter={(v) => `${Math.round(v * 100)}%`} axisLine={false} tickLine={false} /><YAxis type="category" dataKey="name" width={130} reversed axisLine={false} tickLine={false} /><Tooltip formatter={(v: any) => `${(Number(v) * 100).toFixed(1)}%`} /><Bar dataKey="tom" name="TOM" stackId="a" fill="#315bdb" /><Bar dataKey="espontaneo" name="Espontáneo" stackId="a" fill="#18a994" /><Bar dataKey="ayudado" name="Ayudado" stackId="a" fill="#ef9b46" /></BarChart></ResponsiveContainer></div>
            <div className="table-scroll"><table><thead><tr><th>Marca</th><th>TOM</th><th>Espontáneo</th><th>Ayudado</th><th>AWA</th></tr></thead><tbody>{rankedRows.map((r: any) => <tr key={r.Entidad}><td>{r.Entidad}</td><td>{(r['TOM %'] * 100).toFixed(1)}%</td><td>{(r['Espontaneo %'] * 100).toFixed(1)}%</td><td>{(r['Ayudado %'] * 100).toFixed(1)}%</td><td><b>{(r['AWA %'] * 100).toFixed(1)}%</b></td></tr>)}</tbody></table></div>
          </div>
        }) : <div className="empty-panel large-empty"><div className="empty-icon"><UsersRound size={20} /></div><b>Configura ambos análisis</b><span>El flujo usará las respuestas categorizadas y calculará TOM, espontáneo y ayudado por separado para cada perfil.</span></div>}
      </section>
    </div>
  </>
}
