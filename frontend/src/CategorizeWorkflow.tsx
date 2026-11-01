import { useEffect, useMemo, useState } from 'react'
import { ArrowDownToLine, ArrowRight, Check, ChevronDown, LoaderCircle, MessageSquareText, Plus, Search, Sparkles, Tags, WandSparkles, X } from 'lucide-react'

type PageStudy = {
  id: string; name: string; columns: string[]; row_count: number; suggested_questions?: string[];
  classifications?: Classification[];
}
type Category = { nombre: string; descripcion: string; palabras_clave?: string }
type Classification = {
  id: string; question: string; kind: 'brands' | 'themes' | 'sentiment'; categories: string[];
  codeframe: Category[]; config: Record<string, any>;
}
type Draft = {
  id: string; question: string; kind: 'themes' | 'brands' | 'sentiment'; codeframe: Category[];
  known_brands: string[]; context: string; multi: boolean; provider: string; model: string;
}
type ReviewRow = { row_index: number; response: string | null; labels: string[] }

const BRAND_NONE = 'Ninguna'
const NSNR = 'NS/NR'
const SENTIMENT_FRAME: Category[] = [
  { nombre: 'Positivo', descripcion: 'Expresa satisfacción, aprobación o una valoración favorable.' },
  { nombre: 'Neutral', descripcion: 'Describe hechos o preferencias sin una valoración emocional clara.' },
  { nombre: 'Negativo', descripcion: 'Expresa insatisfacción, rechazo o una valoración desfavorable.' },
  { nombre: 'Mixto/ambivalente', descripcion: 'Combina elementos positivos y negativos o expresa sentimientos contradictorios.' },
]

