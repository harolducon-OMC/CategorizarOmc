import { api } from './api'

/** Cliente mínimo para componentes que consultan la API con el token de sesión (misma lógica que api.ts). */
export function getJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  return api<T>(path, options)
}
