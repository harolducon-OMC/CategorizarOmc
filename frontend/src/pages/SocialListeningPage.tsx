import { useMemo, useState, type FormEvent } from 'react'
import { AlertTriangle, BarChart3, Download, ExternalLink, MessageCircle, Search, Settings2, Sparkles } from 'lucide-react'
import { api } from '../api'
import { MetricCard, PageHeading } from '../components/common'
import './social-listening.css'

type Sentiment = 'positivo' | 'neutral' | 'negativo'
type Mention = {
  platform: string
  kind: string
  text: string
  url: string
  language: string
  location: string
  analysis: { sentiment: Sentiment; score: number; emotion: string; topic: string; pain_point?: string | null; risk: boolean; country: string }
}
type AnalysisResult = {
  summary: {
    marca: string
    total_menciones: number
    'sentimiento_%': Record<string, number>
    score_promedio: number
    score_por_red: Record<string, number>
    temas_top: [string, number][]
    pain_points_top: [string, number][]
    alertas_riesgo: { red: string; texto: string }[]
  }
  mentions: Mention[]
}
const NETWORKS = ['Twitter', 'Instagram', 'Tiktok', 'Reddit']
const LANGUAGES = [{ code: 'es', label: 'Español' }, { code: 'en', label: 'Inglés' }, { code: 'pt', label: 'Portugués' }, { code: 'fr', label: 'Francés' }]
const MODEL_DEFAULTS: Record<string, string> = { gemini: 'gemini-3.5-flash-lite', groq: 'llama-3.3-70b-versatile' }
const SENTIMENTS: Sentiment[] = ['positivo', 'neutral', 'negativo']

function csvCell(value: unknown) {
  const text = String(value ?? '')
  const safe = /^[\u0000-\u0020]*[=+\-@]/.test(text) ? `'${text}` : text
  return `"${safe.replace(/"/g, '""')}"`
}
function downloadCsv(rows: Mention[], brand: string) {
  const header = ['Red', 'Tipo', 'Sentimiento', 'Score', 'Emoción', 'Tema', 'Pain point', 'Riesgo', 'País', 'Idioma', 'Texto', 'Enlace']
  const lines = [header, ...rows.map((item) => [item.platform, item.kind, item.analysis.sentiment, item.analysis.score, item.analysis.emotion, item.analysis.topic, item.analysis.pain_point || '', item.analysis.risk ? 'Sí' : 'No', item.analysis.country, item.language, item.text, item.url])]
  const blob = new Blob(['\uFEFF' + lines.map((row) => row.map(csvCell).join(',')).join('\r\n')], { type: 'text/csv;charset=utf-8' })
  const href = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = href
  link.download = `escucha-social-${brand.trim().replace(/[^\p{L}\p{N}-]+/gu, '-').slice(0, 60) || 'reporte'}.csv`
  link.click()
  URL.revokeObjectURL(href)
}

