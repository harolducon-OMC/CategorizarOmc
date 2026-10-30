import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Activity, ArrowDownToLine, ArrowRight, BarChart3, Check, ChevronDown, CircleHelp,
  Database, FileSpreadsheet, FolderOpen, Layers3, LayoutDashboard, LoaderCircle,
  KeyRound, MessageSquareText, Plus, Search, Settings2, Sparkles, Tags, Trash2, UploadCloud,
  UsersRound, WandSparkles, X,
} from 'lucide-react'
import {
  Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip,
  XAxis, YAxis,
} from 'recharts'
import CategorizeWorkflow from './CategorizeWorkflow'
import AwarenessStandalone from './AwarenessStandalone'
import FlowGuide from './FlowGuide'

type Page = 'home' | 'categorize' | 'dashboard' | 'awareness' | 'settings'
type Study = { id: string; name: string; source_filename: string; columns: string[]; row_count: number; created_at: string }
type Category = { nombre: string; descripcion: string }
type Classification = {
  id: string; study_id: string; question: string; kind: 'themes' | 'brands' | 'sentiment'; categories: string[];
  codeframe: Category[]; entities: string[]; aliases: Record<string, string[]>; config: Record<string, unknown>;
  has_insights: boolean; updated_at?: string;
}
type Frequency = { Categoría: string; Menciones: number; '%': number }
type ReviewRow = { row_index: number; response: string | null; labels: string[] }
type AwarenessProfile = {
  name: string
  tom_column: string
  spontaneous_columns: string[]
  aided_columns: string[]
}

const COLORS = ['#315bdb', '#18a994', '#ef9b46', '#8158cb', '#db6482', '#5e7f90', '#a9b548']
const PROVIDERS: Record<string, { label: string; model: string }> = {
  gemini: { label: 'Google Gemini', model: 'gemini-3.5-flash-lite' },
  groq: { label: 'Groq', model: 'openai/gpt-oss-20b' },
  cohere: { label: 'Cohere', model: 'command-a-plus-05-2026' },
  openrouter: { label: 'OpenRouter', model: 'xingchen-agi/xing4.0-29b-a4b:free' },
  anthropic: { label: 'Anthropic', model: 'claude-haiku-5-5' },
}

