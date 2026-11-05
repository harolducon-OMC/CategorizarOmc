import { useState } from 'react'
import { Activity } from 'lucide-react'
import { api } from '../api'

export function AuthPage({ onAuthenticated }: { onAuthenticated: (email: string, token: string) => void }) {
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
