/** Avisos globales cuando el servidor corta o condiciona la sesión (baneo, inactivación, cambio de contraseña obligatorio). */
export const SESSION_ENDED = 'insights:session-ended'
export const PASSWORD_CHANGE_REQUIRED = 'insights:password-change-required'

const AUTH_PATHS = ['/api/auth/login', '/api/auth/register', '/api/auth/change-password']

export function reportAuthFailure(status: number, body: any, path: string) {
  if (AUTH_PATHS.some((prefix) => path.startsWith(prefix))) return
  const code = body?.code
  if (status === 403 && code === 'password_change_required') {
    window.dispatchEvent(new Event(PASSWORD_CHANGE_REQUIRED))
    return
  }
  if (status === 401 || (status === 403 && (code === 'account_banned' || code === 'account_inactive'))) {
    window.dispatchEvent(new CustomEvent(SESSION_ENDED, { detail: typeof body?.detail === 'string' ? body.detail : 'Tu sesión terminó. Inicia sesión de nuevo.' }))
  }
}