async function api<T>(path: string, options: RequestInit = {}, apiKey = ''): Promise<T> {
  const headers = new Headers(options.headers)
  const accessToken = sessionStorage.getItem("insights-token")
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`)
  if (apiKey) headers.set('X-LLM-API-Key', apiKey)
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const response = await fetch(path, { ...options, headers })
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(body.detail || 'Ocurrió un error al consultar el servidor.')
  }
  return response.json() as Promise<T>
}

function App() {
  const [page, setPage] = useState<Page>('home')
  const [studies, setStudies] = useState<Study[]>([])
  const [studyId, setStudyId] = useState(localStorage.getItem('insights-study') || '')
  const [study, setStudy] = useState<any>(null)
  const [provider, setProvider] = useState('gemini')
  const [model, setModel] = useState(PROVIDERS.gemini.model)
  const [apiKey, setApiKey] = useState('')
  const [aiMenuOpen, setAiMenuOpen] = useState(false)
  const [notice, setNotice] = useState<{ text: string; error?: boolean } | null>(null)
  const [busy, setBusy] = useState(false)
  const [authChecked, setAuthChecked] = useState(false)
  const [userEmail, setUserEmail] = useState('')

  const refreshStudies = useCallback(async (preferred?: string) => {
    const list = await api<Study[]>('/api/studies')
    setStudies(list)
    const next = (preferred && list.some((item) => item.id === preferred) ? preferred : '')
      || (list.some((item) => item.id === studyId) ? studyId : '')
      || list[0]?.id || ''
    setStudyId(next)
    if (next) localStorage.setItem('insights-study', next)
    else localStorage.removeItem('insights-study')
    return list
  }, [studyId])

  const refreshStudy = useCallback(async (id = studyId) => {
    if (!id) { setStudy(null); return }
    const result = await api<any>(`/api/studies/${id}/overview`)
    setStudy(result)
  }, [studyId, userEmail])

  useEffect(() => {
    const token = sessionStorage.getItem('insights-token')
    if (!token) { setAuthChecked(true); return }
    api<{email: string}>('/api/auth/me').then((user) => { setUserEmail(user.email); setAuthChecked(true) }).catch(() => { sessionStorage.removeItem('insights-token'); setAuthChecked(true) })
  }, [])

  useEffect(() => {
    if (!userEmail) return
    refreshStudies().catch((err) => setNotice({ text: `No se pudo conectar con la API: ${err.message}`, error: true }))
  }, [userEmail])

  useEffect(() => {
    if (!userEmail) return
    if (!studyId) { setStudy(null); return }
    // Espera a tener el catálogo actual desde la API; nunca consulta un ID viejo del navegador.
    if (!studies.length) return
    if (studies.some((item) => item.id === studyId)) {
      localStorage.setItem('insights-study', studyId)
      refreshStudy(studyId).catch((err) => setNotice({ text: err.message, error: true }))
    } else setStudy(null)
  }, [studyId, userEmail, studies, refreshStudy])

  useEffect(() => {
    if (!notice) return
    const timer = window.setTimeout(() => setNotice(null), 5500)
    return () => window.clearTimeout(timer)
  }, [notice])

  function changeProvider(value: string) {
    setProvider(value)
    setModel(PROVIDERS[value]?.model || '')
  }

  async function deleteStudy(id: string) {
    if (!window.confirm('¿Eliminar este estudio y sus clasificaciones guardadas? Esta acción no se puede deshacer.')) return
    try {
      await api(`/api/studies/${id}`, { method: 'DELETE' })
      const remaining = studies.filter((item) => item.id !== id)
      setStudies(remaining)
      const next = remaining[0]?.id || ''
      setStudyId(next)
      setNotice({ text: 'Estudio eliminado.' })
    } catch (err) { setNotice({ text: (err as Error).message, error: true }) }
  }

  const activeClassifications: Classification[] = study?.classifications || []
  const activePageTitle: Record<Page, string> = {
    home: 'Inicio', categorize: 'Categorización', dashboard: 'Dashboard', awareness: 'Awareness', settings: 'Ajustes',
  }

  if (!authChecked) return <div className="auth-shell"><div className="auth-card">Validando sesión…</div></div>
  if (!userEmail) return <AuthPage onAuthenticated={(email, token) => { sessionStorage.setItem('insights-token', token); setUserEmail(email) }} />

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-lockup"><div className="brand-symbol"><Activity size={19} /></div><div><b>insights</b><span>STUDIO</span></div></div>
        <div className="workspace-label">ESPACIO DE TRABAJO</div>
        <nav className="main-nav">
          <NavButton active={page === 'home'} onClick={() => setPage('home')} icon={<LayoutDashboard size={18} />} label="Inicio" />
          <NavButton active={page === 'categorize'} onClick={() => setPage('categorize')} icon={<Tags size={18} />} label="Categorización" />
          <NavButton active={page === 'dashboard'} onClick={() => setPage('dashboard')} icon={<BarChart3 size={18} />} label="Dashboard" />
          <NavButton active={page === 'awareness'} onClick={() => setPage('awareness')} icon={<UsersRound size={18} />} label="Awareness" />
        </nav>
        <div className="sidebar-divider" />
        <div className="workspace-label">ESTUDIO ACTIVO</div>
        <div className="sidebar-study">
          <span className="study-dot" />
          <select value={studyId} onChange={(e) => setStudyId(e.target.value)} aria-label="Estudio activo">
            <option value="">Selecciona un estudio</option>
            {studies.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
          <ChevronDown size={14} />
        </div>
        {study && <div className="study-mini"><Database size={14} /> {study.row_count.toLocaleString()} respuestas <span>·</span> {study.columns.length} campos</div>}
        <div className="sidebar-spacer" />
        <div className="sidebar-tip"><div className="tip-icon"><CircleHelp size={17} /></div><div><b>¿Necesitas ayuda?</b><span>Consulta la guía local del proyecto.</span></div></div>
        <button className={`nav-button settings-link ${page === 'settings' ? 'active' : ''}`} onClick={() => setPage('settings')}><Settings2 size={18} /><span>Ajustes</span></button>
        <div className="local-status"><span className="online-dot" /> © 2026 Propiedad OMC</div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumbs"><span>Insights Studio</span><span className="crumb-sep">/</span><b>{activePageTitle[page]}</b></div>
          <div className="topbar-right">
            <div className="ai-quick-wrap">
              <button className={`ai-quick-toggle ${aiMenuOpen ? 'open' : ''}`} onClick={() => setAiMenuOpen(!aiMenuOpen)} aria-expanded={aiMenuOpen}>
                <KeyRound size={14} /><span>IA · {PROVIDERS[provider]?.label || provider}</span><ChevronDown size={13} />
              </button>
              {aiMenuOpen && <div className="ai-quick-panel"><div className="ai-panel-heading"><div><b>Proveedor de IA</b><small>Configuración para esta sesión</small></div><button className="tiny-icon" onClick={() => setAiMenuOpen(false)} aria-label="Cerrar"><X size={15} /></button></div><label>Proveedor<select value={provider} onChange={(e) => changeProvider(e.target.value)}>{Object.entries(PROVIDERS).map(([id, item]) => <option key={id} value={id}>{item.label}</option>)}</select></label><label>Modelo<input value={model} onChange={(e) => setModel(e.target.value)} placeholder={PROVIDERS[provider]?.model} /></label><label>API key<input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="Pega tu API key" autoComplete="off" /></label><small className="ai-panel-note">Solo memoria de esta pestaña; no se guarda en PostgreSQL.</small></div>}
            </div>
            {study && <span className="top-study"><Database size={14} /> {study.name}</span>}
            <span className="local-pill"><span className="online-dot" /> Local</span>
            <button className="avatar" title={`Cerrar sesión (${userEmail})`} onClick={() => { sessionStorage.removeItem('insights-token'); setUserEmail(''); setStudies([]); setStudyId('') }}>{userEmail.slice(0,1).toUpperCase()}</button>
          </div>
        </header>
        {notice && <div className={`toast ${notice.error ? 'toast-error' : ''}`}><span>{notice.text}</span><button onClick={() => setNotice(null)}><X size={16} /></button></div>}
        <div className="page-content">
          {page === 'home' && <HomePage studies={studies} study={study} onUpload={async (file, name, sheet) => {
            const form = new FormData(); form.append('file', file); form.append('name', name); form.append('sheet', sheet)
            setBusy(true)
            try { const created = await api<Study>('/api/studies', { method: 'POST', body: form }); await refreshStudies(created.id); setNotice({ text: 'Encuesta importada y guardada en PostgreSQL.' }) }
            catch (err) { setNotice({ text: (err as Error).message, error: true }) }
            finally { setBusy(false) }
          }} busy={busy} onDelete={deleteStudy} onGo={setPage} />}
          {page === 'categorize' && <CategorizeWorkflow study={study} apiKey={apiKey} provider={provider} model={model} onRefresh={refreshStudy} onNotice={setNotice} busy={busy} setBusy={setBusy} />}
          {page === 'dashboard' && <DashboardPage study={study} apiKey={apiKey} provider={provider} model={model} onNotice={setNotice} />}
          {page === 'awareness' && <AwarenessHub study={study} onNotice={setNotice} />}
          {page === 'settings' && <SettingsPage provider={provider} model={model} apiKey={apiKey} setApiKey={setApiKey} onProvider={changeProvider} setModel={setModel} />}
        </div>
        <footer className="footer-note">Insights Studio · OMC <span>© 2026 Harold Ducon and Research.</span></footer>
      </main>
    </div>
  )
}

function AuthPage({ onAuthenticated }: { onAuthenticated: (email: string, token: string) => void }) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function submit(event: React.FormEvent) {
    event.preventDefault(); setError(''); setBusy(true)
    try {
      const data = await api<{access_token: string; email: string}>(`/api/auth/${mode}`, { method: 'POST', body: JSON.stringify({ email, password }) })
      onAuthenticated(data.email, data.access_token)
    } catch (err) { setError((err as Error).message) } finally { setBusy(false) }
  }
  return <main className="auth-shell"><form className="auth-card" onSubmit={submit}>
    <div className="auth-mark"><Activity size={20}/></div><h1>Insights Studio</h1>
    <p>{mode === 'login' ? 'Inicia sesión con tu cuenta corporativa.' : 'Crea una cuenta con correo autorizado @omc.'}</p>
    <label>Correo corporativo<input type="text" inputMode="email" required autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="nombre@omc" /></label>
    <label>Contraseña<input type="password" required minLength={12} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} value={password} onChange={e => setPassword(e.target.value)} placeholder="Mínimo 12 caracteres" /></label>
    {error && <div className="auth-error">{error}</div>}
    <button className="button-primary full-width" disabled={busy}>{busy ? 'Procesando…' : mode === 'login' ? 'Iniciar sesión' : 'Crear cuenta'}</button>
    <button type="button" className="auth-switch" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}>{mode === 'login' ? '¿Primera vez? Crear cuenta' : '¿Ya tienes cuenta? Iniciar sesión'}</button>
    <small>Acceso protegido con token de sesión. El registro requiere el dominio corporativo permitido.</small>
  </form></main>
}

function NavButton({ active, onClick, icon, label }: { active: boolean; onClick: () => void; icon: React.ReactNode; label: string }) {
  return <button className={`nav-button ${active ? 'active' : ''}`} onClick={onClick}>{icon}<span>{label}</span>{active && <span className="nav-active-mark" />}</button>
}

function PageHeading({ eyebrow, title, text, action }: { eyebrow: string; title: string; text: string; action?: React.ReactNode }) {
  return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{text}</p></div>{action && <div className="heading-action">{action}</div>}</div>
}

function HomePage({ studies, study, onUpload, busy, onDelete, onGo }: {
  studies: Study[]; study: any; busy: boolean;
  onUpload: (file: File, name: string, sheet: string) => Promise<void>;
  onDelete: (id: string) => void; onGo: (page: Page) => void;
}) {
  const [file, setFile] = useState<File | null>(null)
  const [name, setName] = useState('')
  const [sheet, setSheet] = useState('')
  const [sheets, setSheets] = useState<string[]>([])
  const [uploadError, setUploadError] = useState('')
  const [dragging, setDragging] = useState(false)
  const [guideOpen, setGuideOpen] = useState(false)
  async function selectFile(next: File | null) {
    setFile(next); setUploadError(''); setSheets([]); setSheet('')
    if (!next) return
    if (!/\.(csv|xlsx)$/i.test(next.name)) { setUploadError('Elige un archivo CSV o XLSX.'); return }
    if (next.size > 25 * 1024 * 1024) { setUploadError('El archivo supera el límite de 25 MB.'); return }
    setName(next.name.replace(/\.[^.]+$/, ''))
    if (/\.xlsx$/i.test(next.name)) {
      try {
        const form = new FormData(); form.append('file', next)
        const result = await api<{ sheets: string[] }>('/api/uploads/sheets', { method: 'POST', body: form })
        setSheets(result.sheets); setSheet(result.sheets[0] || '')
      } catch (err) { setUploadError((err as Error).message) }
    }
  }
  return <>
    <PageHeading eyebrow="VISTA GENERAL" title="Tu espacio de análisis" text="Carga una encuesta, categoriza respuestas y convierte la voz de tus clientes en decisiones." action={<div className="secure-chip"><Database size={15} /> Privado en tu entorno</div>} />
    <div className="welcome-strip"><div className="welcome-icon"><Sparkles size={19} /></div><div><b>Bienvenido a Insights Studio</b><span>Un flujo de investigación más claro: importa, codifica, explora y exporta desde una sola vista.</span></div><button onClick={() => setGuideOpen(true)}>Ver flujo <ArrowRight size={15} /></button></div>
    {guideOpen && <FlowGuide hasStudy={!!study} onClose={() => setGuideOpen(false)} onGo={onGo} />}
    <div className="section-title-row"><div><h2>Importar una encuesta</h2><p>Se guardará en PostgreSQL para continuar después.</p></div><span className="file-limit">CSV o XLSX · Hasta 25 MB</span></div>
    <div className="upload-layout">
      <div className={`upload-card ${dragging ? 'dragging' : ''}`} onDragOver={(e) => { e.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={(e) => { e.preventDefault(); setDragging(false); selectFile(e.dataTransfer.files[0] || null) }}>
        <input id="file-input" type="file" accept=".csv,.xlsx" onChange={(e) => selectFile(e.target.files?.[0] || null)} hidden />
        <div className="upload-icon"><UploadCloud size={26} /></div>
        <h3>{file ? file.name : 'Arrastra tu archivo aquí'}</h3>
        <p>{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB listo para importar` : 'o selecciona una encuesta desde tu computador'}</p>
        <label className="button-secondary" htmlFor="file-input">{file ? 'Cambiar archivo' : 'Seleccionar archivo'}</label>
        {uploadError && <div className="inline-error">{uploadError}</div>}
      </div>
      <div className="upload-form card">
        <div className="card-label">DETALLES DEL ESTUDIO</div>
        <label>Nombre del estudio<input value={name} onChange={(e) => setName(e.target.value)} placeholder="Ej. Seguimiento de marca Q4" /></label>
        {sheets.length > 1 && <label>Hoja de Excel<select value={sheet} onChange={(e) => setSheet(e.target.value)}>{sheets.map((item) => <option key={item}>{item}</option>)}</select></label>}
        <div className="helper-text"><FileSpreadsheet size={14} /> Cada fila debe representar una respuesta.</div>
        <button className="button-primary full-width" disabled={!file || busy || !!uploadError} onClick={() => file && onUpload(file, name, sheet)}>{busy ? <><LoaderCircle className="spin" size={16} /> Importando...</> : <>Importar encuesta <ArrowRight size={16} /></>}</button>
      </div>
    </div>
    {study && <>
      <div className="section-title-row mt-32"><div><h2>Estudio activo</h2><p>Vista previa del archivo y acceso a las herramientas.</p></div><button className="button-text danger" onClick={() => onDelete(study.id)}><Trash2 size={15} /> Eliminar estudio</button></div>
      <div className="metric-grid">
        <MetricCard icon={<UsersRound />} label="Respuestas" value={study.row_count.toLocaleString()} sub="filas de encuesta" color="blue" />
        <MetricCard icon={<Layers3 />} label="Variables" value={study.columns.length} sub="campos detectados" color="mint" />
        <MetricCard icon={<Tags />} label="Preguntas abiertas" value={study.suggested_questions?.length || 0} sub="recomendadas; puedes elegir cualquier columna" color="orange" />
        <MetricCard icon={<BarChart3 />} label="Clasificaciones" value={study.classifications?.length || 0} sub="guardadas en este estudio" color="purple" />
      </div>
      <div className="card preview-card"><div className="card-heading"><div><div className="card-label">MUESTRA DE DATOS</div><h3>{study.name}</h3></div><span className="muted">{study.source_filename}</span></div><DataTable columns={study.columns || []} rows={study.preview || []} /></div>
      <div className="quick-actions"><button className="quick-action" onClick={() => onGo('categorize')}><span className="qa-icon blue"><Tags size={18} /></span><span><b>Categorizar respuestas</b><small>Crear temas o detectar marcas</small></span><ArrowRight size={17} /></button><button className="quick-action" onClick={() => onGo('dashboard')}><span className="qa-icon mint"><BarChart3 size={18} /></span><span><b>Explorar resultados</b><small>Frecuencias, segmentos e insights</small></span><ArrowRight size={17} /></button></div>
    </>}
    {studies.length > 0 && !study && <div className="card muted-card">Selecciona uno de tus estudios en el menú lateral para continuar.</div>}
  </>
}

