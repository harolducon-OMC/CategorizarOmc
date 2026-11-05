import { useState } from 'react'
import { ArrowRight, BarChart3, Database, FileSpreadsheet, Layers3, LoaderCircle, Sparkles, Tags, Trash2, UploadCloud, UsersRound } from 'lucide-react'
import { api } from '../api'
import { PageHeading, MetricCard, DataTable } from '../components/common'
import type { Page, Study } from '../types'
import FlowGuide from '../FlowGuide'

export function HomePage({ studies, study, onUpload, busy, onDelete, onGo }: {
  studies: Study[]; study: any; busy: boolean;
  onUpload: (file: File, name: string, sheet: string) => Promise<void>;
  onDelete: (id: string) => void; onGo: (page: Page) => void;
}) {
  const [file, setFile] = useState<File | null>(null)
  const [name, setName] = useState('')
  const [sheet, setSheet] = useState('')
  const [sheets, setSheets] = useState<string[]>([])
  const [uploadError, setUploadError] = useState('')
  const [dragging, setDragging] = useState(false)
  const [guideOpen, setGuideOpen] = useState(false)
  async function selectFile(next: File | null) {
    setFile(next); setUploadError(''); setSheets([]); setSheet('')
    if (!next) return
    if (!/\.(csv|xlsx)$/i.test(next.name)) { setUploadError('Elige un archivo CSV o XLSX.'); return }
    if (next.size > 25 * 1024 * 1024) { setUploadError('El archivo supera el límite de 25 MB.'); return }
    setName(next.name.replace(/\.[^.]+$/, ''))
    if (/\.xlsx$/i.test(next.name)) {
      try {
        const form = new FormData(); form.append('file', next)
        const result = await api<{ sheets: string[] }>('/api/uploads/sheets', { method: 'POST', body: form })
        setSheets(result.sheets); setSheet(result.sheets[0] || '')
      } catch (err) { setUploadError((err as Error).message) }
    }
  }
  return <>
    <PageHeading eyebrow="VISTA GENERAL" title="Tu espacio de análisis" text="Carga una encuesta, categoriza respuestas y convierte la voz de tus clientes en decisiones." action={<div className="secure-chip"><Database size={15} /> Privado en tu entorno</div>} />
    <div className="welcome-strip"><div className="welcome-icon"><Sparkles size={19} /></div><div><b>Bienvenido a Insights Studio</b><span>Un flujo de investigación más claro: importa, codifica, explora y exporta desde una sola vista.</span></div><button onClick={() => setGuideOpen(true)}>Ver flujo <ArrowRight size={15} /></button></div>
    {guideOpen && <FlowGuide hasStudy={!!study} onClose={() => setGuideOpen(false)} onGo={onGo} />}
    <div className="section-title-row"><div><h2>Importar una encuesta</h2><p>Se guardará en PostgreSQL para continuar después.</p></div><span className="file-limit">CSV o XLSX · Hasta 25 MB</span></div>
    <div className="upload-layout">
      <div className={`upload-card ${dragging ? 'dragging' : ''}`} onDragOver={(e) => { e.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={(e) => { e.preventDefault(); setDragging(false); selectFile(e.dataTransfer.files[0] || null) }}>
        <input id="file-input" type="file" accept=".csv,.xlsx" onChange={(e) => selectFile(e.target.files?.[0] || null)} hidden />
        <div className="upload-icon"><UploadCloud size={26} /></div>
        <h3>{file ? file.name : 'Arrastra tu archivo aquí'}</h3>
        <p>{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB listo para importar` : 'o selecciona una encuesta desde tu computador'}</p>
        <label className="button-secondary" htmlFor="file-input">{file ? 'Cambiar archivo' : 'Seleccionar archivo'}</label>
        {uploadError && <div className="inline-error">{uploadError}</div>}
      </div>
      <div className="upload-form card">
        <div className="card-label">DETALLES DEL ESTUDIO</div>
        <label>Nombre del estudio<input value={name} onChange={(e) => setName(e.target.value)} placeholder="Ej. Seguimiento de marca Q4" /></label>
        {sheets.length > 1 && <label>Hoja de Excel<select value={sheet} onChange={(e) => setSheet(e.target.value)}>{sheets.map((item) => <option key={item}>{item}</option>)}</select></label>}
        <div className="helper-text"><FileSpreadsheet size={14} /> Cada fila debe representar una respuesta.</div>
        <button className="button-primary full-width" disabled={!file || busy || !!uploadError} onClick={() => file && onUpload(file, name, sheet)}>{busy ? <><LoaderCircle className="spin" size={16} /> Importando...</> : <>Importar encuesta <ArrowRight size={16} /></>}</button>
      </div>
    </div>
    {study && <>
      <div className="section-title-row mt-32"><div><h2>Estudio activo</h2><p>Vista previa del archivo y acceso a las herramientas.</p></div><button className="button-text danger" onClick={() => onDelete(study.id)}><Trash2 size={15} /> Eliminar estudio</button></div>
      <div className="metric-grid">
        <MetricCard icon={<UsersRound />} label="Respuestas" value={study.row_count.toLocaleString()} sub="filas de encuesta" color="blue" />
        <MetricCard icon={<Layers3 />} label="Variables" value={study.columns.length} sub="campos detectados" color="mint" />
        <MetricCard icon={<Tags />} label="Preguntas abiertas" value={study.suggested_questions?.length || 0} sub="recomendadas; puedes elegir cualquier columna" color="orange" />
        <MetricCard icon={<BarChart3 />} label="Clasificaciones" value={study.classifications?.length || 0} sub="guardadas en este estudio" color="purple" />
      </div>
      <div className="card preview-card"><div className="card-heading"><div><div className="card-label">MUESTRA DE DATOS</div><h3>{study.name}</h3></div><span className="muted">{study.source_filename}</span></div><DataTable columns={study.columns || []} rows={study.preview || []} /></div>
      <div className="quick-actions"><button className="quick-action" onClick={() => onGo('categorize')}><span className="qa-icon blue"><Tags size={18} /></span><span><b>Categorizar respuestas</b><small>Crear temas o detectar marcas</small></span><ArrowRight size={17} /></button><button className="quick-action" onClick={() => onGo('dashboard')}><span className="qa-icon mint"><BarChart3 size={18} /></span><span><b>Explorar resultados</b><small>Frecuencias, segmentos e insights</small></span><ArrowRight size={17} /></button></div>
    </>}
    {studies.length > 0 && !study && <div className="card muted-card">Selecciona uno de tus estudios en el menú lateral para continuar.</div>}
  </>
}
