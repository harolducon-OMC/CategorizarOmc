import { useEffect } from 'react'
import { ArrowRight, BarChart3, Check, KeyRound, Tags, UploadCloud, UsersRound, X } from 'lucide-react'

type Target = 'home' | 'categorize' | 'dashboard' | 'awareness' | 'settings'

/** Guía rápida del flujo de trabajo: qué hace cada sección y a dónde ir después. */
export default function FlowGuide({ hasStudy, onClose, onGo }: { hasStudy: boolean; onClose: () => void; onGo: (page: Target) => void }) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const steps: { icon: JSX.Element; title: string; text: string; page: Target; action: string; done?: boolean }[] = [
    { icon: <KeyRound size={17} />, title: 'Configura tu IA', text: 'En Ajustes guarda la API key del proveedor que vayas a usar (Gemini, Groq, Cohere, OpenRouter o Anthropic). Se cifra y se reutiliza automáticamente.', page: 'settings', action: 'Ir a Ajustes' },
    { icon: <UploadCloud size={17} />, title: 'Importa tu encuesta', text: 'Sube un CSV o Excel (hasta 25 MB). Queda guardado como estudio y puedes volver a él cuando quieras.', page: 'home', action: 'Importar en Inicio', done: hasStudy },
    { icon: <Tags size={17} />, title: 'Categoriza respuestas abiertas', text: 'Elige las preguntas, clasifica por temas, marcas o sentimiento, revisa el catálogo y corrige etiquetas. Al terminar se descarga un Excel consolidado.', page: 'categorize', action: 'Ir a Categorización' },
    { icon: <BarChart3 size={17} />, title: 'Explora resultados', text: 'Frecuencias, cruces por segmento e insights con citas de las respuestas. También puedes exportar el reporte en Excel.', page: 'dashboard', action: 'Ir al Dashboard' },
    { icon: <UsersRound size={17} />, title: 'Mide Awareness de marca', text: 'Calcula TOM, espontáneo y ayudado. Tienes dos opciones: integrado, con las marcas ya categorizadas; o independiente, cargando directamente un CSV/Excel.', page: 'awareness', action: 'Ir a Awareness' },
  ]

  return (
    <div className="flow-guide-overlay" onClick={onClose} role="presentation">
      <div className="flow-guide card" role="dialog" aria-modal="true" aria-labelledby="flow-guide-title" onClick={(e) => e.stopPropagation()}>
        <div className="flow-guide-head">
          <div>
            <div className="card-label">CÓMO FUNCIONA</div>
            <h3 id="flow-guide-title">De la encuesta cruda a los insights</h3>
            <p>Insights Studio convierte respuestas abiertas en datos listos para analizar. Este es el camino recomendado:</p>
          </div>
          <button className="tiny-icon" onClick={onClose} aria-label="Cerrar guía"><X size={16} /></button>
        </div>
        <ol className="flow-guide-steps">
          {steps.map((step, index) => (
            <li key={step.title}>
              <span className={`flow-guide-num ${step.done ? 'done' : ''}`}>{step.done ? <Check size={13} /> : index + 1}</span>
              <div>
                <b>{step.icon} {step.title}</b>
                <p>{step.text}</p>
              </div>
              <button className="button-secondary" onClick={() => { onGo(step.page); onClose() }}>{step.action} <ArrowRight size={14} /></button>
            </li>
          ))}
        </ol>
        <div className="info-callout"><Check size={16} /><span>Awareness independiente no necesita estudio: si solo quieres calcular recordación de una base, entra directo a esa pestaña.</span></div>
      </div>
    </div>
  )
}
