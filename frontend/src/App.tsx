import { lazy, Suspense, useCallback, useEffect, useState } from 'react'
import { Activity, BarChart3, ChevronDown, CircleHelp, Database, LayoutDashboard, KeyRound, Settings2, ShieldCheck, Tags, UsersRound, X } from 'lucide-react'
import { api } from './api'
import { NavButton } from './components/common'
import { PROVIDERS } from './constants'
import { AuthPage } from './pages/AuthPage'
import { HomePage } from './pages/HomePage'
import type { Page, Study, Classification, Role } from './types'
import HelpAssistant from './HelpAssistant'
import { PageSkeleton } from './components/Skeleton'
import { setVitalsPage } from './vitals'
import { PASSWORD_CHANGE_REQUIRED, SESSION_ENDED } from './authEvents'
import { ChangePasswordScreen } from './pages/ChangePasswordScreen'
import './AwarenessExtras.css'

// Cada pantalla pesada se descarga solo cuando se abre (el JS inicial es mucho más pequeño)
const AwarenessHub = lazy(() => import('./pages/AwarenessHub').then((m) => ({ default: m.AwarenessHub })))
const DashboardPage = lazy(() => import('./pages/DashboardPage').then((m) => ({ default: m.DashboardPage })))
const SettingsPage = lazy(() => import('./pages/SettingsPage').then((m) => ({ default: m.SettingsPage })))
const AdminPage = lazy(() => import('./pages/AdminPage').then((m) => ({ default: m.AdminPage })))
const CategorizeWorkflow = lazy(() => import('./CategorizeWorkflow'))