function MetricCard({ icon, label, value, sub, color }: { icon: React.ReactNode; label: string; value: string | number; sub: string; color: string }) {
  return <div className="metric-card"><div className={`metric-icon ${color}`}>{icon}</div><div><span>{label}</span><strong>{value}</strong><small>{sub}</small></div></div>
}

function DataTable({ columns, rows }: { columns: string[]; rows: Record<string, any>[] }) {
  if (!rows.length) return <div className="empty-inline">Sin filas para mostrar.</div>
  return <div className="table-scroll"><table><thead><tr>{columns.slice(0, 8).map((c) => <th key={c}>{c}</th>)}</tr></thead><tbody>{rows.slice(0, 8).map((row, i) => <tr key={i}>{columns.slice(0, 8).map((c) => <td key={c}>{String(row[c] ?? '—').slice(0, 90)}</td>)}</tr>)}</tbody></table></div>
}

function CategorizePage({ study, apiKey, provider, model, onRefresh, onNotice, busy, setBusy }: any) {
  const [question, setQuestion] = useState('')
  const [kind, setKind] = useState<'themes' | 'brands'>('themes')
  const [context, setContext] = useState('')
  const [knownText, setKnownText] = useState('')
  const [frame, setFrame] = useState<Category[]>([])
  const [multi, setMulti] = useState(true)
  const questions: string[] = study?.suggested_questions?.length ? study.suggested_questions : study?.columns || []
  useEffect(() => { setQuestion(study?.suggested_questions?.[0] || study?.columns?.[0] || ''); setFrame([]) }, [study?.id])
  async function propose() {
    if (!study || !question) { onNotice({ text: 'Selecciona una pregunta.', error: true }); return }
    setBusy(true)
    try {
      const result = await api<{ codeframe: Category[] }>(`/api/studies/${study.id}/propose-categories`, {
        method: 'POST', body: JSON.stringify({ question, context, provider, model, max_categories: 10 }),
      }, apiKey)
      setFrame(result.codeframe)
      onNotice({ text: `Se propusieron ${result.codeframe.length} categorías. Puedes editar el catálogo antes de clasificar.` })
    } catch (err) { onNotice({ text: (err as Error).message, error: true }) }
    finally { setBusy(false) }
  }
  async function classify() {
    if (!study || !question) return
    
    if (kind === 'themes' && !frame.length) { onNotice({ text: 'Primero propone o agrega categorías.', error: true }); return }
    setBusy(true)
    try {
      const result = await api<any>(`/api/studies/${study.id}/classifications`, {
        method: 'POST', body: JSON.stringify({
          question, kind, codeframe: frame, known_brands: knownText.split('\n').map((v) => v.trim()).filter(Boolean),
          context, multi, provider, model, max_categories: 10,
        }),
      }, apiKey)
      await onRefresh(study.id)
      onNotice({ text: `Clasificación guardada · ${result.categories.length} categorías disponibles.` })
    } catch (err) { onNotice({ text: (err as Error).message, error: true }) }
    finally { setBusy(false) }
  }
  if (!study) return <EmptyState title="Carga o selecciona un estudio" text="La categorización se activa cuando tengas una encuesta lista." action="Ir a Inicio" />
  return <>
    <PageHeading eyebrow="CODIFICACIÓN ASISTIDA" title="Categorización" text="Define el catálogo, aplica la IA y revisa las etiquetas con control total." />
    <div className="stepper"><div className="step active"><span>01</span><b>Configurar</b></div><div className="step-line" /><div className="step"><span>02</span><b>Revisar catálogo</b></div><div className="step-line" /><div className="step"><span>03</span><b>Clasificar y editar</b></div></div>
    <div className="form-layout">
      <section className="card form-card">
        <div className="card-heading"><div><div className="card-label">01 · PREGUNTA</div><h3>¿Qué quieres analizar?</h3></div><span className="soft-badge">{study.row_count.toLocaleString()} respuestas</span></div>
        <label>Pregunta abierta<select value={question} onChange={(e) => setQuestion(e.target.value)}>{(study.columns || []).map((c: string) => <option key={c} value={c}>{c}</option>)}</select></label>
        <div className="field-label">Tipo de análisis</div>
        <div className="segmented"><button className={kind === 'themes' ? 'selected' : ''} onClick={() => setKind('themes')}><MessageSquareText size={16} /> Temas / motivos</button><button className={kind === 'brands' ? 'selected' : ''} onClick={() => setKind('brands')}><Tags size={16} /> Marcas</button></div>
        {kind === 'themes' ? <>
          <label>Contexto del estudio <span className="optional">OPCIONAL</span><textarea rows={3} value={context} onChange={(e) => setContext(e.target.value)} placeholder="Producto, categoría, mercado o instrucciones para el análisis…" /></label>
          <div className="inline-actions"><button className="button-secondary" onClick={propose} disabled={busy}><WandSparkles size={16} /> Proponer categorías con IA</button><span className="muted">Puedes editarlas antes de clasificar.</span></div>
          <div className="codeframe-editor">
            <div className="editor-heading"><div><b>Catálogo de categorías</b><small>{frame.length} categorías</small></div><button className="icon-button" title="Agregar categoría" onClick={() => setFrame([...frame, { nombre: '', descripcion: '' }])}><Plus size={17} /></button></div>
            {frame.length === 0 ? <div className="empty-frame"><Sparkles size={18} /><span>Propón categorías con IA o crea el catálogo manualmente.</span></div> : frame.map((item, index) => <div className="category-edit-row" key={index}><span className="category-num">{String(index + 1).padStart(2, '0')}</span><input value={item.nombre} placeholder="Nombre" onChange={(e) => setFrame(frame.map((v, i) => i === index ? { ...v, nombre: e.target.value } : v))} /><input value={item.descripcion} placeholder="Qué incluye (opcional)" onChange={(e) => setFrame(frame.map((v, i) => i === index ? { ...v, descripcion: e.target.value } : v))} /><button className="tiny-icon" onClick={() => setFrame(frame.filter((_, i) => i !== index))} title="Eliminar"><X size={15} /></button></div>)}
          </div>
          <label className="check-row"><input type="checkbox" checked={multi} onChange={(e) => setMulti(e.target.checked)} /><span>Permitir varias categorías por respuesta</span></label>
        </> : <>
          <label>Marcas permitidas <span className="optional">UNA POR LÍNEA</span><textarea rows={6} value={knownText} onChange={(e) => setKnownText(e.target.value)} placeholder={'Marca A\nMarca B\nMarca C'} /><small className="field-help">Catálogo cerrado: la IA asigna únicamente estas marcas. Una marca fuera del catálogo se clasifica como “Otra”; “Ninguna” requiere una respuesta explícita sin marca y una respuesta sin información será NS/NR.</small></label>
          <div className="info-callout"><Check size={16} /><span>Las marcas detectadas se podrán normalizar y corregir antes de Awareness.</span></div>
        </>}
        <button className="button-primary full-width classify-button" onClick={classify} disabled={busy || !question || (kind === 'themes' && !frame.length)}>{busy ? <><LoaderCircle className="spin" size={16} /> Procesando respuestas...</> : <><Sparkles size={16} /> Clasificar {study.row_count.toLocaleString()} respuestas</>}</button>
        <div className="privacy-note"><Database size={14} /> La API key cifrada se guarda en tu cuenta y puedes cambiarla desde Ajustes.</div>
      </section>
      <aside className="card side-info-card"><div className="side-info-symbol"><Sparkles size={20} /></div><div className="card-label">ASISTENCIA INTELIGENTE</div><h3>IA con el catálogo bajo tu control</h3><p>Define el marco de categorías o la lista de marcas y revisa lo que la IA produce. Las etiquetas se pueden corregir fila por fila después de clasificar.</p><div className="info-separator" /><div className="info-item"><span>Proveedor</span><b>{PROVIDERS[provider]?.label || provider}</b></div><div className="info-item"><span>Modelo</span><b>{model || 'No configurado'}</b></div><button className="text-link" onClick={() => onNotice({ text: 'Edita proveedor, modelo y API key desde Ajustes en el menú izquierdo.' })}>Configurar proveedor <ArrowRight size={14} /></button></aside>
    </div>
  </>
}

