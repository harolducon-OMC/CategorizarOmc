import { useEffect, useState } from 'react'
import { Database } from 'lucide-react'
import { api } from '../api'
import { PageHeading } from '../components/common'
import { PROVIDERS } from '../constants'

export function SettingsPage({ provider, model, apiKey, setApiKey, onProvider, setModel, onKeysChanged }: any) {
  const [configured, setConfigured] = useState(false)
  const [unreadable, setUnreadable] = useState(false)
  const [keyInput, setKeyInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  useEffect(() => {
    setKeyInput(''); setMessage('')
    api<{providers: string[]; unreadable?: string[]}>('/api/me/api-keys').then((result) => { setConfigured(result.providers.includes(provider)); setUnreadable((result.unreadable || []).includes(provider)) }).catch((err) => setMessage((err as Error).message))
  }, [provider])
  async function saveKey() {
    if (!keyInput.trim()) { setMessage('Pega la API key para guardarla.'); return }
    setBusy(true); setMessage('')
    try {
      await api(`/api/me/api-keys/${encodeURIComponent(provider)}`, { method: 'PUT', body: JSON.stringify({ api_key: keyInput.trim() }) })
      setConfigured(true); setUnreadable(false); setKeyInput(''); setApiKey(''); onKeysChanged?.()
      setMessage('Clave guardada cifrada para tu usuario. Se utilizará automáticamente con este proveedor.')
    } catch (err) { setMessage((err as Error).message) } finally { setBusy(false) }
  }
  async function deleteKey() {
    setBusy(true); setMessage('')
    try {
      await api(`/api/me/api-keys/${encodeURIComponent(provider)}`, { method: 'DELETE' })
      setConfigured(false); setUnreadable(false); setMessage('Clave guardada eliminada.'); onKeysChanged?.()
    } catch (err) { setMessage((err as Error).message) } finally { setBusy(false) }
  }
  return <>
    <PageHeading eyebrow="PREFERENCIAS DE TU CUENTA" title="Ajustes" text="Guarda una API key por proveedor para que tus análisis la usen automáticamente. Puedes reemplazarla o eliminarla cuando quieras." />
    <div className="settings-layout"><section className="card form-card settings-card"><div className="card-label">PROVEEDOR DE IA</div><h3>Conexión del modelo</h3><label>Proveedor<select value={provider} onChange={(e) => onProvider(e.target.value)}>{Object.entries(PROVIDERS).map(([id, item]) => <option key={id} value={id}>{item.label}</option>)}</select></label><label>Modelo<input value={model} onChange={(e) => setModel(e.target.value)} placeholder={PROVIDERS[provider]?.model} /></label>
      <div className="setting-key-status">{unreadable ? <>⚠ Hay una clave guardada para {PROVIDERS[provider]?.label || provider}, pero no se puede leer (el servidor cambió su JWT_SECRET). Pega la clave de nuevo y guárdala.</> : configured ? <><span className="online-dot" /> Ya guardaste una clave para {PROVIDERS[provider]?.label || provider}. No se vuelve a mostrar.</> : <>No hay una clave guardada para este proveedor.</>}</div>
      <label>{configured ? 'Reemplazar API key' : 'API key'}<input type="password" value={keyInput} onChange={(e) => setKeyInput(e.target.value)} placeholder={configured ? 'Pega una clave nueva para reemplazarla' : 'Pega tu clave de API'} autoComplete="new-password" /></label>
      <div className="inline-actions"><button className="button-primary" onClick={saveKey} disabled={busy || !keyInput.trim()}>{busy ? 'Guardando…' : configured ? 'Guardar nueva clave' : 'Guardar clave'}</button>{configured && <button className="button-secondary" onClick={deleteKey} disabled={busy}>Eliminar clave</button>}</div>
      {message && <div className="auth-error" role="status">{message}</div>}
      <div className="info-callout"><Database size={16} /><span>La clave se cifra en el backend y solo se devuelve al proveedor al ejecutar una tarea. Nunca se muestra de nuevo en la interfaz.</span></div><div className="provider-note"><b>Nota de privacidad</b><p>Al clasificar o generar insights, las respuestas seleccionadas y tu clave se usan para llamar al proveedor elegido. La clave cifrada se guarda vinculada a tu usuario.</p></div></section><aside className="card side-info-card"><div className="card-label">ESTADO LOCAL</div><h3>Tu entorno de desarrollo</h3><div className="setting-status"><span className="online-dot" /> <div><b>PostgreSQL</b><small>Claves cifradas guardadas por usuario y proveedor</small></div></div><div className="setting-status"><span className="online-dot" /> <div><b>FastAPI</b><small>Documentación interactiva en /docs</small></div></div><div className="setting-status"><span className="online-dot" /> <div><b>React + Vite</b><small>Desarrollo local con recarga</small></div></div></aside></div>
  </>
}