function App() {
  const [page, setPage] = useState<Page>('home')
  const [studies, setStudies] = useState<Study[]>([])
  const [studyId, setStudyId] = useState(localStorage.getItem('insights-study') || '')
  const [study, setStudy] = useState<any>(null)
  const [studiesLoaded, setStudiesLoaded] = useState(false)
  const [provider, setProvider] = useState(() => {
    const saved = localStorage.getItem('insights-provider') || ''
    return PROVIDERS[saved] ? saved : 'gemini'
  })
  const [model, setModel] = useState(() => {
    const saved = localStorage.getItem('insights-provider') || ''
    return localStorage.getItem('insights-model') || PROVIDERS[saved]?.model || PROVIDERS.gemini.model
  })
  const [savedKeys, setSavedKeys] = useState<{ providers: string[]; unreadable: string[] }>({ providers: [], unreadable: [] })
  const [apiKey, setApiKey] = useState('')
  const [aiMenuOpen, setAiMenuOpen] = useState(false)
  const [notice, setNotice] = useState<{ text: string; error?: boolean } | null>(null)
  const [busy, setBusy] = useState(false)
  const [authChecked, setAuthChecked] = useState(false)
  const [userEmail, setUserEmail] = useState('')
  const [role, setRole] = useState<Role>('user')
  const [mustChange, setMustChange] = useState(false)
  const [sessionNotice, setSessionNotice] = useState('')

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
    api<{ email: string; role: Role; must_change_password: boolean }>('/api/auth/me')
      .then((user) => { setUserEmail(user.email); setRole(user.role); setMustChange(user.must_change_password); setAuthChecked(true) })
      .catch(() => { sessionStorage.removeItem('insights-token'); setAuthChecked(true) })
  }, [])

  // El servidor puede cortar la sesión (baneo, inactivación, restablecimiento) o exigir cambiar la contraseña
  useEffect(() => {
    const ended = (event: Event) => {
      sessionStorage.removeItem('insights-token')
      setUserEmail(''); setRole('user'); setMustChange(false); setStudies([]); setStudyId(''); setStudy(null)
      setSessionNotice((event as CustomEvent<string>).detail || '')
    }
    const passwordRequired = () => setMustChange(true)
    window.addEventListener(SESSION_ENDED, ended)
    window.addEventListener(PASSWORD_CHANGE_REQUIRED, passwordRequired)
    return () => {
      window.removeEventListener(SESSION_ENDED, ended)
      window.removeEventListener(PASSWORD_CHANGE_REQUIRED, passwordRequired)
    }
  }, [])

  useEffect(() => {
    if (!userEmail) return
    refreshStudies().catch((err) => setNotice({ text: `No se pudo conectar con la API: ${err.message}`, error: true })).finally(() => setStudiesLoaded(true))
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

  // Proveedor y modelo se recuerdan en este navegador (nunca la clave).
  useEffect(() => { localStorage.setItem('insights-provider', provider) }, [provider])
  useEffect(() => { localStorage.setItem('insights-model', model) }, [model])

  const refreshKeys = useCallback(() => {
    api<{ providers: string[]; unreadable?: string[] }>('/api/me/api-keys')
      .then((result) => setSavedKeys({ providers: result.providers, unreadable: result.unreadable || [] }))
      .catch(() => {})
  }, [])
  useEffect(() => { if (userEmail) refreshKeys() }, [userEmail, refreshKeys])

  async function deleteStudy(id: string) {
    if (!window.confirm('¿Eliminar este estudio y sus clasificaciones guardadas? Esta acción no se puede deshacer.')) return
    // Optimista: el estudio desaparece de inmediato y se restaura si el servidor falla
    const previousStudies = studies, previousId = studyId
    const remaining = studies.filter((item) => item.id !== id)
    setStudies(remaining)
    setStudyId(remaining[0]?.id || '')
    try {
      await api(`/api/studies/${id}`, { method: 'DELETE' })
      setNotice({ text: 'Estudio eliminado.' })
    } catch (err) {
      setStudies(previousStudies); setStudyId(previousId)
      setNotice({ text: (err as Error).message, error: true })
    }
  }

  useEffect(() => { setVitalsPage(page) }, [page])

  const activeClassifications: Classification[] = study?.classifications || []
  const activePageTitle: Record<Page, string> = {
    home: 'Inicio', categorize: 'Categorización', dashboard: 'Dashboard', awareness: 'Awareness', settings: 'Ajustes', admin: 'Administración',
  }

  if (!authChecked) return <div className="auth-shell"><div className="auth-card">Validando sesión…</div></div>
  function logout() {
    sessionStorage.removeItem('insights-token')
    setUserEmail(''); setRole('user'); setMustChange(false); setStudies([]); setStudyId(''); setStudy(null)
  }
  if (!userEmail) return <AuthPage notice={sessionNotice} onAuthenticated={(email, token, info) => {
    sessionStorage.setItem('insights-token', token)
    setSessionNotice(''); setRole((info?.role as Role) || 'user'); setMustChange(Boolean(info?.must_change_password)); setUserEmail(email)
  }} />
  if (mustChange) return <ChangePasswordScreen email={userEmail} onLogout={logout} onDone={(token) => { sessionStorage.setItem('insights-token', token); setMustChange(false) }} />

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
          {role !== 'user' && <NavButton active={page === 'admin'} onClick={() => setPage('admin')} icon={<ShieldCheck size={18} />} label="Administración" />}
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
        <div className="sidebar-tip"><div className="tip-icon"><CircleHelp size={17} /></div><div><b>¿Necesitas ayuda?</b><span>Pregunta desde el botón «Ayuda».</span></div></div>
        <button className={`nav-button settings-link ${page === 'settings' ? 'active' : ''}`} onClick={() => setPage('settings')}><Settings2 size={18} /><span>Ajustes</span></button>
        <div className="local-status"><span className="online-dot" /> © 2026 Propiedad OMC</div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumbs"><span>Insights Studio</span><span className="crumb-sep">/</span><b>{activePageTitle[page]}</b></div>
          <div className="topbar-right">
            <div className="ai-quick-wrap">
              <button className={`ai-quick-toggle ${aiMenuOpen ? 'open' : ''}`} onClick={() => setAiMenuOpen(!aiMenuOpen)} aria-expanded={aiMenuOpen}>
                <KeyRound size={14} /><span>IA · {PROVIDERS[provider]?.label || provider}</span><span className={`key-dot ${savedKeys.unreadable.includes(provider) ? 'bad' : savedKeys.providers.includes(provider) ? 'ok' : 'none'}`} title={savedKeys.providers.includes(provider) ? 'Clave guardada' : 'Sin clave guardada'} /><ChevronDown size={13} />
              </button>
              {aiMenuOpen && <div className="ai-quick-panel"><div className="ai-panel-heading"><div><b>Proveedor de IA</b><small>Configuración para esta sesión</small></div><button className="tiny-icon" onClick={() => setAiMenuOpen(false)} aria-label="Cerrar"><X size={15} /></button></div><label>Proveedor<select value={provider} onChange={(e) => changeProvider(e.target.value)}>{Object.entries(PROVIDERS).map(([id, item]) => <option key={id} value={id}>{item.label}</option>)}</select></label><label>Modelo<input value={model} onChange={(e) => setModel(e.target.value)} placeholder={PROVIDERS[provider]?.model} /></label><div className={`key-status ${savedKeys.unreadable.includes(provider) ? 'bad' : savedKeys.providers.includes(provider) ? 'ok' : 'none'}`}>{savedKeys.unreadable.includes(provider) ? <>La clave guardada de {PROVIDERS[provider]?.label} no se puede leer. <button className="button-text" onClick={() => { setPage('settings'); setAiMenuOpen(false) }}>Guárdala de nuevo en Ajustes</button></> : savedKeys.providers.includes(provider) ? <>✓ Usando tu clave guardada de {PROVIDERS[provider]?.label}.</> : <>No hay clave guardada para {PROVIDERS[provider]?.label}. <button className="button-text" onClick={() => { setPage('settings'); setAiMenuOpen(false) }}>Guardar en Ajustes</button></>}</div>{savedKeys.providers.length > 0 && <small className="ai-panel-note">Claves guardadas: {savedKeys.providers.map((id) => PROVIDERS[id]?.label || id).join(', ')}.</small>}<label>Clave solo para esta sesión <span className="optional">OPCIONAL</span><input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder={savedKeys.providers.includes(provider) ? 'Déjalo vacío para usar la guardada' : 'Pega tu API key'} autoComplete="off" /></label><small className="ai-panel-note">Si la escribes aquí, tiene prioridad y no se guarda en la base de datos.</small></div>}
            </div>
            {study && <span className="top-study"><Database size={14} /> {study.name}</span>}
            <span className="local-pill"><span className="online-dot" /> Local</span>
            <button className="avatar" title={`Cerrar sesión (${userEmail})`} onClick={logout}>{userEmail.slice(0,1).toUpperCase()}</button>
          </div>
        </header>
        {notice && <div className={`toast ${notice.error ? 'toast-error' : ''}`}><span>{notice.text}</span><button onClick={() => setNotice(null)}><X size={16} /></button></div>}
        <div className="page-content">
          {!studiesLoaded ? <PageSkeleton /> : <Suspense fallback={<PageSkeleton />}>
          {page === 'home' && <HomePage studies={studies} study={study} onUpload={async (file, name, sheet) => {
            const form = new FormData(); form.append('file', file); form.append('name', name); form.append('sheet', sheet)
            setBusy(true)
            try { const created = await api<Study>('/api/studies', { method: 'POST', body: form }); await refreshStudies(created.id); setNotice({ text: 'Encuesta importada y guardada en PostgreSQL.' }) }
            catch (err) { setNotice({ text: (err as Error).message, error: true }) }
            finally { setBusy(false) }
          }} busy={busy} onDelete={deleteStudy} onGo={setPage} />}
          {page === 'categorize' && <CategorizeWorkflow study={study} apiKey={apiKey} provider={provider} model={model} onRefresh={refreshStudy} onNotice={setNotice} busy={busy} setBusy={setBusy} />}
          {page === 'admin' && role !== 'user' && <AdminPage role={role} email={userEmail} onNotice={setNotice} />}
          {page === 'dashboard' && <DashboardPage study={study} apiKey={apiKey} provider={provider} model={model} onNotice={setNotice} />}
          {page === 'awareness' && <AwarenessHub study={study} onNotice={setNotice} />}
          {page === 'settings' && <SettingsPage provider={provider} model={model} apiKey={apiKey} setApiKey={setApiKey} onProvider={changeProvider} setModel={setModel} onKeysChanged={refreshKeys} />}
          </Suspense>}
        </div>
        <footer className="footer-note">Insights Studio · OMC <span>© 2026 Harold Ducon and Research.</span></footer>
      </main>
      <HelpAssistant
        provider={provider}
        model={model}
        apiKey={apiKey}
        page={page}
        study={study}
        onOpenSettings={() => setPage('settings')}
        onNavigate={setPage}
      />
    </div>
  )
}

export default App