function DashboardPage({ study, apiKey, provider, model, onNotice }: any) {
  const classes: Classification[] = study?.classifications || []
  const [selectedId, setSelectedId] = useState('')
  const [freq, setFreq] = useState<Frequency[]>([])
  const [base, setBase] = useState(0)
  const [segments, setSegments] = useState<any[]>([])
  const [segmentColumn, setSegmentColumn] = useState('')
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
  async function loadSegments() {
    if (!selected || !segmentColumn) return
    try { const result = await api<any>(`/api/classifications/${selected.id}/segments?column=${encodeURIComponent(segmentColumn)}`); setSegments(result.segments) }
    catch (err) { onNotice({ text: (err as Error).message, error: true }) }
  }
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
    <div className="dashboard-grid">
      <section className="card chart-card"><div className="card-heading"><div><div className="card-label">DISTRIBUCIÓN</div><h3>Frecuencia por categoría</h3></div><span className="soft-badge">{chartData.length} categorías</span></div>
        {chartData.length ? <div className="chart-wrap"><ResponsiveContainer width="100%" height={Math.max(300, chartData.length * 48)}><BarChart data={chartData} layout="vertical" margin={{ top: 8, right: 32, left: 16, bottom: 8 }}><CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e9edf3" /><XAxis type="number" tickFormatter={(v) => `${Math.round(v * 100)}%`} axisLine={false} tickLine={false} tick={{ fill: '#8b94a7', fontSize: 11 }} /><YAxis type="category" dataKey="name" width={140} axisLine={false} tickLine={false} tick={{ fill: '#4b566b', fontSize: 12 }} /><Tooltip formatter={(value: any, _name: any, props: any) => [`${(Number(value) * 100).toFixed(1)}% · ${props.payload.n} menciones`, 'Frecuencia']} contentStyle={{ border: '1px solid #e7eaf0', borderRadius: 10, fontSize: 12 }} /><Bar dataKey="pct" radius={[0, 5, 5, 0]} barSize={21}>{chartData.map((_item, index) => <Cell key={index} fill={COLORS[index % COLORS.length]} />)}<LabelList dataKey="pct" position="right" formatter={(v: any) => `${Math.round(Number(v) * 100)}%`} style={{ fill: '#647086', fontSize: 11 }} /></Bar></BarChart></ResponsiveContainer></div> : <div className="empty-inline">No hay respuestas válidas para graficar.</div>}
        <div className="frequency-table"><div className="table-scroll"><table><thead><tr><th>Categoría</th><th>Personas</th><th>Porcentaje</th></tr></thead><tbody>{freq.map((row) => <tr key={row.Categoría}><td><span className="color-dot" style={{ background: COLORS[freq.indexOf(row) % COLORS.length] }} />{row.Categoría}</td><td>{row.Menciones.toLocaleString()}</td><td>{(row['%'] * 100).toFixed(1)}%</td></tr>)}</tbody></table></div></div>
      </section>
      <section className="card segment-card"><div className="card-label">COMPARACIÓN</div><h3>Explorar segmentos</h3><p>Compara la proporción de cada categoría entre grupos del estudio.</p><label>Segmentar por<select value={segmentColumn} onChange={(e) => { setSegmentColumn(e.target.value); setSegments([]) }}><option value="">Selecciona un campo</option>{(study.columns || []).filter((c: string) => c !== selected?.question).map((c: string) => <option key={c}>{c}</option>)}</select></label><button className="button-primary full-width" disabled={!segmentColumn} onClick={loadSegments}>Calcular cruce <ArrowRight size={15} /></button>
        {segments.length > 0 && <div className="segment-results"><div className="table-scroll"><table><thead><tr><th>Segmento (base)</th>{selected?.categories.slice(0, 3).map((c: string) => <th key={c}>{c}</th>)}</tr></thead><tbody>{segments.map((row) => <tr key={row.segment}><td>{row.segment} <small>n={row.base}</small></td>{selected?.categories.slice(0, 3).map((c: string) => <td key={c}>{(Number(row[c] || 0) * 100).toFixed(0)}%</td>)}</tr>)}</tbody></table></div></div>}
        <div className="small-note">Los segmentos con bases pequeñas deben interpretarse con cautela.</div>
      </section>
    </div>
    <div className="section-title-row mt-28"><div><h2>Insights cualitativos</h2><p>La IA redacta a partir de respuestas reales; cifras y citas se controlan desde el código.</p></div><button className="button-secondary" disabled={subBusy} onClick={generate}><Sparkles size={16} /> {subBusy ? 'Generando…' : 'Generar insights'}</button></div>
    {insight?.categorias?.length ? <div className="insight-grid">{insight.resumen && <div className="summary-insight"><div className="insight-kicker"><Sparkles size={15} /> LECTURA GENERAL</div><p>{insight.resumen}</p></div>}{insight.categorias.map((item: any) => <article className="card insight-card" key={item.categoria}><div className="insight-top"><span className="insight-dot" /> <b>{item.categoria}</b><span>{item.n} respuestas · {(item.pct * 100).toFixed(0)}%</span></div><p>{item.explicacion}</p>{item.citas?.map((quote: string, i: number) => <blockquote key={i}>“{quote}”</blockquote>)}</article>)}</div> : <div className="empty-panel"><div className="empty-icon"><Sparkles size={19} /></div><b>¿Qué está diciendo tu audiencia?</b><span>Genera una síntesis temática con citas verificables de las respuestas.</span></div>}
    <div className="section-title-row mt-32"><div><h2>Revisión y edición manual</h2><p>Corrige una etiqueta por fila; el cambio se guarda directamente en PostgreSQL.</p></div><button className="button-primary" onClick={saveEdits} disabled={subBusy || !Object.keys(edits).length}><Check size={15} /> Guardar {Object.keys(edits).length ? `(${Object.keys(edits).length})` : 'cambios'}</button></div>
    <div className="card review-card"><div className="review-toolbar"><div className="card-label">RESPUESTAS · MUESTRA DE {reviewRows.length}</div><span className="muted">{study.row_count.toLocaleString()} filas · Ctrl/Cmd para elegir varias etiquetas</span></div><div className="table-scroll"><table><thead><tr><th>Fila</th><th>Respuesta</th><th>Etiqueta actual</th><th>Editar etiquetas</th></tr></thead><tbody>{reviewRows.map((row) => { const options = [...selected.categories, ...['Ninguna', 'NS/NR'].filter((value) => (value !== 'Ninguna' || selected.kind === 'brands') && !selected.categories.includes(value))]; return <tr key={row.row_index}><td className="row-number">{row.row_index + 1}</td><td className="response-cell">{row.response || <span className="muted">(vacía)</span>}</td><td><span className="label-chip">{row.labels.join(' · ')}</span></td><td><select multiple disabled={!String(row.response ?? '').trim()} size={2} value={edits[row.row_index] ?? row.labels} onChange={(e) => { let values = Array.from(e.target.selectedOptions).map((option) => option.value); const exclusive = values.find((value) => value === 'Ninguna' || value === 'NS/NR'); if (exclusive) values = [exclusive]; setEdits({ ...edits, [row.row_index]: values }) }}>{options.map((c: string) => <option key={c} value={c}>{c}</option>)}</select></td></tr> })}</tbody></table></div>{reviewRows.length < study.row_count && <button className="button-secondary load-more" onClick={loadMore}>Cargar más respuestas</button>}</div>
  </>
}

function AwarenessHub({ study, onNotice }: any) {
  // Dos formas de usar Awareness, sin iframes ni servicios aparte:
  //  - Integrado: toma marcas y alias de las clasificaciones del estudio activo.
  //  - Independiente: carga un CSV/XLSX propio y genera el Excel de resultados.
  const [tab, setTab] = useState<'flow' | 'standalone'>(() => (sessionStorage.getItem('awareness-tab') as 'flow' | 'standalone') || 'flow')
  const choose = (next: 'flow' | 'standalone') => { setTab(next); sessionStorage.setItem('awareness-tab', next) }
  return <>
    <div className="segmented awa-tabs">
      <button className={tab === 'flow' ? 'selected' : ''} onClick={() => choose('flow')}>Integrado al flujo de categorización</button>
      <button className={tab === 'standalone' ? 'selected' : ''} onClick={() => choose('standalone')}>Independiente · CSV / Excel</button>
    </div>
    {tab === 'flow'
      ? <AwarenessPage study={study} onNotice={onNotice} />
      : <>
          <PageHeading eyebrow="RECORDACIÓN DE MARCA" title="Awareness independiente" text="Carga una base CSV o Excel, configura marcas y columnas, y descarga el reporte. No requiere crear un estudio ni ejecutar el flujo de categorización." />
          <AwarenessStandalone onNotice={onNotice} />
        </>}
  </>
}

function AwarenessPage({ study, onNotice }: any) {
  const brandClasses: Classification[] = (study?.classifications || []).filter((item: Classification) => item.kind === 'brands')
  const [classIds, setClassIds] = useState<string[]>([])
  const [analyses, setAnalyses] = useState<AwarenessProfile[]>([
    { name: 'AWA Marca', tom_column: '', spontaneous_columns: [], aided_columns: [] },
    { name: 'AWA Publicitario', tom_column: '', spontaneous_columns: [], aided_columns: [] },
  ])
  const [demographics, setDemographics] = useState<Record<string, string>>({ sexo: '', edad: '', departamento: '', estrato: '', ingreso: '' })
  const [segment, setSegment] = useState('')
  const [segmentValue, setSegmentValue] = useState('')
  const [segmentValues, setSegmentValues] = useState<string[]>([])
  const [result, setResult] = useState<any>(null)
  const [busy, setBusy] = useState(false)
  const [authChecked, setAuthChecked] = useState(false)
  const [userEmail, setUserEmail] = useState('')
  const brandClass = brandClasses.find((item) => item.id === classIds[0]) || brandClasses[0]
  const analysesReady = analyses.every((item) => [item.tom_column, ...item.spontaneous_columns, ...item.aided_columns].some(Boolean))
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
  async function calculate() {
    if (!study || !brandClass || !classIds.length || !analysesReady) return
    setBusy(true)
    try {
      setResult(await api<any>(`/api/studies/${study.id}/awareness`, {
        method: 'POST', body: JSON.stringify({
          classification_id: classIds[0], classification_ids: classIds, analyses,
          demographics, segment_column: segment, segment_value: segmentValue,
        }),
      }))
    } catch (err) { onNotice({ text: (err as Error).message, error: true }) }
    finally { setBusy(false) }
  }
  if (!study) return <EmptyState title="Carga o selecciona un estudio" text="Awareness utiliza las columnas de una encuesta y una lista de marcas." action="Ir a Inicio" />
  if (!brandClasses.length) return <EmptyState title="Primero detecta marcas" text="Clasifica una pregunta de tipo Marcas para reutilizar sus marcas y alias en Awareness." action="Ir a Categorización" />
  const multiSelect = (index: number, label: string, key: 'spontaneous_columns' | 'aided_columns') => <label>{label}<select multiple value={analyses[index][key]} onChange={(e) => updateAnalysis(index, { [key]: Array.from(e.target.selectedOptions).map((o) => o.value) })}>{(study.columns || []).map((c: string) => <option key={c}>{c}</option>)}</select><small className="field-help">Puedes seleccionar una pregunta base; sus columnas con sufijo como _1 y _2 se agrupan automáticamente. Mantén Ctrl/Cmd para elegir varias preguntas.</small></label>
  const resultAnalyses = result?.analyses || (result ? [{ name: 'Awareness', rows: result.rows || [] }] : [])
  return <>
    <PageHeading eyebrow="RECORDACIÓN DE MARCA" title="Awareness" text="Configura Top of Mind, recordación espontánea y ayudada a partir de las marcas detectadas." />
    <div className="awareness-layout">
      <section className="card form-card">
        <div className="card-label">CONFIGURACIÓN</div><h3>Diseña los dos análisis</h3>
        <div className="awareness-source-picker"><div className="awareness-source-heading"><b>Preguntas categorizadas para consolidar las marcas</b><button className="button-text" onClick={() => setClassIds(classIds.length === brandClasses.length ? [] : brandClasses.map((item) => item.id))}>{classIds.length === brandClasses.length ? 'Desmarcar todas' : 'Seleccionar todas'}</button></div><div className="awareness-source-list">{brandClasses.map((item) => <label key={item.id}><input type="checkbox" checked={classIds.includes(item.id)} onChange={(event) => setClassIds((current) => event.target.checked ? [...current, item.id] : current.filter((id) => id !== item.id))} /><span>{item.question}</span></label>)}</div><small className="field-help">El catálogo de marcas se consolida con las preguntas seleccionadas; cuando una pregunta ya está categorizada, se usan sus etiquetas guardadas y corregidas.</small></div>
        {analyses.map((analysis, index) => <div className="awareness-profile" key={analysis.name}>
          <div className="card-label mt-12">{analysis.name.toUpperCase()}</div>
          <div className="form-grid-two"><label>TOM · pregunta base<select value={analysis.tom_column} onChange={(e) => updateAnalysis(index, { tom_column: e.target.value })}><option value="">Sin TOM</option>{study.columns.map((c: string) => <option key={c}>{c}</option>)}</select><small className="field-help">Agrupa automáticamente las columnas hermanas del mismo código.</small></label>{multiSelect(index, 'Espontáneo · preguntas', 'spontaneous_columns')}</div>
          {multiSelect(index, 'Ayudado · preguntas', 'aided_columns')}
        </div>)}
        {!analysesReady && <small className="field-help">Configura al menos una pregunta en cada análisis para obtener AWA Marca y AWA Publicitario.</small>}
        <div className="form-grid-two mt-12"><label>Segmento opcional<select value={segment} onChange={(e) => { setSegment(e.target.value); setSegmentValue('') }}><option value="">Total</option>{study.columns.map((c: string) => <option key={c}>{c}</option>)}</select></label>{segment && <label>Valor del segmento<select value={segmentValue} onChange={(e) => setSegmentValue(e.target.value)}>{segmentValues.map((v) => <option key={v} value={v}>{v}</option>)}</select></label>}</div>
        <div className="card-label mt-12">VARIABLES DEMOGRÁFICAS</div><div className="form-grid-two">{Object.entries(demographics).map(([key, value]) => <label key={key}>{key[0].toUpperCase() + key.slice(1)}<select value={value} onChange={(e) => setDemographics({ ...demographics, [key]: e.target.value })}><option value="">No usar</option>{study.columns.map((c: string) => <option key={c}>{c}</option>)}</select></label>)}</div>
        <button className="button-primary full-width" onClick={calculate} disabled={busy || !classIds.length || !analysesReady}>{busy ? <><LoaderCircle className="spin" size={16} /> Calculando…</> : <><BarChart3 size={16} /> Calcular ambos análisis</>}</button>
      </section>
      <section className="card awareness-result">
        <div className="card-heading"><div><div className="card-label">RESULTADOS</div><h3>Awareness por tipo</h3></div>{result && <span className="base-chip">Base: <b>{result.base}</b></span>}</div>
        {resultAnalyses.length ? resultAnalyses.map((analysis: any) => {
          const chartRows = analysis.rows.map((r: any) => ({ name: r.Entidad, tom: r['TOM %'], espontaneo: r['Espontaneo %'], ayudado: r['Ayudado %'] }))
          return <div className="awareness-analysis-result" key={analysis.name}>
            <h4>{analysis.name}</h4>
            <div className="chart-wrap"><ResponsiveContainer width="100%" height={Math.max(260, chartRows.length * 40)}><BarChart data={chartRows} layout="vertical" margin={{ left: 18, right: 26 }}><CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e9edf3" /><XAxis type="number" tickFormatter={(v) => `${Math.round(v * 100)}%`} axisLine={false} tickLine={false} /><YAxis type="category" dataKey="name" width={130} axisLine={false} tickLine={false} /><Tooltip formatter={(v: any) => `${(Number(v) * 100).toFixed(1)}%`} /><Bar dataKey="tom" name="TOM" stackId="a" fill="#315bdb" /><Bar dataKey="espontaneo" name="Espontáneo" stackId="a" fill="#18a994" /><Bar dataKey="ayudado" name="Ayudado" stackId="a" fill="#ef9b46" /></BarChart></ResponsiveContainer></div>
            <div className="table-scroll"><table><thead><tr><th>Marca</th><th>TOM</th><th>Espontáneo</th><th>Ayudado</th><th>AWA</th></tr></thead><tbody>{analysis.rows.map((r: any) => <tr key={r.Entidad}><td>{r.Entidad}</td><td>{(r['TOM %'] * 100).toFixed(1)}%</td><td>{(r['Espontaneo %'] * 100).toFixed(1)}%</td><td>{(r['Ayudado %'] * 100).toFixed(1)}%</td><td><b>{(r['AWA %'] * 100).toFixed(1)}%</b></td></tr>)}</tbody></table></div>
          </div>
        }) : <div className="empty-panel large-empty"><div className="empty-icon"><UsersRound size={20} /></div><b>Configura ambos análisis</b><span>El flujo usará las respuestas categorizadas y calculará TOM, espontáneo y ayudado por separado para cada perfil.</span></div>}
      </section>
    </div>
  </>
}

function SettingsPage({ provider, model, apiKey, setApiKey, onProvider, setModel }: any) {
  const [configured, setConfigured] = useState(false)
  const [keyInput, setKeyInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  useEffect(() => {
    setKeyInput(''); setMessage('')
    api<{providers: string[]}>('/api/me/api-keys').then((result) => setConfigured(result.providers.includes(provider))).catch((err) => setMessage((err as Error).message))
  }, [provider])
  async function saveKey() {
    if (!keyInput.trim()) { setMessage('Pega la API key para guardarla.'); return }
    setBusy(true); setMessage('')
    try {
      await api(`/api/me/api-keys/${encodeURIComponent(provider)}`, { method: 'PUT', body: JSON.stringify({ api_key: keyInput.trim() }) })
      setConfigured(true); setKeyInput(''); setApiKey('')
      setMessage('Clave guardada cifrada para tu usuario. Se utilizará automáticamente con este proveedor.')
    } catch (err) { setMessage((err as Error).message) } finally { setBusy(false) }
  }
  async function deleteKey() {
    setBusy(true); setMessage('')
    try {
      await api(`/api/me/api-keys/${encodeURIComponent(provider)}`, { method: 'DELETE' })
      setConfigured(false); setMessage('Clave guardada eliminada.')
    } catch (err) { setMessage((err as Error).message) } finally { setBusy(false) }
  }
  return <>
    <PageHeading eyebrow="PREFERENCIAS DE TU CUENTA" title="Ajustes" text="Guarda una API key por proveedor para que tus análisis la usen automáticamente. Puedes reemplazarla o eliminarla cuando quieras." />
    <div className="settings-layout"><section className="card form-card settings-card"><div className="card-label">PROVEEDOR DE IA</div><h3>Conexión del modelo</h3><label>Proveedor<select value={provider} onChange={(e) => onProvider(e.target.value)}>{Object.entries(PROVIDERS).map(([id, item]) => <option key={id} value={id}>{item.label}</option>)}</select></label><label>Modelo<input value={model} onChange={(e) => setModel(e.target.value)} placeholder={PROVIDERS[provider]?.model} /></label>
      <div className="setting-key-status">{configured ? <><span className="online-dot" /> Ya guardaste una clave para {PROVIDERS[provider]?.label || provider}. No se vuelve a mostrar.</> : <>No hay una clave guardada para este proveedor.</>}</div>
      <label>{configured ? 'Reemplazar API key' : 'API key'}<input type="password" value={keyInput} onChange={(e) => setKeyInput(e.target.value)} placeholder={configured ? 'Pega una clave nueva para reemplazarla' : 'Pega tu clave de API'} autoComplete="new-password" /></label>
      <div className="inline-actions"><button className="button-primary" onClick={saveKey} disabled={busy || !keyInput.trim()}>{busy ? 'Guardando…' : configured ? 'Guardar nueva clave' : 'Guardar clave'}</button>{configured && <button className="button-secondary" onClick={deleteKey} disabled={busy}>Eliminar clave</button>}</div>
      {message && <div className="auth-error" role="status">{message}</div>}
      <div className="info-callout"><Database size={16} /><span>La clave se cifra en el backend y solo se devuelve al proveedor al ejecutar una tarea. Nunca se muestra de nuevo en la interfaz.</span></div><div className="provider-note"><b>Nota de privacidad</b><p>Al clasificar o generar insights, las respuestas seleccionadas y tu clave se usan para llamar al proveedor elegido. La clave cifrada se guarda vinculada a tu usuario.</p></div></section><aside className="card side-info-card"><div className="card-label">ESTADO LOCAL</div><h3>Tu entorno de desarrollo</h3><div className="setting-status"><span className="online-dot" /> <div><b>PostgreSQL</b><small>Claves cifradas guardadas por usuario y proveedor</small></div></div><div className="setting-status"><span className="online-dot" /> <div><b>FastAPI</b><small>Documentación interactiva en /docs</small></div></div><div className="setting-status"><span className="online-dot" /> <div><b>React + Vite</b><small>Desarrollo local con recarga</small></div></div></aside></div>
  </>
}

function EmptyState({ title, text, action }: { title: string; text: string; action: string }) {
  return <div className="empty-state"><div className="empty-state-mark"><FolderOpen size={25} /></div><h2>{title}</h2><p>{text}</p><a href="/" className="button-secondary">{action} <ArrowRight size={15} /></a></div>
}

export default App
