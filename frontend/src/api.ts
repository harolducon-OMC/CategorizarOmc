import { reportAuthFailure } from './authEvents'
async function request<T>(path: string, options: RequestInit = {}, apiKey = ''): Promise<T> {
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
    reportAuthFailure(response.status, body, path)
    throw new Error(typeof body.detail === 'string' ? body.detail : 'Ocurrió un error al consultar el servidor.')
  }
  return response.json() as Promise<T>
}

const inflight = new Map<string, Promise<unknown>>()

/**
 * Cliente de la API. Si dos componentes piden el mismo GET a la vez, se hace una sola llamada
 * y ambos reciben el mismo resultado (la clave incluye la sesión y la API key).
 */
export function api<T>(path: string, options: RequestInit = {}, apiKey = ''): Promise<T> {
  const method = (options.method || 'GET').toUpperCase()
  if (method !== 'GET' || options.body) return request<T>(path, options, apiKey)
  const key = `${path}|${apiKey}|${sessionStorage.getItem('insights-token') || ''}`
  const pending = inflight.get(key)
  if (pending) return pending as Promise<T>
  const promise = request<T>(path, options, apiKey).finally(() => inflight.delete(key))
  inflight.set(key, promise)
  return promise
}
