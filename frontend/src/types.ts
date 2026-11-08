export type Page = 'home' | 'categorize' | 'dashboard' | 'awareness' | 'settings' | 'admin'
export type Role = 'user' | 'admin' | 'super_admin'

export type Study = { id: string; name: string; source_filename: string; columns: string[]; row_count: number; created_at: string }

export type Category = { nombre: string; descripcion: string }

export type Classification = {
  id: string; study_id: string; question: string; kind: 'themes' | 'brands' | 'sentiment'; categories: string[];
  codeframe: Category[]; entities: string[]; aliases: Record<string, string[]>; config: Record<string, unknown>;
  has_insights: boolean; updated_at?: string;
}

export type Frequency = { Categoría: string; Menciones: number; '%': number }

export type ReviewRow = { row_index: number; response: string | null; labels: string[] }

export type AwarenessProfile = {
  name: string
  tom_code: string
  spontaneous_codes: string
  aided_codes: string
}

export type AwarenessValidationRow = { tipo: string; campo: string; columnas: string }
