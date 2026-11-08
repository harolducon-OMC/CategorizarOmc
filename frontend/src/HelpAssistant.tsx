import { FormEvent, useEffect, useRef, useState } from 'react'
import { ArrowRight, LoaderCircle, Send, Settings2, Sparkles, X } from 'lucide-react'
import { api } from './api'
import type { Page } from './types'
import './HelpAssistant.css'

type Action = { label: string; page: Page }
type Message = {
  role: 'user' | 'assistant'
  content: string
  actions?: Action[]
  related?: { id: string; title: string }[]
  askAi?: string          // pregunta que se puede enviar a la IA si la guía no tuvo respuesta
  source?: 'guia' | 'ia'
}
type GuideAnswer = {
  confident: boolean; answer: string; title?: string; actions: Action[]; related: { id: string; title: string }[]
}

const STARTER: Message = {
  role: 'assistant',
  content: '¡Hola! 👋 Soy Insy. Respondo con la guía de la plataforma: es instantáneo y no envía tus datos a ningún proveedor. ¿En qué te ayudo?',
}

const SUGGESTIONS: Record<Page, string[]> = {
  home: ['¿Cómo importo mi encuesta?', '¿Qué son las preguntas abiertas recomendadas?', '¿Cómo elimino un estudio?'],
  categorize: ['¿Cómo categorizo por temas?', '¿Qué significa «Otros» y «Ninguna»?', '¿Para qué sirven los diccionarios?'],
  dashboard: ['¿Cómo corrijo etiquetas?', '¿Cómo mido la calidad de la categorización?', '¿Cómo se generan los insights?'],
  awareness: ['¿Qué diferencia hay entre TOM, espontáneo y ayudado?', '¿Awareness usa lo que categoricé?', '¿Cómo escribo los códigos de pregunta?'],
  settings: ['¿Dónde guardo mi API key?', '¿Qué proveedor de IA elijo?', '¿Cómo protegen mis datos?'],
  admin: ['¿Qué puede hacer cada rol?', '¿Cómo restablezco la contraseña de alguien?', '¿Qué políticas de seguridad puedo configurar?'],
}

/** Siguiente paso recomendado según el estado real del estudio (sin IA). */
function nextStep(study: any): { text: string; action: Action } {
  if (!study?.id) return { text: 'Importa tu encuesta para empezar.', action: { label: 'Ir a Inicio', page: 'home' } }
  const classifications: { kind: string }[] = study.classifications || []
  const open = study.suggested_questions?.length || 0
  if (!classifications.length) {
    return {
      text: open ? `Detecté ${open} preguntas abiertas. Categoriza la primera.` : 'Elige una pregunta abierta y categorízala.',
      action: { label: 'Ir a Categorización', page: 'categorize' },
    }
  }
  if (classifications.some((item) => item.kind === 'brands')) {
    return { text: 'Ya tienes marcas categorizadas: calcula el Awareness.', action: { label: 'Ir a Awareness', page: 'awareness' } }
  }
  return { text: 'Revisa resultados y mide la calidad de la categorización.', action: { label: 'Ir al Dashboard', page: 'dashboard' } }
}

function Robot({ size = 40 }: { size?: number }) {
  return (
    <svg className="robot" width={size} height={size} viewBox="0 0 64 64" aria-hidden="true">
      <line x1="32" y1="8" x2="32" y2="14" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" />
      <circle className="robot-antenna" cx="32" cy="6" r="3.4" fill="#5eead4" />
      <rect x="4" y="27" width="6" height="12" rx="3" fill="#cfd9f5" />
      <rect x="54" y="27" width="6" height="12" rx="3" fill="#cfd9f5" />
      <rect x="10" y="14" width="44" height="34" rx="12" fill="#fff" />
      <rect x="15" y="19" width="34" height="24" rx="8" fill="#273751" />
      <ellipse className="robot-eye" cx="25" cy="29" rx="3.4" ry="4.2" fill="#6d94ff" />
      <ellipse className="robot-eye" cx="39" cy="29" rx="3.4" ry="4.2" fill="#6d94ff" />
      <path d="M27 37 q5 4 10 0" stroke="#6d94ff" strokeWidth="2.2" fill="none" strokeLinecap="round" />
      <rect x="21" y="50" width="22" height="9" rx="4.5" fill="#fff" />
    </svg>
  )
}

