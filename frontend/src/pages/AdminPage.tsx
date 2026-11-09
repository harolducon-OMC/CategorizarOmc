import { useCallback, useEffect, useState } from 'react'
import { KeyRound, Search, ShieldCheck } from 'lucide-react'
import { api } from '../api'
import type { Role } from '../types'
import { TableSkeleton } from '../components/Skeleton'
import './admin.css'

type AdminUser = {
  id: string; email: string; role: Role; status: 'active' | 'inactive' | 'banned'; created_at: string | null
  last_login_at: string | null; ban_reason: string | null; banned_by: string | null; must_change_password: boolean
  study_count: number; locked: boolean
}
type PolicyInfo = {
  policy: Record<string, any>; defaults: Record<string, any>
  fields: Record<string, { type: string; min: number | null; max: number | null; label: string }>
  providers: { id: string; name: string }[]
}
type AuditEvent = { id: string; actor: string; action: string; target: string | null; details: Record<string, any>; created_at: string }
type Notice = { text: string; error?: boolean }

const ROLE_LABEL: Record<Role, string> = { user: 'Usuario', admin: 'Administrador', super_admin: 'Super administrador' }
const STATUS_LABEL = { active: 'Activa', inactive: 'Inactiva', banned: 'Baneada' }
const ACTION_LABEL: Record<string, string> = {
  deactivate: 'Inactivó la cuenta', reactivate: 'Reactivó la cuenta', ban: 'Baneó la cuenta', unban: 'Quitó el baneo',
  reset_password: 'Restableció la contraseña', delete: 'Eliminó la cuenta', set_role: 'Cambió el rol', update_policy: 'Actualizó políticas',
}
const FIELD_LABEL: Record<string, string> = {
  min_password_length: 'Longitud mínima de contraseña',
  session_minutes: 'Duración de la sesión (min)',
  max_failed_logins: 'Intentos fallidos permitidos',
  lockout_minutes: 'Minutos de bloqueo',
  require_complexity: 'Exigir contraseña compleja',
  registration_enabled: 'Registro de personas nuevas',
  ai_redact_pii: 'Ocultar datos personales a la IA',
  allowed_email_domains: 'Dominios de correo permitidos',
  allowed_ai_providers: 'Proveedores de IA permitidos',
  reason: 'Motivo',
  role: 'Rol',
  email: 'Correo',
}
const UNIT: Record<string, string> = {
  min_password_length: 'caracteres', session_minutes: 'min', max_failed_logins: 'intentos', lockout_minutes: 'min',
}

const when = (iso: string | null) => (iso ? new Date(iso).toLocaleString('es-CO', { dateStyle: 'medium', timeStyle: 'short' }) : '—')

function formatValue(key: string, value: any): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'boolean') return value ? 'Activado' : 'Desactivado'
  if (Array.isArray(value)) return value.length ? value.join(', ') : key.startsWith('allowed_') ? 'Sin restricción' : '—'
  if (key === 'role' && typeof value === 'string' && value in ROLE_LABEL) return ROLE_LABEL[value as Role]
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

type Change = { label: string; from?: string; to?: string; text?: string }

function describeDetails(details: Record<string, any> | null | undefined): Change[] {
  return Object.entries(details || {}).map(([key, value]) => {
    const label = FIELD_LABEL[key] || key
    if (value && typeof value === 'object' && !Array.isArray(value) && ('to' in value || 'from' in value)) {
      return { label, from: formatValue(key, (value as any).from), to: formatValue(key, (value as any).to) }
    }
    return { label, text: formatValue(key, value) }
  })
}

export function AdminPage({ role, email, onNotice }: {
  role: Role; email: string; onNotice: (notice: Notice) => void
}) {
  const [tab, setTab] = useState<'users' | 'policies' | 'audit'>('users')
  return (
    <div className="admin-page">
      <div className="page-heading admin-heading">
        <div className="eyebrow">ADMINISTRACIÓN</div>
        <h1>Panel de administración</h1>
      </div>
      <div className="admin-tabs" role="tablist">
        {([['users', 'Usuarios'], ['policies', 'Políticas de seguridad'], ['audit', 'Auditoría']] as const).map(([id, label]) => (
          <button key={id} role="tab" aria-selected={tab === id} className={tab === id ? 'active' : ''} onClick={() => setTab(id)}>{label}</button>
        ))}
      </div>
      {tab === 'users' && <UsersTab role={role} email={email} onNotice={onNotice} />}
      {tab === 'policies' && <PoliciesTab onNotice={onNotice} />}
      {tab === 'audit' && <AuditTab onNotice={onNotice} />}
    </div>
  )
}