async function request<T>(path: string, options: RequestInit = {}, apiKey = ''): Promise<T> {
  const headers = new Headers(options.headers)
  const accessToken = sessionStorage.getItem("insights-token")
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`)
  if (apiKey) headers.set('X-LLM-API-Key', apiKey)
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  const response = await fetch(path, { ...options, headers })
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(body.detail || 'Error al consultar el backend.')
  }
  return response.json() as Promise<T>
}

export default function CategorizeWorkflow({ study, apiKey, provider, model, onRefresh, onNotice, busy, setBusy }: any) {
  // Las sugerencias ayudan a empezar, pero la lista de trabajo conserva todos los encabezados exactos del Excel.
  const questions: string[] = useMemo(() => study?.columns || [], [study?.id, study?.columns])
  const [question, setQuestion] = useState('')
  const [selectedQuestions, setSelectedQuestions] = useState<string[]>([])
  const [columnSearch, setColumnSearch] = useState('')
  const [batchProgress, setBatchProgress] = useState('')
  const [kind, setKind] = useState<'themes' | 'brands' | 'sentiment'>('themes')
  const [context, setContext] = useState('')
  const [knownText, setKnownText] = useState('')
  const [frame, setFrame] = useState<Category[]>([])
  const [multi, setMulti] = useState(true)
  const [step, setStep] = useState<1 | 2 | 3>(1)
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [rows, setRows] = useState<ReviewRow[]>([])
  const [offset, setOffset] = useState(0)
  const [edits, setEdits] = useState<Record<number, string[]>>({})
  const [isReady, setIsReady] = useState(false)

  const classifications: Classification[] = study?.classifications || []
  const currentClassification = classifications.find((item) => item.question === question)
  const currentDraft = drafts.find((item) => item.question === question)
  const knownBrands = useMemo(() => knownText.split(/\r?\n/).map((v) => v.trim()).filter(Boolean), [knownText])

  useEffect(() => {
    let cancelled = false
    async function initialize() {
      if (!study?.id) return
      setIsReady(false)
      const first = study.suggested_questions?.[0] || questions[0] || ''
      try {
        const saved = await request<Draft[]>(`/api/studies/${study.id}/drafts`)
        if (cancelled) return
        setDrafts(saved)
        setSelectedQuestions((study.suggested_questions || []).filter((column: string) => questions.includes(column)))
        setQuestion((current) => current && questions.includes(current) ? current : first)
      } catch (err) {
        if (!cancelled) onNotice({ text: (err as Error).message, error: true })
      } finally {
        if (!cancelled) setIsReady(true)
      }
    }
    initialize()
    return () => { cancelled = true }
  }, [study?.id])

  useEffect(() => {
    if (!question || !isReady) return
    const draft = drafts.find((item) => item.question === question)
    const complete = classifications.find((item) => item.question === question)
    if (draft) {
      setKind(draft.kind); setContext(draft.context || ''); setFrame(draft.codeframe || [])
      setKnownText((draft.known_brands || []).join('\n')); setMulti(draft.multi ?? true); setStep(2)
    } else if (complete) {
      setKind(complete.kind); setContext(complete.config?.context || ''); setFrame(complete.codeframe || [])
      setKnownText((complete.config?.known_brands || []).join('\n')); setMulti(complete.config?.multi ?? true); setStep(3)
    } else {
      setKind('themes'); setContext(''); setFrame([]); setKnownText(''); setMulti(true); setStep(1)
    }
    setRows([]); setOffset(0); setEdits({})
  }, [question, study?.id, isReady])

  useEffect(() => {
    let cancelled = false
    async function loadRows() {
      if (!currentClassification || step !== 3) { setRows([]); return }
      try {
        const result = await request<{ rows: ReviewRow[] }>(`/api/classifications/${currentClassification.id}/rows?offset=0&limit=100`)
        if (!cancelled) { setRows(result.rows); setOffset(0) }
      } catch (err) { if (!cancelled) onNotice({ text: (err as Error).message, error: true }) }
    }
    loadRows()
    return () => { cancelled = true }
  }, [currentClassification?.id, step])

  function payload(questionValue = question, kindValue = kind, frameValue = frame) {
    const codeframe = kindValue === 'sentiment' ? SENTIMENT_FRAME : kindValue === 'brands' ? [] : frameValue.filter((item) => item.nombre.trim())
    return { question: questionValue, kind: kindValue, codeframe, known_brands: knownBrands, context, multi: kindValue === 'sentiment' ? false : multi, provider, model }
  }

  async function fetchConsolidatedWorkbook() {
    const token = sessionStorage.getItem('insights-token')
    const response = await fetch(`/api/studies/${study.id}/export-categorizations`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!response.ok) {
      const body = await response.json().catch(() => ({ detail: response.statusText }))
      throw new Error(body.detail || 'No se pudo generar el Excel consolidado.')
    }
    const blob = await response.blob()
    const disposition = response.headers.get('Content-Disposition') || ''
    const filename = disposition.match(/filename="?([^";]+)"?/i)?.[1] || 'estudio_categorizaciones.xlsx'
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url; anchor.download = filename; document.body.appendChild(anchor); anchor.click(); anchor.remove()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    return filename
  }

  async function downloadConsolidatedWorkbook() {
    setBusy(true); setBatchProgress('Generando Excel consolidado…')
    try {
      const filename = await fetchConsolidatedWorkbook()
      onNotice({ text: `Excel consolidado descargado: ${filename}` })
    } catch (err) { onNotice({ text: (err as Error).message, error: true }) }
    finally { setBatchProgress(''); setBusy(false) }
  }

  async function saveDraft() {
    const saved = await request<Draft>(`/api/studies/${study.id}/drafts`, {
      method: 'PUT', body: JSON.stringify(payload()),
    })
    setDrafts((existing) => [...existing.filter((item) => item.question !== question), saved])
    return saved
  }

  async function goToReview() {
    if (!study || !question) return
    if (kind === 'brands' && !knownBrands.length) {
      onNotice({ text: 'Agrega al menos una marca permitida antes de revisar el catálogo.', error: true }); return
    }
    setBusy(true)
    try {
      if (kind === 'sentiment') {
        setFrame(SENTIMENT_FRAME)
        const saved = await request<Draft>(`/api/studies/${study.id}/drafts`, { method: 'PUT', body: JSON.stringify(payload(question, 'sentiment', SENTIMENT_FRAME)) })
        setDrafts((existing) => [...existing.filter((item) => item.question !== question), saved])
      } else if (kind === 'themes' && frame.filter((item) => item.nombre.trim()).length === 0) {
        
        const result = await request<{ codeframe: Category[] }>(`/api/studies/${study.id}/propose-categories`, {
          method: 'POST', body: JSON.stringify({ question, context, provider, model, max_categories: 10 }),
        }, apiKey)
        setFrame(result.codeframe)
        const saved = await request<Draft>(`/api/studies/${study.id}/drafts`, {
          method: 'PUT', body: JSON.stringify(payload(question, 'themes', result.codeframe)),
        })
        setDrafts((existing) => [...existing.filter((item) => item.question !== question), saved])
      } else {
        await saveDraft()
      }
      setStep(2)
      onNotice({ text: 'Catálogo guardado como borrador. Revísalo y ajústalo antes de clasificar.' })
    } catch (err) { onNotice({ text: (err as Error).message, error: true }) }
    finally { setBusy(false) }
  }

  async function classify() {
    
    if (kind === 'themes' && frame.filter((item) => item.nombre.trim()).length === 0) {
      onNotice({ text: 'El catálogo debe tener al menos una categoría.', error: true }); return
    }
    if (kind === 'brands' && !knownBrands.length) {
      onNotice({ text: 'El catálogo de marcas está vacío.', error: true }); return
    }
    setBusy(true)
    try {
      await saveDraft()
      const result = await request<any>(`/api/studies/${study.id}/classifications`, {
        method: 'POST', body: JSON.stringify({ ...payload(), max_categories: 10 }),
      }, apiKey)
      setDrafts((existing) => existing.filter((item) => item.question !== question))
      await onRefresh(study.id)
      const fetched = await request<{ rows: ReviewRow[] }>(`/api/classifications/${result.id}/rows?offset=0&limit=100`)
      setRows(fetched.rows); setOffset(0); setEdits({}); setStep(3)
      onNotice({ text: `Clasificación terminada para esta pregunta: ${result.categories.length} etiquetas disponibles. Corrige las filas que necesites y guarda.` })
    } catch (err) { onNotice({ text: (err as Error).message, error: true }) }
    finally { setBusy(false) }
  }

  async function classifySelected() {
    const chosen = questions.filter((column) => selectedQuestions.includes(column))
    if (!chosen.length) { onNotice({ text: 'Selecciona al menos una columna para clasificar.', error: true }); return }
    if (kind === 'brands' && !knownBrands.length) { onNotice({ text: 'Define la lista de marcas antes de procesar el lote.', error: true }); return }
    const pending = chosen.filter((column) => !classifications.some((item) => item.question === column))
    if (!pending.length) { onNotice({ text: 'Todas las columnas seleccionadas ya tienen clasificación. Puedes revisarlas o reclasificar una individualmente.', error: true }); return }
    setBusy(true)
    const completed: string[] = []
    let failure = ''
    try {
      for (let index = 0; index < pending.length; index += 1) {
        const column = pending[index]
        setBatchProgress(`Clasificando ${index + 1} de ${pending.length}: ${column}`)
        let codeframe: Category[] = []
        if (kind === 'sentiment') {
          codeframe = SENTIMENT_FRAME
        } else if (kind === 'themes') {
          const savedDraft = drafts.find((draft) => draft.question === column && draft.kind === 'themes')
          codeframe = column === question ? frame.filter((item) => item.nombre.trim()) : (savedDraft?.codeframe || []).filter((item) => item.nombre.trim())
          if (!codeframe.length) {
            const proposal = await request<{ codeframe: Category[] }>(`/api/studies/${study.id}/propose-categories`, {
              method: 'POST', body: JSON.stringify({ question: column, context, provider, model, max_categories: 10 }),
            }, apiKey)
            codeframe = proposal.codeframe
          }
        }
        await request(`/api/studies/${study.id}/classifications`, {
          method: 'POST', body: JSON.stringify({ ...payload(column, kind, codeframe), max_categories: 10 }),
        }, apiKey)
        completed.push(column)
      }
    } catch (err) {
      failure = (err as Error).message
    }
    if (completed.length) {
      try { await onRefresh(study.id) } catch { /* Los resultados individuales ya se guardaron en la API. */ }
      setQuestion(completed[0]); setStep(3)
    }
    let exportFilename = ''
    let exportError = ''
    if (!failure && completed.length) {
      setBatchProgress('Generando Excel consolidado…')
      try { exportFilename = await fetchConsolidatedWorkbook() }
      catch (err) { exportError = (err as Error).message }
    }
    setBatchProgress(''); setBusy(false)
    if (failure) onNotice({ text: `Se completaron ${completed.length} de ${pending.length} columnas; las anteriores quedaron guardadas. Se detuvo por: ${failure}`, error: true })
    else if (exportError) onNotice({ text: `Lote terminado y guardado, pero no se pudo descargar el Excel automáticamente: ${exportError}. Usa “Descargar Excel consolidado” en la revisión.`, error: true })
    else onNotice({ text: `Lote terminado: ${completed.length} columnas clasificadas una por una. Se descargó ${exportFilename}; puedes revisar cada pregunta y volver a descargarlo tras guardar correcciones.` })
  }

  async function loadMore() {
    if (!currentClassification) return
    const next = offset + 100
    try {
      const result = await request<{ rows: ReviewRow[] }>(`/api/classifications/${currentClassification.id}/rows?offset=${next}&limit=100`)
      setRows((existing) => [...existing, ...result.rows]); setOffset(next)
    } catch (err) { onNotice({ text: (err as Error).message, error: true }) }
  }

  async function saveEdits() {
    if (!currentClassification) return
    const changes = Object.entries(edits).map(([row_index, labels]) => ({ row_index: Number(row_index), labels }))
    if (!changes.length) { onNotice({ text: 'No tienes correcciones pendientes.' }); return }
    setBusy(true)
    try {
      await request(`/api/classifications/${currentClassification.id}/labels`, {
        method: 'PATCH', body: JSON.stringify({ changes }),
      })
      setRows((existing) => existing.map((row) => edits[row.row_index] ? { ...row, labels: edits[row.row_index] } : row))
      setEdits({})
      await onRefresh(study.id)
      onNotice({ text: `Se guardaron ${changes.length} correcciones en PostgreSQL.` })
    } catch (err) { onNotice({ text: (err as Error).message, error: true }) }
    finally { setBusy(false) }
  }

  async function nextQuestion() {
    const index = questions.indexOf(question)
    if (index >= 0 && index + 1 < questions.length) await switchQuestion(questions[index + 1])
    else onNotice({ text: 'Ya revisaste la última pregunta del estudio.' })
  }

  async function switchQuestion(next: string) {
    if (!next || next === question) return
    if (step === 2) {
      setBusy(true)
      try { await saveDraft() }
      catch (err) { onNotice({ text: (err as Error).message, error: true }); return }
      finally { setBusy(false) }
    }
    setQuestion(next)
  }

  if (!study) return <div className="empty-state"><div className="empty-state-mark"><Tags size={25} /></div><h2>Carga o selecciona un estudio</h2><p>La categorización se activa cuando tengas una encuesta lista.</p></div>
  if (!isReady) return <div className="empty-panel"><LoaderCircle className="spin" size={20} /><b>Cargando borradores del estudio…</b></div>

  const completionText = (q: string) => classifications.some((item) => item.question === q) ? 'Lista' : drafts.some((item) => item.question === q) ? 'Borrador' : 'Pendiente'
  const canGoNext = questions.indexOf(question) >= 0 && questions.indexOf(question) < questions.length - 1
  const reviewLabels = currentClassification?.categories || []
  const filteredQuestions = questions.filter((column) => column.toLocaleLowerCase().includes(columnSearch.trim().toLocaleLowerCase()))
  const allQuestionsSelected = questions.length > 0 && selectedQuestions.length === questions.length
  const pendingSelectedCount = selectedQuestions.filter((column) => !classifications.some((item) => item.question === column)).length

  return <>
    <div className="page-heading"><div><div className="eyebrow">CODIFICACIÓN ASISTIDA</div><h1>Categorización</h1><p>Trabaja pregunta por pregunta. El catálogo queda guardado como borrador y puedes revisarlo antes de aplicar la IA.</p></div><span className="soft-badge">{study.row_count.toLocaleString()} respuestas</span></div>
    <div className="question-workspace">
      <aside className="card question-nav-card"><div className="card-label">PREGUNTAS DEL ESTUDIO</div><div className="question-nav-title">{questions.length} columnas disponibles</div><div className="question-nav-list">{questions.map((q, index) => <button className={`question-nav-item ${q === question ? 'selected' : ''}`} key={q} onClick={() => switchQuestion(q)}><span className="question-nav-num">{String(index + 1).padStart(2, '0')}</span><span className="question-nav-text">{q}</span><span className={`question-status ${completionText(q) === 'Lista' ? 'done' : completionText(q) === 'Borrador' ? 'draft' : ''}`}>{completionText(q)}</span></button>)}</div></aside>
      <section className="workflow-main">
        <div className="stepper workflow-stepper">{([1, 2, 3] as const).map((number, index) => <div className="step-wrap" key={number}><div className={`step ${step === number ? 'active' : ''} ${step > number ? 'complete' : ''}`}><span>{step > number ? <Check size={12} /> : `0${number}`}</span><b>{number === 1 ? 'Configurar' : number === 2 ? 'Revisar catálogo' : 'Clasificar y editar'}</b></div>{index < 2 && <div className={`step-line ${step > number ? 'done' : ''}`} />}</div>)}</div>

        {step === 1 && <section className="card form-card workflow-card">
          <div className="card-heading"><div><div className="card-label">PASO 01 · CONFIGURAR</div><h3>¿Qué quieres analizar?</h3></div><span className="soft-badge">Pregunta {Math.max(questions.indexOf(question) + 1, 1)} de {questions.length}</span></div>
          <label>Columna para configurar<select value={question} onChange={(e) => switchQuestion(e.target.value)}>{questions.map((q) => <option key={q} value={q}>{q}</option>)}</select></label>
          <div className="column-picker"><div className="column-picker-heading"><b>Columnas del Excel para procesar</b><span>{selectedQuestions.length} de {questions.length} seleccionadas</span></div><div className="column-picker-tools"><label className="column-search"><Search size={14} /><input value={columnSearch} onChange={(e) => setColumnSearch(e.target.value)} placeholder="Buscar código, ej. CE1 o CA1_2" /></label><button className="button-text" onClick={() => setSelectedQuestions(allQuestionsSelected ? [] : [...questions])}>{allQuestionsSelected ? 'Desmarcar todas' : 'Seleccionar todas'}</button></div><div className="column-check-list">{filteredQuestions.map((column) => <label key={column} className="column-check-item"><input type="checkbox" checked={selectedQuestions.includes(column)} onChange={(event) => setSelectedQuestions((current) => event.target.checked ? [...questions.filter((item) => current.includes(item) || item === column)] : current.filter((item) => item !== column))} /><span>{column}</span>{(study.suggested_questions || []).includes(column) && <small>Sugerida</small>}</label>)}{filteredQuestions.length === 0 && <span className="muted">No se encontraron columnas.</span>}</div><small className="field-help">Cada encabezado se trata por separado: CE1, CE1_1 y CA1_2 son columnas distintas. El botón Seleccionar todas incluye todas las columnas: deja sin marcar IDs y campos demográficos/cerrados que no quieras categorizar.</small></div>
          <div className="field-label">Tipo de análisis</div>
          <div className="segmented"><button className={kind === 'themes' ? 'selected' : ''} onClick={() => { setKind('themes'); setFrame([]) }}><MessageSquareText size={16} /> Temas / motivos</button><button className={kind === 'brands' ? 'selected' : ''} onClick={() => { setKind('brands'); setFrame([]) }}><Tags size={16} /> Marcas</button><button className={kind === 'sentiment' ? 'selected' : ''} onClick={() => { setKind('sentiment'); setMulti(false); setFrame(SENTIMENT_FRAME) }}><Sparkles size={16} /> Sentimiento</button></div>
          {kind === 'themes' ? <><label>Contexto del estudio <span className="optional">OPCIONAL</span><textarea rows={3} value={context} onChange={(e) => setContext(e.target.value)} placeholder="Producto, categoría, mercado o instrucciones para el análisis…" /></label><div className="inline-actions"><button className="button-secondary" disabled={busy} onClick={async () => { setBusy(true); try { const result = await request<{ codeframe: Category[] }>(`/api/studies/${study.id}/propose-categories`, { method: 'POST', body: JSON.stringify({ question, context, provider, model, max_categories: 10 }) }, apiKey); setFrame(result.codeframe); onNotice({ text: `Propuesta lista: ${result.codeframe.length} categorías. Pulsa Continuar para guardarla y revisarla.` }) } catch (err) { onNotice({ text: (err as Error).message, error: true }) } finally { setBusy(false) } }}><WandSparkles size={16} /> Proponer categorías con IA</button><span className="muted">La propuesta no clasifica todavía.</span></div><label className="check-row"><input type="checkbox" checked={multi} onChange={(e) => setMulti(e.target.checked)} /><span>Permitir varias categorías por respuesta</span></label></> : kind === 'brands' ? <><label>Marcas permitidas <span className="optional">UNA POR LÍNEA</span><textarea rows={7} value={knownText} onChange={(e) => setKnownText(e.target.value)} placeholder={'Nike\nAdidas\nPuma'} /><small className="field-help">La IA asigna marcas del catálogo; una marca real fuera de la lista será “Otra”. “Ninguna” se reserva para respuestas explícitas sin marca y NS/NR para falta de información.</small></label><label className="check-row"><input type="checkbox" checked={!multi} onChange={(e) => setMulti(!e.target.checked)} /><span>Solo la primera marca mencionada (primera mención / TOM)</span></label>{!multi && <small className="field-help">Con esta opción cada respuesta queda con una sola marca: la primera que aparece. Si esa primera marca no está en tu lista, queda como “Otra”.</small>}</> : null}
          {kind === 'sentiment' && <><div className="info-callout"><Sparkles size={16} /><span>Se aplicarán las mismas etiquetas a cada columna: Positivo, Neutral, Negativo y Mixto/ambivalente. La IA procesa una columna a la vez.</span></div><label>Contexto del estudio <span className="optional">OPCIONAL</span><textarea rows={2} value={context} onChange={(e) => setContext(e.target.value)} placeholder="Contexto para interpretar las respuestas…" /></label></>}
          <button className="button-primary full-width classify-button" disabled={busy || !question} onClick={goToReview}>{busy ? <><LoaderCircle className="spin" size={16} /> Guardando…</> : <>Continuar a revisar catálogo <ArrowRight size={16} /></>}</button>
        </section>}

        {step === 2 && <section className="card form-card workflow-card">
          <div className="card-heading"><div><div className="card-label">PASO 02 · REVISAR CATÁLOGO</div><h3>{kind === 'brands' ? 'Marcas permitidas' : kind === 'sentiment' ? 'Etiquetas de sentimiento' : 'Categorías propuestas'}</h3></div><button className="button-text" onClick={() => setStep(1)}>Volver a configurar</button></div>
          <div className="review-question-banner"><span className="card-label">PREGUNTA SELECCIONADA</span><b>{question}</b><small>Revisa y corrige el catálogo. Aún no se han asignado etiquetas a las respuestas.</small></div>
          {kind === 'themes' ? <div className="codeframe-editor"><div className="editor-heading"><div><b>Catálogo de categorías</b><small>{frame.filter((item) => item.nombre.trim()).length} categorías</small></div><button className="icon-button" title="Agregar categoría" onClick={() => setFrame((items) => [...items, { nombre: '', descripcion: '', palabras_clave: '' }])}><Plus size={17} /></button></div>{frame.length === 0 ? <div className="empty-frame"><Sparkles size={18} /><span>Usa “Proponer categorías con IA” o agrega una categoría manualmente.</span></div> : frame.map((item, index) => <div className="category-edit-row" key={index}><span className="category-num">{String(index + 1).padStart(2, '0')}</span><input value={item.nombre} placeholder="Nombre de la categoría" onChange={(e) => setFrame((items) => items.map((v, i) => i === index ? { ...v, nombre: e.target.value } : v))} /><input value={item.descripcion} placeholder="Qué incluye (opcional)" onChange={(e) => setFrame((items) => items.map((v, i) => i === index ? { ...v, descripcion: e.target.value } : v))} /><input value={item.palabras_clave || ""} placeholder="Diccionario: sinónimos, separados por coma" onChange={(e) => setFrame((items) => items.map((v, i) => i === index ? { ...v, palabras_clave: e.target.value } : v))} /><button className="tiny-icon" title="Eliminar" onClick={() => setFrame((items) => items.filter((_, i) => i !== index))}><X size={15} /></button></div>)}</div> : kind === 'sentiment' ? <div className="brand-review-list">{SENTIMENT_FRAME.map((item, index) => <div className="sentiment-review-row" key={item.nombre}><span>{String(index + 1).padStart(2, '0')}</span><div><b>{item.nombre}</b><small>{item.descripcion}</small></div></div>)}</div> : <><div className="brand-review-list">{knownBrands.map((brand, index) => <div className="brand-review-row" key={`${brand}-${index}`}><span>{String(index + 1).padStart(2, '0')}</span><b>{brand}</b><Check size={15} /></div>)}</div><button className="button-secondary" onClick={() => setStep(1)}>Editar lista de marcas</button></>}
          <div className="info-callout"><Check size={16} /><span>Este borrador se guarda en PostgreSQL por estudio y pregunta. Puedes salir y retomarlo después.</span></div>
          <button className="button-primary full-width classify-button" disabled={busy || (kind === 'themes' ? !frame.some((item) => item.nombre.trim()) : kind === 'brands' ? !knownBrands.length : false)} onClick={classify}>{busy ? <><LoaderCircle className="spin" size={16} /> Clasificando respuestas…</> : <><Sparkles size={16} /> Clasificar solo {question}</>}</button><div className="batch-classify-box"><div><b>Procesamiento secuencial</b><small>{pendingSelectedCount} columnas pendientes de las {selectedQuestions.length} seleccionadas; las ya clasificadas se omiten.</small></div>{batchProgress && <span className="batch-progress">{batchProgress}</span>}<button className="button-secondary full-width" disabled={busy || pendingSelectedCount === 0} onClick={classifySelected}>{busy && batchProgress ? <><LoaderCircle className="spin" size={15} /> {batchProgress}</> : <>Clasificar {pendingSelectedCount} columnas seleccionadas, una por una</>}</button></div>
        </section>}

        {step === 3 && <section className="card form-card workflow-card">
          <div className="card-heading"><div><div className="card-label">PASO 03 · CLASIFICAR Y EDITAR</div><h3>Revisa las etiquetas asignadas</h3></div><div className="review-actions"><button className="button-secondary" onClick={() => setStep(2)}>Revisar catálogo</button><button className="button-secondary" disabled={busy || !!Object.keys(edits).length} title={Object.keys(edits).length ? 'Guarda las correcciones pendientes antes de exportar.' : 'Descarga el estudio fuente con todas las clasificaciones guardadas.'} onClick={downloadConsolidatedWorkbook}><ArrowDownToLine size={15} /> Descargar Excel consolidado</button><button className="button-primary" disabled={busy || !Object.keys(edits).length} onClick={saveEdits}><Check size={15} /> Guardar cambios {Object.keys(edits).length ? `(${Object.keys(edits).length})` : ''}</button></div></div>
          <div className="review-question-banner"><span className="card-label">PREGUNTA</span><b>{question}</b><small>{study.row_count.toLocaleString()} respuestas · {rows.length} cargadas · Edita las etiquetas y guarda tus correcciones.</small></div>
          <div className="table-scroll workflow-review-table"><table><thead><tr><th>Fila</th><th>Respuesta</th><th>Etiqueta actual</th><th>Corregir etiquetas</th></tr></thead><tbody>{rows.map((row) => { const options = [...reviewLabels, ...(kind === 'brands' ? [BRAND_NONE] : []), NSNR, ...(kind === 'themes' ? ['Otro'] : [])].filter((value, index, all) => all.indexOf(value) === index); return <tr key={row.row_index}><td className="row-number">{row.row_index + 1}</td><td className="response-cell">{row.response || <span className="muted">(vacía)</span>}</td><td><span className="label-chip">{row.labels.join(' · ') || '—'}</span></td><td><select multiple disabled={!String(row.response ?? '').trim()} size={Math.min(Math.max(options.length, 2), 4)} value={edits[row.row_index] ?? row.labels} onChange={(e) => { let value = Array.from(e.target.selectedOptions).map((option) => option.value); const exclusive = value.find((label) => label === BRAND_NONE || label === NSNR); if (exclusive) value = [exclusive]; setEdits((current) => ({ ...current, [row.row_index]: value })) }}>{options.map((label) => <option key={label} value={label}>{label}</option>)}</select></td></tr> })}</tbody></table></div>
          {rows.length < study.row_count && <button className="button-secondary load-more" onClick={loadMore}>Cargar siguientes 100 respuestas</button>}
          <div className="workflow-bottom-actions"><span className="muted">Las correcciones se guardan para esta pregunta en PostgreSQL.</span>{canGoNext && <button className="button-secondary" onClick={nextQuestion}>Siguiente pregunta <ArrowRight size={15} /></button>}</div>
        </section>}
      </section>
    </div>
  </>
}