export default function HelpAssistant({
  provider,
  model,
  apiKey,
  page,
  study,
  onOpenSettings,
  onNavigate,
}: {
  provider: string
  model: string
  apiKey: string
  page: Page
  study: any
  onOpenSettings: () => void
  onNavigate: (page: Page) => void
}) {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<Message[]>([STARTER])
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [needsKey, setNeedsKey] = useState(false)
  const [greet, setGreet] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  // Importante: con llaves para que el efecto NO devuelva nada (evita "u is not a function")
  useEffect(() => {
    if (open) bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, busy, open])

  // Saludo del robot: una sola vez por sesión
  useEffect(() => {
    let seen = false
    try { seen = !!sessionStorage.getItem('help-greeted') } catch { /* ignorar */ }
    if (seen) return
    const show = window.setTimeout(() => {
      setGreet(true)
      try { sessionStorage.setItem('help-greeted', '1') } catch { /* ignorar */ }
    }, 1500)
    const hide = window.setTimeout(() => setGreet(false), 10000)
    return () => {
      window.clearTimeout(show)
      window.clearTimeout(hide)
    }
  }, [])

  const setLast = (message: Message) => setMessages((current) => {
    const copy = current.slice()
    copy[copy.length - 1] = message
    return copy
  })

  /** 1) Guía propia: gratis, instantánea y sin enviar datos a terceros. */
  async function ask(question: string, article?: string) {
    const content = question.trim()
    if ((!content && !article) || busy) return
    setMessages((current) => [...current, { role: 'user', content: content || 'Ver también' }, { role: 'assistant', content: '' }])
    setDraft('')
    setBusy(true)
    setNeedsKey(false)
    try {
      const answer = await api<GuideAnswer>('/api/help/ask', {
        method: 'POST',
        body: JSON.stringify(article ? { article } : { question: content, page }),
      })
      if (answer.confident) {
        setLast({ role: 'assistant', content: answer.answer, actions: answer.actions, related: answer.related, source: 'guia' })
      } else {
        setLast({
          role: 'assistant',
          content: 'No encontré eso en la guía de la plataforma. Puedes reformular la pregunta o, si quieres, preguntarle a la IA.',
          related: answer.related, askAi: content,
        })
      }
    } catch (error) {
      setLast({ role: 'assistant', content: `No pude consultar la guía ahora. ${(error as Error).message}`, askAi: content })
    } finally {
      setBusy(false)
    }
  }

  /** 2) IA opcional: solo cuando la persona lo pide de forma explícita. */
  async function askAi(question: string) {
    if (busy) return
    setMessages((current) => {
      const copy = current.map((message) => message.askAi === question ? { ...message, askAi: undefined } : message)
      return [...copy, { role: 'assistant', content: '', source: 'ia' }]
    })
    setBusy(true)
    setNeedsKey(false)
    const history = messages.filter((message) => message.content).slice(-11).map(({ role, content }) => ({ role, content }))
    try {
      const token = sessionStorage.getItem('insights-token')
      const headers = new Headers({ 'Content-Type': 'application/json' })
      if (token) headers.set('Authorization', `Bearer ${token}`)
      if (apiKey) headers.set('X-LLM-API-Key', apiKey)
      const response = await fetch('/api/help/chat/stream', {
        method: 'POST',
        headers,
        body: JSON.stringify({ provider, model, messages: [...history, { role: 'user', content: question }].slice(-12) }),
      })
      if (!response.ok || !response.body) {
        const payload = await response.json().catch(() => ({ detail: response.statusText }))
        throw new Error(typeof payload.detail === 'string' ? payload.detail : 'No se pudo consultar a la IA.')
      }
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let text = ''
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const events = buffer.split('\n\n')
        buffer = events.pop() || ''
        for (const raw of events) {
          const line = raw.trim()
          if (!line.startsWith('data:')) continue
          const event = JSON.parse(line.slice(5).trim())
          if (event.error) throw new Error(event.error)
          if (event.delta) { text += event.delta; setLast({ role: 'assistant', content: text, source: 'ia' }) }
        }
      }
      if (!text) setLast({ role: 'assistant', content: 'No pude preparar una respuesta. Intenta reformular la pregunta.', source: 'ia' })
    } catch (error) {
      const detail = (error as Error).message
      if (/API key|clave/i.test(detail)) setNeedsKey(true)
      setLast({ role: 'assistant', content: `No pude responder con la IA. ${detail}`, source: 'ia' })
    } finally {
      setBusy(false)
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    void ask(draft)
  }

  function go(target: Page) {
    onNavigate(target)
    setOpen(false)
  }

  const step = nextStep(study)
  const lastMessage = messages[messages.length - 1]

  return (
    <div className="help-assistant-root">
      {open && (
        <section className="help-chat-panel" aria-label="Asistente de ayuda">
          <header className="help-chat-header">
            <span className="help-chat-mark"><Robot size={28} /></span>
            <div><b>Insy · Asistente de Insights</b><small>Guía de la plataforma · sin IA por defecto</small></div>
            <button type="button" className="help-chat-close" onClick={() => setOpen(false)} aria-label="Cerrar asistente"><X size={17} /></button>
          </header>
          <div className="help-chat-messages" aria-live="polite">
            {messages.map((message, index) => !message.content ? null : (
              <div key={`${index}-${message.role}`} className={`help-chat-message ${message.role}`}>
                <span>{message.content}</span>
                {message.role === 'assistant' && message.source && (
                  <small className="help-chat-source">{message.source === 'guia' ? 'Guía de la plataforma' : `Respuesta de la IA · ${provider}`}</small>
                )}
                {message.actions?.map((action) => (
                  <button key={action.label} className="help-chat-action" type="button" onClick={() => go(action.page)}>
                    {action.label} <ArrowRight size={13} />
                  </button>
                ))}
                {message.askAi && (
                  <button
                    className="help-chat-ai-button" type="button" disabled={busy} onClick={() => void askAi(message.askAi as string)}
                    title={`Se enviará solo tu pregunta al proveedor ${provider}. Se ocultan correos y teléfonos.`}
                  >
                    <Sparkles size={13} /> Preguntar a la IA
                  </button>
                )}
                {message.related && message.related.length > 0 && (
                  <div className="help-chat-related">
                    <small>Ver también</small>
                    {message.related.map((item) => (
                      <button key={item.id} type="button" disabled={busy} onClick={() => void ask(item.title, item.id)}>{item.title}</button>
                    ))}
                  </div>
                )}
                {message.role === 'assistant' && needsKey && index === messages.length - 1 && (
                  <button className="help-chat-settings-link" type="button" onClick={onOpenSettings}>
                    <Settings2 size={14} /> Abrir Ajustes <ArrowRight size={13} />
                  </button>
                )}
              </div>
            ))}
            {messages.length === 1 && !busy && (
              <>
                <div className="help-chat-nextstep">
                  <small>SIGUIENTE PASO RECOMENDADO</small>
                  <span>{step.text}</span>
                  <button type="button" onClick={() => go(step.action.page)}>{step.action.label} <ArrowRight size={13} /></button>
                </div>
                <div className="help-chat-suggestions">
                  {SUGGESTIONS[page].map((question) => (
                    <button key={question} type="button" onClick={() => void ask(question)}>{question}</button>
                  ))}
                </div>
              </>
            )}
            {busy && !lastMessage?.content && <div className="help-chat-thinking"><LoaderCircle className="spin" size={14} /> {lastMessage?.source === 'ia' ? 'Consultando a la IA…' : 'Buscando en la guía…'}</div>}
            <div ref={bottomRef} />
          </div>
          <form className="help-chat-composer" onSubmit={submit}>
            <textarea
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void ask(draft) } }}
              placeholder="Pregunta sobre una parte de la plataforma…"
              maxLength={500}
              rows={2}
              aria-label="Pregunta para el asistente"
            />
            <button type="submit" disabled={busy || !draft.trim()} aria-label="Enviar pregunta">
              {busy ? <LoaderCircle className="spin" size={17} /> : <Send size={16} />}
            </button>
          </form>
          <div className="help-chat-footnote">La IA solo se usa si pulsas «Preguntar a la IA». No compartas claves ni datos sensibles.</div>
        </section>
      )}

      {greet && !open && (
        <div className="help-greeting" role="status">
          <button type="button" className="help-greeting-close" onClick={() => setGreet(false)} aria-label="Cerrar saludo">×</button>
          <b>¡Hola! 👋 Soy Insy</b>
          <span>Tu asistente de Insights Studio. ¿Te ayudo con algo?</span>
        </div>
      )}

      <button
        type="button"
        translate="no"
        className={`help-assistant-toggle ${open ? 'open' : ''}`}
        onClick={() => { setGreet(false); setOpen((value) => !value) }}
        aria-expanded={open}
        aria-label={open ? 'Cerrar asistente de ayuda' : 'Abrir asistente de ayuda'}
        title="Pregúntale a Insy"
      >
        <Robot size={40} />
        <X className="ico-close" size={22} />
      </button>
    </div>
  )
}
