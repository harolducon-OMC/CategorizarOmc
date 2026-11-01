/** Cliente mínimo para componentes que consultan la API con el token de sesión. */
export async function getJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  const token = sessionStorage.getItem('insights-token')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  const response = await fetch(path, { ...options, headers })
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(typeof body.detail === 'string' ? body.detail : 'Ocurrió un error al consultar el servidor.')
  }
  return response.json() as Promise<T>
}
