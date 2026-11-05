import { useEffect, useState } from 'react'
import { ArrowRight, Check, Database, LoaderCircle, MessageSquareText, Plus, Sparkles, Tags, WandSparkles, X } from 'lucide-react'
import { api } from '../api'
import { PageHeading, EmptyState } from '../components/common'
import { PROVIDERS } from '../constants'
import type { Category } from '../types'

export function CategorizePage({ study, apiKey, provider, model, onRefresh, onNotice, busy, setBusy }: any) {
  const [question, setQuestion] = useState('')
  const [kind, setKind] = useState<'themes' | 'brands'>('themes')
  const [context, setContext] = useState('')
  const [knownText, setKnownText] = useState('')
  const [frame, setFrame] = useState<Category[]>([])
  const [multi, setMulti] = useState(true)
  const questions: string[] = study?.suggested_questions?.length ? study.suggested_questions : study?.columns || []
  useEffect(() => { setQuestion(study?.suggested_questions?.[0] || study?.columns?.[0] || ''); setFrame([]) }, [study?.id])
  async function propose() {
    if (!study || !question) { onNotice({ text: 'Selecciona una pregunta.', error: true }); return }
    setBusy(true)
    try {
      const result = await api<{ codeframe: Category[] }>(`/api/studies/${study.id}/propose-categories`, {
        method: 'POST', body: JSON.stringify({ question, context, provider, model, max_categories: 10 }),
      }, apiKey)
      setFrame(result.codeframe)
      onNotice({ text: `Se propusieron ${result.codeframe.length} categorías. Puedes editar el catálogo antes de clasificar.` })
    } catch (err) { onNotice({ text: (err as Error).message, error: true }) }
    finally { setBusy(false) }
  }
  async function classify() {
    if (!study || !question) return
    
    if (kind === 'themes' && !frame.length) { onNotice({ text: 'Primero propone o agrega categorías.', error: true }); return }
    setBusy(true)
    try {
      const result = await api<any>(`/api/studies/${study.id}/classifications`, {
        method: 'POST', body: JSON.stringify({
          question, kind, codeframe: frame, known_brands: knownText.split('\n').map((v) => v.trim()).filter(Boolean),
          context, multi, provider, model, max_categories: 10,
        }),
      }, apiKey)
      await onRefresh(study.id)
      onNotice({ text: `Clasificación guardada · ${result.categories.length} categorías disponibles.` })
    } catch (err) { onNotice({ text: (err as Error).message, error: true }) }
    finally { setBusy(false) }
  }
  if (!study) return <EmptyState title="Carga o selecciona un estudio" text="La categorización se activa cuando tengas una encuesta lista." action="Ir a Inicio" />
  return <>
    <PageHeading eyebrow="CODIFICACIÓN ASISTIDA" title="Categorización" text="Define el catálogo, aplica la IA y revisa las etiquetas con control total." />
    <div className="stepper"><div className="step active"><span>01</span><b>Configurar</b></div><div className="step-line" /><div className="step"><span>02</span><b>Revisar catálogo</b></div><div className="step-line" /><div className="step"><span>03</span><b>Clasificar y editar</b></div></div>
    <div className="form-layout">
      <section className="card form-card">
        <div className="card-heading"><div><div className="card-label">01 · PREGUNTA</div><h3>¿Qué quieres analizar?</h3></div><span className="soft-badge">{study.row_count.toLocaleString()} respuestas</span></div>
        <label>Pregunta abierta<select value={question} onChange={(e) => setQuestion(e.target.value)}>{(study.columns || []).map((c: string) => <option key={c} value={c}>{c}</option>)}</select></label>
        <div className="field-label">Tipo de análisis</div>
        <div className="segmented"><button className={kind === 'themes' ? 'selected' : ''} onClick={() => setKind('themes')}><MessageSquareText size={16} /> Temas / motivos</button><button className={kind === 'brands' ? 'selected' : ''} onClick={() => setKind('brands')}><Tags size={16} /> Marcas</button></div>
        {kind === 'themes' ? <>
          <label>Contexto del estudio <span className="optional">OPCIONAL</span><textarea rows={3} value={context} onChange={(e) => setContext(e.target.value)} placeholder="Producto, categoría, mercado o instrucciones para el análisis…" /></label>
          <div className="inline-actions"><button className="button-secondary" onClick={propose} disabled={busy}><WandSparkles size={16} /> Proponer categorías con IA</button><span className="muted">Puedes editarlas antes de clasificar.</span></div>
          <div className="codeframe-editor">
            <div className="editor-heading"><div><b>Catálogo de categorías</b><small>{frame.length} categorías</small></div><button className="icon-button" title="Agregar categoría" onClick={() => setFrame([...frame, { nombre: '', descripcion: '' }])}><Plus size={17} /></button></div>
            {frame.length === 0 ? <div className="empty-frame"><Sparkles size={18} /><span>Propón categorías con IA o crea el catálogo manualmente.</span></div> : frame.map((item, index) => <div className="category-edit-row" key={index}><span className="category-num">{String(index + 1).padStart(2, '0')}</span><input value={item.nombre} placeholder="Nombre" onChange={(e) => setFrame(frame.map((v, i) => i === index ? { ...v, nombre: e.target.value } : v))} /><input value={item.descripcion} placeholder="Qué incluye (opcional)" onChange={(e) => setFrame(frame.map((v, i) => i === index ? { ...v, descripcion: e.target.value } : v))} /><button className="tiny-icon" onClick={() => setFrame(frame.filter((_, i) => i !== index))} title="Eliminar"><X size={15} /></button></div>)}
          </div>
          <label className="check-row"><input type="checkbox" checked={multi} onChange={(e) => setMulti(e.target.checked)} /><span>Permitir varias categorías por respuesta</span></label>
        </> : <>
          <label>Marcas permitidas <span className="optional">UNA POR LÍNEA</span><textarea rows={6} value={knownText} onChange={(e) => setKnownText(e.target.value)} placeholder={'Marca A\nMarca B\nMarca C'} /><small className="field-help">Catálogo cerrado: la IA asigna únicamente estas marcas. Una marca fuera del catálogo se clasifica como “Otra”; “Ninguna” requiere una respuesta explícita sin marca y una respuesta sin información será NS/NR.</small></label>
          <div className="info-callout"><Check size={16} /><span>Las marcas detectadas se podrán normalizar y corregir antes de Awareness.</span></div>
        </>}
        <button className="button-primary full-width classify-button" onClick={classify} disabled={busy || !question || (kind === 'themes' && !frame.length)}>{busy ? <><LoaderCircle className="spin" size={16} /> Procesando respuestas...</> : <><Sparkles size={16} /> Clasificar {study.row_count.toLocaleString()} respuestas</>}</button>
        <div className="privacy-note"><Database size={14} /> La API key cifrada se guarda en tu cuenta y puedes cambiarla desde Ajustes.</div>
      </section>
      <aside className="card side-info-card"><div className="side-info-symbol"><Sparkles size={20} /></div><div className="card-label">ASISTENCIA INTELIGENTE</div><h3>IA con el catálogo bajo tu control</h3><p>Define el marco de categorías o la lista de marcas y revisa lo que la IA produce. Las etiquetas se pueden corregir fila por fila después de clasificar.</p><div className="info-separator" /><div className="info-item"><span>Proveedor</span><b>{PROVIDERS[provider]?.label || provider}</b></div><div className="info-item"><span>Modelo</span><b>{model || 'No configurado'}</b></div><button className="text-link" onClick={() => onNotice({ text: 'Edita proveedor, modelo y API key desde Ajustes en el menú izquierdo.' })}>Configurar proveedor <ArrowRight size={14} /></button></aside>
    </div>
  </>
}
