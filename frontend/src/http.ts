import { reportAuthFailure } from './authEvents'
/** Cliente mínimo para componentes que consultan la API con el token de sesión. */
async function requestJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  const token = sessionStorage.getItem('insights-token')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  const response = await fetch(path, { ...options, headers })
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    reportAuthFailure(response.status, body, path)
    throw new Error(typeof body.detail === 'string' ? body.detail : 'Ocurrió un error al consultar el servidor.')
  }
  return response.json() as Promise<T>
}

const inflight = new Map<string, Promise<unknown>>()

export function getJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const method = (options.method || 'GET').toUpperCase()
  if (method !== 'GET' || options.body) return requestJson<T>(path, options)
  const key = `${path}|${sessionStorage.getItem('insights-token') || ''}`
  const pending = inflight.get(key)
  if (pending) return pending as Promise<T>
  const promise = requestJson<T>(path, options).finally(() => inflight.delete(key))
  inflight.set(key, promise)
  return promise
}
