import { useEffect, useState } from 'react'
import { Database, KeyRound, ShieldCheck } from 'lucide-react'
import { api } from '../api'

type KeyName = 'xpoz' | 'gemini' | 'groq'
const FIELDS: { id: KeyName; label: string; detail: string }[] = [
  { id: 'xpoz', label: 'Xpoz', detail: 'Necesaria para buscar menciones en redes.' },
  { id: 'gemini', label: 'Google Gemini', detail: 'Clave exclusiva para analizar sentimiento en Escucha social.' },
  { id: 'groq', label: 'Groq', detail: 'Clave exclusiva para analizar sentimiento en Escucha social.' },
]

export function SocialListeningKeys() {
  const [configured, setConfigured] = useState<KeyName[]>([])
  const [unreadable, setUnreadable] = useState<KeyName[]>([])
  const [values, setValues] = useState<Record<KeyName, string>>({ xpoz: '', gemini: '', groq: '' })
  const [busy, setBusy] = useState<KeyName | ''>('')
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState('')
  const [isError, setIsError] = useState(false)

  async function refresh() {
    setLoading(true)
    try {
      const result = await api<{ configured: KeyName[]; unreadable: KeyName[] }>('/api/me/social-listening/keys')
      setConfigured(result.configured || [])
      setUnreadable(result.unreadable || [])
    } catch (error) {
      setMessage((error as Error).message); setIsError(true)
    } finally { setLoading(false) }
  }
  useEffect(() => { void refresh() }, [])

  async function save(id: KeyName) {
    const key = values[id].trim()
    if (!key) { setMessage(`Pega primero la clave de ${FIELDS.find((field) => field.id === id)?.label}.`); setIsError(true); return }
    setBusy(id); setMessage(''); setIsError(false)
    try {
      await api(`/api/me/social-listening/keys/${id}`, { method: 'PUT', body: JSON.stringify({ api_key: key }) })
      setValues((current) => ({ ...current, [id]: '' }))
      await refresh()
      setMessage('Clave guardada cifrada para Escucha social. No se comparte con el categorizador.')
    } catch (error) { setMessage((error as Error).message); setIsError(true) }
    finally { setBusy('') }
  }
  async function remove(id: KeyName) {
    setBusy(id); setMessage(''); setIsError(false)
    try {
      await api(`/api/me/social-listening/keys/${id}`, { method: 'DELETE' })
      await refresh()
      setMessage('Clave eliminada de Escucha social.')
    } catch (error) { setMessage((error as Error).message); setIsError(true) }
    finally { setBusy('') }
  }

  return <section className="card form-card social-key-card">
    <div className="card-label">CREDENCIALES INDEPENDIENTES</div>
    <h3><KeyRound size={16} /> Escucha social</h3>
    <p className="social-key-intro">Estas credenciales están separadas de las claves de IA del categorizador. Cada una se cifra y queda vinculada a tu usuario; nunca se vuelve a mostrar.</p>
    <div className="social-key-list">{FIELDS.map((field) => {
      const saved = configured.includes(field.id)
      const unread = unreadable.includes(field.id)
      return <div className="social-key-row" key={field.id}>
        <div className="social-key-row-heading"><label htmlFor={`social-key-${field.id}`}>{field.label}</label><span className={unread ? 'social-key-state warn' : saved ? 'social-key-state saved' : 'social-key-state'}>{unread ? 'Necesita actualizarse' : saved ? 'Configurada' : 'Sin configurar'}</span></div>
        <p>{field.detail}{unread && ' La clave no se puede descifrar con la configuración de cifrado actual; reemplázala.'}</p>
        <div className="social-key-input-row"><input id={`social-key-${field.id}`} type="password" autoComplete="new-password" value={values[field.id]} onChange={(event) => setValues((current) => ({ ...current, [field.id]: event.target.value }))} placeholder={saved ? 'Pega una nueva clave para reemplazarla' : 'Pega la clave API'} /><button className="button-primary" onClick={() => void save(field.id)} disabled={loading || busy !== '' || !values[field.id].trim()}>{busy === field.id ? 'Guardando…' : saved ? 'Reemplazar' : 'Guardar'}</button>{saved && <button className="button-secondary" onClick={() => void remove(field.id)} disabled={busy !== ''}>Eliminar</button>}</div>
      </div>
    })}</div>
    {message && <div className={isError ? 'auth-error' : 'social-key-success'} role="status">{message}</div>}
    <div className="info-callout"><ShieldCheck size={16} /><span>Se almacenan bajo identificadores distintos y solo el módulo de Escucha social puede solicitarlas. Gemini/Groq aquí no heredan ni leen la clave guardada para categorizar.</span></div>
    <div className="social-key-footnote"><Database size={14} /> {loading ? 'Consultando estado de claves…' : 'Cifrado del servidor · almacenamiento por usuario · sin exposición en el navegador'}</div>
  </section>
}
