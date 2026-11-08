import { FormEvent, useState } from 'react'
import { api } from '../api'
import './admin.css'

/** Pantalla obligatoria tras un restablecimiento: la contraseña temporal solo sirve para entrar y cambiarla. */
export function ChangePasswordScreen({ email, onDone, onLogout }: {
  email: string
  onDone: (token: string) => void
  onLogout: () => void
}) {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
    if (next !== confirm) { setError('La confirmación no coincide con la nueva contraseña.'); return }
    setBusy(true)
    try {
      const data = await api<{ access_token: string }>('/api/auth/change-password', {
        method: 'POST', body: JSON.stringify({ current_password: current, new_password: next }),
      })
      onDone(data.access_token)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-shell">
      <form className="auth-card change-password-card" onSubmit={submit}>
        <h2>Crea tu nueva contraseña</h2>
        <p className="change-password-note">
          El administrador restableció el acceso de <b>{email}</b>. Escribe la contraseña temporal que recibiste y elige una nueva que solo tú conozcas.
        </p>
        <label>Contraseña temporal<input type="password" autoComplete="current-password" value={current} onChange={(event) => setCurrent(event.target.value)} required /></label>
        <label>Nueva contraseña<input type="password" autoComplete="new-password" minLength={12} value={next} onChange={(event) => setNext(event.target.value)} required /></label>
        <label>Confirma la nueva contraseña<input type="password" autoComplete="new-password" minLength={12} value={confirm} onChange={(event) => setConfirm(event.target.value)} required /></label>
        {error && <div className="auth-error" role="alert">{error}</div>}
        <button className="button-primary" type="submit" disabled={busy}>{busy ? 'Guardando…' : 'Guardar y continuar'}</button>
        <button className="button-secondary" type="button" onClick={onLogout}>Cerrar sesión</button>
      </form>
    </div>
  )
}
