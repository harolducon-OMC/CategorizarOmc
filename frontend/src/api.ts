
export async function api<T>(path: string, options: RequestInit = {}, apiKey = ''): Promise<T> {
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
    throw new Error(body.detail || 'Ocurrió un error al consultar el servidor.')
  }
  return response.json() as Promise<T>
}
