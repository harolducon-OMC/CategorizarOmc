import { FormEvent, useState } from 'react'
import { KeyRound } from 'lucide-react'
import { api } from '../api'

/** Cambio de contraseña voluntario (en Ajustes). Cierra las demás sesiones y conserva esta con un token nuevo. */
export function ChangeMyPassword() {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [message, setMessage] = useState<{ text: string; error?: boolean } | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setMessage(null)
    if (next !== confirm) { setMessage({ text: 'La confirmación no coincide con la nueva contraseña.', error: true }); return }
    setBusy(true)
    try {
      const data = await api<{ access_token: string }>('/api/auth/change-password', {
        method: 'POST', body: JSON.stringify({ current_password: current, new_password: next }),
      })
      sessionStorage.setItem('insights-token', data.access_token)
      setCurrent(''); setNext(''); setConfirm('')
      setMessage({ text: 'Contraseña actualizada. Las demás sesiones abiertas se cerraron.' })
    } catch (error) {
      setMessage({ text: (error as Error).message, error: true })
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="card change-my-password" onSubmit={submit}>
      <div className="card-label"><KeyRound size={13} /> CAMBIAR MI CONTRASEÑA</div>
      <p className="admin-help">Si olvidaste tu contraseña, un administrador puede restablecerla desde su panel.</p>
      <div className="policy-grid">
        <label className="policy-field">Contraseña actual<input type="password" autoComplete="current-password" value={current} onChange={(event) => setCurrent(event.target.value)} required /></label>
        <label className="policy-field">Nueva contraseña<input type="password" autoComplete="new-password" minLength={12} value={next} onChange={(event) => setNext(event.target.value)} required /></label>
        <label className="policy-field">Confirmar nueva contraseña<input type="password" autoComplete="new-password" minLength={12} value={confirm} onChange={(event) => setConfirm(event.target.value)} required /></label>
      </div>
      {message && <div className={message.error ? 'auth-error' : 'awa-base-warning'} role="status">{message.text}</div>}
      <button className="button-primary" type="submit" disabled={busy}>{busy ? 'Guardando…' : 'Cambiar contraseña'}</button>
    </form>
  )
}