function UsersTab({ role, email, onNotice }: { role: Role; email: string; onNotice: (notice: Notice) => void }) {
  const [users, setUsers] = useState<AdminUser[]>([])
  const [total, setTotal] = useState(0)
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('all')
  const [loading, setLoading] = useState(true)
  const [temp, setTemp] = useState<{ email: string; password: string } | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    api<{ total: number; users: AdminUser[] }>(`/api/admin/users?q=${encodeURIComponent(query)}&status=${status}&limit=100`)
      .then((result) => { setUsers(result.users); setTotal(result.total) })
      .catch((error) => onNotice({ text: error.message, error: true }))
      .finally(() => setLoading(false))
  }, [query, status, onNotice])

  useEffect(() => { load() }, [load])

  async function run(request: () => Promise<unknown>, success: string) {
    try { await request(); onNotice({ text: success }); load() } catch (error) { onNotice({ text: (error as Error).message, error: true }) }
  }

  const post = (user: AdminUser, action: string, body?: object) =>
    api(`/api/admin/users/${user.id}/${action}`, { method: 'POST', ...(body ? { body: JSON.stringify(body) } : {}) })

  async function resetPassword(user: AdminUser) {
    if (!window.confirm(`Se generará una contraseña temporal para ${user.email} y se cerrarán sus sesiones abiertas. ¿Continuar?`)) return
    try {
      const result = await api<{ email: string; temporary_password: string }>(`/api/admin/users/${user.id}/reset-password`, { method: 'POST' })
      setTemp({ email: result.email, password: result.temporary_password })
      load()
    } catch (error) { onNotice({ text: (error as Error).message, error: true }) }
  }

  function ban(user: AdminUser) {
    const reason = window.prompt(`Motivo del baneo de ${user.email} (mínimo 5 caracteres). Quedará registrado.`)
    if (reason && reason.trim().length >= 5) void run(() => post(user, 'ban', { reason }), 'Cuenta baneada.')
  }

  function remove(user: AdminUser) {
    const typed = window.prompt(`Esto elimina la cuenta y TODOS sus estudios. No se puede deshacer.\nEscribe el correo para confirmar:\n${user.email}`)
    if (typed) void run(() => api(`/api/admin/users/${user.id}?confirm_email=${encodeURIComponent(typed)}`, { method: 'DELETE' }), 'Cuenta eliminada.')
  }

  const toggleAdmin = (user: AdminUser) => {
    const makeAdmin = user.role === 'user'
    if (window.confirm(makeAdmin ? `¿Nombrar administrador a ${user.email}?` : `¿Quitar el rol de administrador a ${user.email}?`)) {
      void run(() => api(`/api/admin/users/${user.id}/role`, { method: 'PUT', body: JSON.stringify({ role: makeAdmin ? 'admin' : 'user' }) }), 'Rol actualizado.')
    }
  }

  return (
    <div className="card admin-card">
      <div className="admin-toolbar">
        <label className="admin-search"><Search size={14} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar por correo…" /></label>
        <select value={status} onChange={(event) => setStatus(event.target.value)} aria-label="Filtrar por estado">
          <option value="all">Todas</option><option value="active">Activas</option><option value="inactive">Inactivas</option><option value="banned">Baneadas</option>
        </select>
        <small>{total} {total === 1 ? 'cuenta' : 'cuentas'}</small>
      </div>
      {temp && (
        <div className="admin-temp" role="alert">
          <b>Contraseña temporal para {temp.email}</b>
          <code>{temp.password}</code>
          <span>Entrégala por un canal seguro. No se volverá a mostrar y {temp.email} deberá cambiarla al iniciar sesión.</span>
          <div>
            <button className="button-secondary" onClick={() => { void navigator.clipboard?.writeText(temp.password); onNotice({ text: 'Contraseña copiada.' }) }}>Copiar</button>
            <button className="button-secondary" onClick={() => setTemp(null)}>Ya la entregué</button>
          </div>
        </div>
      )}
      {loading && !users.length ? <TableSkeleton rows={6} /> : (
        <div className="table-scroll"><table className="admin-table users-table"><thead><tr><th>Correo</th><th>Rol</th><th>Estado</th><th>Estudios</th><th>Último acceso</th><th>Acciones</th></tr></thead><tbody>
          {users.map((user) => {
            const isSelf = user.email.toLowerCase() === email.toLowerCase()
            const canAct = !isSelf && user.role !== 'super_admin' && (role === 'super_admin' || user.role === 'user')
            const canRole = role === 'super_admin' && !isSelf && user.role !== 'super_admin'
            return (
              <tr key={user.id}>
                <td>{user.email}{isSelf && <small> (tú)</small>}{user.must_change_password && <small className="admin-flag"> · debe cambiar contraseña</small>}{user.locked && <small className="admin-flag"> · bloqueada</small>}</td>
                <td><span className={`admin-badge role-${user.role}`}>{ROLE_LABEL[user.role]}</span></td>
                <td><span className={`admin-badge st-${user.status}`} title={user.ban_reason ? `Motivo: ${user.ban_reason} (por ${user.banned_by})` : ''}>{STATUS_LABEL[user.status]}</span></td>
                <td>{user.study_count}</td>
                <td>{when(user.last_login_at)}</td>
                <td>
                  <div className="admin-actions">
                    {canAct && <>
                      <button onClick={() => void resetPassword(user)} title="Genera una contraseña temporal"><KeyRound size={12} /> Restablecer</button>
                      {user.status === 'banned'
                        ? <button onClick={() => void run(() => post(user, 'unban'), 'Baneo retirado.')}>Quitar baneo</button>
                        : <button onClick={() => ban(user)} title="Por incumplir las políticas. Queda el motivo registrado y se cierran las sesiones.">Banear</button>}
                      {user.status !== 'banned' && (user.status === 'inactive'
                        ? <button onClick={() => void run(() => post(user, 'reactivate'), 'Cuenta reactivada.')}>Reactivar</button>
                        : <button onClick={() => void run(() => post(user, 'deactivate'), 'Cuenta inactivada.')} title="Para quien ya no hace parte de la organización (reversible).">Inactivar</button>)}
                      <button className="danger" onClick={() => remove(user)}>Eliminar</button>
                    </>}
                    {canRole && <button onClick={() => toggleAdmin(user)}><ShieldCheck size={12} /> {user.role === 'user' ? 'Hacer administrador' : 'Quitar admin'}</button>}
                    {!canAct && !canRole && <span className="admin-muted">—</span>}
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody></table></div>
      )}
    </div>
  )
}

const parseDomains = (text: string) => text.split(',').map((item) => item.trim()).filter(Boolean)

function PoliciesTab({ onNotice }: { onNotice: (notice: Notice) => void }) {
  const [info, setInfo] = useState<PolicyInfo | null>(null)
  const [saved, setSaved] = useState<Record<string, any>>({})
  const [draft, setDraft] = useState<Record<string, any>>({})
  const [domains, setDomains] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api<PolicyInfo>('/api/admin/policies')
      .then((result) => {
        setInfo(result); setSaved(result.policy); setDraft(result.policy)
        setDomains((result.policy.allowed_email_domains || []).join(', '))
      })
      .catch((error) => onNotice({ text: error.message, error: true }))
  }, [onNotice])

  async function save() {
    setBusy(true)
    try {
      const changes = { ...draft, allowed_email_domains: parseDomains(domains) }
      const result = await api<{ policy: Record<string, any>; changed: string[] }>('/api/admin/policies', { method: 'PUT', body: JSON.stringify({ changes }) })
      setSaved(result.policy); setDraft(result.policy)
      setDomains((result.policy.allowed_email_domains || []).join(', '))
      onNotice({ text: result.changed.length ? `Políticas guardadas (${result.changed.length} cambios).` : 'No había cambios.' })
    } catch (error) { onNotice({ text: (error as Error).message, error: true }) } finally { setBusy(false) }
  }

  if (!info) return <div className="card admin-card"><TableSkeleton rows={5} /></div>

  const dirty = JSON.stringify({ ...draft, allowed_email_domains: parseDomains(domains) })
    !== JSON.stringify({ ...saved, allowed_email_domains: saved.allowed_email_domains || [] })

  const number = (key: string) => (
    <label key={key} className="policy-field">
      <span>{info.fields[key].label}</span>
      <span className="policy-input">
        <input type="number" min={info.fields[key].min ?? undefined} max={info.fields[key].max ?? undefined} value={draft[key] ?? ''}
          onChange={(event) => setDraft({ ...draft, [key]: Number(event.target.value) })} />
        {UNIT[key] && <span className="unit">{UNIT[key]}</span>}
      </span>
      <small>Entre {info.fields[key].min} y {info.fields[key].max}</small>
    </label>
  )
  const toggle = (key: string) => (
    <label key={key} className="policy-switch">
      <span>{info.fields[key].label}</span>
      <input type="checkbox" checked={Boolean(draft[key])} onChange={(event) => setDraft({ ...draft, [key]: event.target.checked })} />
    </label>
  )
  const allowed: string[] = draft.allowed_ai_providers || []

  return (
    <div className="card admin-card policy-card">
      <div className="admin-card-head">
        <div>
          <h2>Políticas de seguridad</h2>
          <p>Los cambios aplican a nuevos inicios de sesión, registros y cambios de contraseña. Cada cambio queda en la auditoría.</p>
        </div>
      </div>

      <section className="policy-section">
        <div className="policy-section-head">
          <h3>Contraseñas</h3>
          <p>Qué tan robustas deben ser las contraseñas nuevas.</p>
        </div>
        <div className="policy-section-body">
          <div className="policy-grid">{number('min_password_length')}</div>
          <div className="policy-switches">{toggle('require_complexity')}</div>
        </div>
      </section>

      <section className="policy-section">
        <div className="policy-section-head">
          <h3>Sesión y bloqueo</h3>
          <p>Duración de la sesión y protección contra intentos fallidos.</p>
        </div>
        <div className="policy-section-body">
          <div className="policy-grid">
            {['session_minutes', 'max_failed_logins', 'lockout_minutes'].map(number)}
          </div>
        </div>
      </section>

      <section className="policy-section">
        <div className="policy-section-head">
          <h3>Registro de cuentas</h3>
          <p>Quién puede crear una cuenta nueva.</p>
        </div>
        <div className="policy-section-body">
          <div className="policy-switches">{toggle('registration_enabled')}</div>
          <label className="policy-field">
            <span>{info.fields.allowed_email_domains.label}</span>
            <span className="policy-input">
              <input value={domains} onChange={(event) => setDomains(event.target.value)} placeholder="empresa.com, empresa.co" />
            </span>
            <small>Separa los dominios con comas.</small>
          </label>
        </div>
      </section>

      <section className="policy-section">
        <div className="policy-section-head">
          <h3>Inteligencia artificial</h3>
          <p>Privacidad de los datos y proveedores habilitados.</p>
        </div>
        <div className="policy-section-body">
          <div className="policy-switches">{toggle('ai_redact_pii')}</div>
          <div className="policy-field">
            <span>{info.fields.allowed_ai_providers.label}</span>
            <div className="policy-providers">
              {info.providers.map((provider) => (
                <label key={provider.id} className="policy-chip">
                  <input type="checkbox" checked={allowed.includes(provider.id)}
                    onChange={(event) => setDraft({ ...draft, allowed_ai_providers: event.target.checked ? [...allowed, provider.id] : allowed.filter((id) => id !== provider.id) })} />
                  {provider.name}
                </label>
              ))}
            </div>
            <small>{allowed.length ? 'Solo se podrán usar los proveedores marcados.' : 'Sin marcar = se permiten todos.'}</small>
          </div>
        </div>
      </section>

      <div className="policy-footer">
        <span className="policy-dirty">{dirty ? 'Tienes cambios sin guardar' : ''}</span>
        <div className="policy-buttons">
          <button className="button-secondary" disabled={busy} onClick={() => { setDraft(info.defaults); setDomains((info.defaults.allowed_email_domains || []).join(', ')) }}>Restaurar valores por defecto</button>
          <button className="button-primary" disabled={busy || !dirty} onClick={() => void save()}>{busy ? 'Guardando…' : 'Guardar políticas'}</button>
        </div>
      </div>
    </div>
  )
}

function AuditTab({ onNotice }: { onNotice: (notice: Notice) => void }) {
  const [events, setEvents] = useState<AuditEvent[] | null>(null)
  useEffect(() => {
    api<{ events: AuditEvent[] }>('/api/admin/audit?limit=150').then((result) => setEvents(result.events)).catch((error) => onNotice({ text: error.message, error: true }))
  }, [onNotice])
  if (!events) return <div className="card admin-card"><TableSkeleton rows={6} /></div>
  return (
    <div className="card admin-card">
      <div className="admin-card-head">
        <div>
          <h2>Registro de acciones administrativas</h2>
          <p>Quién hizo qué y cuándo. Los más recientes primero.</p>
        </div>
        <small className="admin-count">{events.length} {events.length === 1 ? 'evento' : 'eventos'}</small>
      </div>
      {!events.length ? <p className="admin-help">Aún no hay acciones registradas.</p> : (
        <div className="table-scroll"><table className="admin-table audit-table"><thead><tr><th>Fecha</th><th>Quién</th><th>Acción</th><th>Sobre</th><th>Detalle</th></tr></thead><tbody>
          {events.map((event) => {
            const changes = describeDetails(event.details)
            return (
              <tr key={event.id}>
                <td className="audit-when">{when(event.created_at)}</td>
                <td>{event.actor}</td>
                <td><span className={`audit-pill act-${event.action}`}>{ACTION_LABEL[event.action] || event.action}</span></td>
                <td>{event.target || '—'}</td>
                <td className="audit-details">
                  {changes.length ? changes.map((change) => (
                    change.text !== undefined
                      ? <div key={change.label} className="audit-line"><span className="audit-field">{change.label}:</span> {change.text}</div>
                      : <div key={change.label} className="audit-line">
                          <span className="audit-field">{change.label}</span>
                          <span className="audit-chip audit-from">{change.from}</span>
                          <span className="audit-arrow">→</span>
                          <span className="audit-chip audit-to">{change.to}</span>
                        </div>
                  )) : <span className="admin-muted">—</span>}
                </td>
              </tr>
            )
          })}
        </tbody></table></div>
      )}
    </div>
  )
}