export function SocialListeningPage({ onOpenSettings }: { onOpenSettings: () => void }) {
  const [brand, setBrand] = useState('')
  const [platforms, setPlatforms] = useState<string[]>(['Twitter', 'Reddit'])
  const [languages, setLanguages] = useState<string[]>(['es'])
  const [maxMentions, setMaxMentions] = useState(60)
  const [withComments, setWithComments] = useState(false)
  const [provider, setProvider] = useState<'gemini' | 'groq'>('gemini')
  const [model, setModel] = useState(MODEL_DEFAULTS.gemini)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [networkFilter, setNetworkFilter] = useState('Todas')
  const [sentimentFilter, setSentimentFilter] = useState('Todos')
  const [query, setQuery] = useState('')

  const filteredMentions = useMemo(() => (result?.mentions || []).filter((item) => {
    const networkOk = networkFilter === 'Todas' || item.platform === networkFilter
    const sentimentOk = sentimentFilter === 'Todos' || item.analysis.sentiment === sentimentFilter
    const q = query.trim().toLocaleLowerCase()
    const textOk = !q || [item.text, item.analysis.topic, item.analysis.pain_point, item.analysis.emotion].some((v) => String(v || '').toLocaleLowerCase().includes(q))
    return networkOk && sentimentOk && textOk
  }), [result, networkFilter, sentimentFilter, query])

  async function analyze(event: FormEvent) {
    event.preventDefault()
    if (!brand.trim()) { setError('Escribe una marca o palabra clave.'); return }
    if (!platforms.length) { setError('Selecciona al menos una red social.'); return }
    if (!model.trim()) { setError('Indica el ID del modelo de IA.'); return }
    setLoading(true); setError(''); setResult(null)
    try {
      const response = await api<AnalysisResult>('/api/social-listening/analyze', {
        method: 'POST',
        body: JSON.stringify({ brand: brand.trim(), max_mentions: maxMentions, platforms, languages, with_comments: withComments, provider, model: model.trim() }),
      })
      setResult(response)
      setNetworkFilter('Todas'); setSentimentFilter('Todos'); setQuery('')
    } catch (err) {
      setError((err as Error).message || 'No se pudo completar el análisis.')
    } finally { setLoading(false) }
  }

  function toggle(setter: (value: string[]) => void, current: string[], value: string) {
    setter(current.includes(value) ? current.filter((item) => item !== value) : [...current, value])
  }

  const summary = result?.summary
  const risks = summary?.alertas_riesgo || []
  return <div className="social-page">
    <PageHeading eyebrow="INTELIGENCIA DE MARCA" title="Escucha social" text="Busca menciones públicas y analiza sentimiento, temas y señales de riesgo en redes sociales." action={<button className="button-secondary" onClick={onOpenSettings}><Settings2 size={15} /> Configurar claves</button>} />

    <form className="card social-search-card" onSubmit={analyze}>
      <div className="social-section-label"><Search size={15} /> BÚSQUEDA Y FUENTES</div>
      <div className="social-search-row"><label className="social-brand-field">Marca o palabra clave<input value={brand} onChange={(e) => setBrand(e.target.value)} placeholder="Ej. nombre de marca" maxLength={120} /></label><label className="social-max-field">Máx. menciones<select value={maxMentions} onChange={(e) => setMaxMentions(Number(e.target.value))}>{[20, 40, 60, 100, 150, 200].map((n) => <option key={n} value={n}>{n}</option>)}</select></label></div>
      <div className="social-option-grid">
        <fieldset className="social-option-group"><legend>Redes sociales</legend><div className="social-checks">{NETWORKS.map((network) => <label className="social-check" key={network}><input type="checkbox" checked={platforms.includes(network)} onChange={() => toggle(setPlatforms, platforms, network)} />{network}</label>)}</div></fieldset>
        <fieldset className="social-option-group"><legend>Idioma</legend><div className="social-checks">{LANGUAGES.map((language) => <label className="social-check" key={language.code}><input type="checkbox" checked={languages.includes(language.code)} onChange={() => toggle(setLanguages, languages, language.code)} />{language.label}</label>)}</div><small>Sin selección: todos los idiomas.</small></fieldset>
      </div>
      <div className="social-ai-row"><label>Proveedor de análisis<select value={provider} onChange={(e) => { const value = e.target.value as 'gemini' | 'groq'; setProvider(value); setModel(MODEL_DEFAULTS[value]) }}><option value="gemini">Google Gemini · clave independiente</option><option value="groq">Groq · clave independiente</option></select></label><label className="social-model-field">ID del modelo<input value={model} onChange={(e) => setModel(e.target.value)} maxLength={160} /></label></div>
      <label className="social-comments"><input type="checkbox" checked={withComments} onChange={(e) => setWithComments(e.target.checked)} /><span>Incluir comentarios de Instagram y TikTok <small>Puede consumir créditos adicionales de Xpoz.</small></span></label>
      <div className="social-form-footer"><span className="social-private-note">Las claves se configuran en Ajustes y nunca se muestran aquí.</span><button className="button-primary social-run" type="submit" disabled={loading}>{loading ? <><span className="social-spinner" /> Analizando…</> : <><Sparkles size={15} /> Analizar menciones</>}</button></div>
      {loading && <div className="social-loading" role="status">Consultando redes y clasificando menciones con {provider === 'gemini' ? 'Gemini' : 'Groq'}. Puede tardar un poco.</div>}
      {error && <div className="social-error" role="alert">{error}{/clave|configur/i.test(error) && <button type="button" className="button-text" onClick={onOpenSettings}>Abrir Ajustes</button>}</div>}
    </form>

    {!result && !loading && <div className="social-empty"><div className="social-empty-icon"><MessageCircle size={23} /></div><h2>Tu informe aparecerá aquí</h2><p>Elige una marca y las redes que quieres consultar. Los resultados de este análisis son temporales y no se guardan como estudios ni se mezclan con la categorización.</p></div>}

    {result && <section className="social-results" aria-live="polite">
      <div className="social-results-heading"><div><div className="eyebrow">RESULTADOS DE BÚSQUEDA</div><h2>{result.summary.marca}</h2><p>{summary?.total_menciones || 0} menciones clasificadas · datos disponibles solo en esta sesión</p></div><button className="button-secondary" onClick={() => downloadCsv(filteredMentions, result.summary.marca)} disabled={!filteredMentions.length}><Download size={15} /> Descargar CSV</button></div>
      <div className="social-metric-grid">
        <MetricCard icon={<MessageCircle size={17} />} label="Menciones" value={summary?.total_menciones || 0} sub="Clasificadas por IA" color="blue" />
        <MetricCard icon={<BarChart3 size={17} />} label="Score promedio" value={summary?.score_promedio ?? '—'} sub="Escala de −1 a 1" color="mint" />
        <MetricCard icon={<Sparkles size={17} />} label="Sentimiento positivo" value={`${summary?.['sentimiento_%']?.positivo ?? 0}%`} sub="Sobre el total analizado" color="purple" />
        <MetricCard icon={<AlertTriangle size={17} />} label="Alertas de riesgo" value={risks.length} sub="Revisar menciones señaladas" color="orange" />
      </div>
      <div className="social-insights-grid">
        <div className="card social-insight-card"><h3>Sentimiento</h3>{SENTIMENTS.map((sentiment) => { const value = summary?.['sentimiento_%']?.[sentiment] || 0; return <div className="social-sentiment-row" key={sentiment}><span>{sentiment}</span><div className="social-track"><i className={`social-fill ${sentiment}`} style={{ width: `${Math.min(100, value)}%` }} /></div><b>{value}%</b></div> })}</div>
        <div className="card social-insight-card"><h3>Temas principales</h3>{summary?.temas_top?.length ? <ol className="social-ranked-list">{summary.temas_top.slice(0, 6).map(([topic, count]) => <li key={topic}><span>{topic}</span><b>{count}</b></li>)}</ol> : <p className="social-muted">No se detectaron temas.</p>}</div>
        <div className="card social-insight-card"><h3>Pain points</h3>{summary?.pain_points_top?.length ? <ol className="social-ranked-list">{summary.pain_points_top.slice(0, 6).map(([topic, count]) => <li key={topic}><span>{topic}</span><b>{count}</b></li>)}</ol> : <p className="social-muted">No se detectaron pain points.</p>}</div>
      </div>
      {risks.length > 0 && <div className="social-risk-panel"><div><AlertTriangle size={17} /><b>Menciones que requieren revisión</b></div>{risks.slice(0, 5).map((risk, i) => <p key={`${risk.red}-${i}`}><span>{risk.red}</span>{risk.texto}</p>)}</div>}
      <div className="card social-table-card"><div className="social-table-heading"><div><h3>Menciones analizadas</h3><p>{filteredMentions.length} de {result.mentions.length} filas</p></div><div className="social-table-filters"><label className="social-filter-search"><Search size={14} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar en menciones" /></label><select aria-label="Filtrar por red" value={networkFilter} onChange={(e) => setNetworkFilter(e.target.value)}><option>Todas</option>{NETWORKS.map((network) => <option key={network}>{network}</option>)}</select><select aria-label="Filtrar por sentimiento" value={sentimentFilter} onChange={(e) => setSentimentFilter(e.target.value)}><option>Todos</option>{SENTIMENTS.map((sentiment) => <option key={sentiment}>{sentiment}</option>)}</select></div></div>
        {filteredMentions.length ? <div className="social-table-scroll"><table><thead><tr><th>Red</th><th>Sentimiento</th><th>Tema / emoción</th><th>Mención</th><th>País</th><th>Enlace</th></tr></thead><tbody>{filteredMentions.map((item, index) => <tr key={`${item.platform}-${index}`}><td>{item.platform}<small>{item.kind}</small></td><td><span className={`social-sentiment-tag ${item.analysis.sentiment}`}>{item.analysis.sentiment}</span><small>score {Number(item.analysis.score).toFixed(2)}</small></td><td>{item.analysis.topic}<small>{item.analysis.emotion}{item.analysis.pain_point ? ` · ${item.analysis.pain_point}` : ''}</small></td><td className="social-mention-text">{item.text}{item.analysis.risk && <span className="social-risk-label">Riesgo</span>}</td><td>{item.analysis.country || 'desconocido'}</td><td>{item.url ? <a href={item.url} target="_blank" rel="noreferrer" aria-label="Abrir mención"><ExternalLink size={14} /></a> : '—'}</td></tr>)}</tbody></table></div> : <div className="social-muted social-no-rows">No hay menciones que coincidan con los filtros.</div>}
      </div>
      <p className="social-disclaimer">El análisis de sentimiento es una clasificación automatizada y puede equivocarse. Verifica las menciones antes de tomar decisiones.</p>
    </section>}
  </div>
}
