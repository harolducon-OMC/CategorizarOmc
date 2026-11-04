import { FormEvent, useEffect, useRef, useState } from 'react'
import { ArrowRight, LoaderCircle, Send, Settings2, X } from 'lucide-react'
import './HelpAssistant.css'

type Message = { role: 'user' | 'assistant'; content: string }

const STARTER: Message = {
  role: 'assistant',
  content: '¡Hola! 👋 Soy Insy, tu asistente de Insights Studio. Puedo explicarte categorización, claves de IA, Awareness, edición e insights. ¿Por dónde empezamos?',
}

const SUGGESTIONS = [
  '¿Cómo se categorizan las marcas?',
  '¿Dónde guardo o cambio mi API key?',
  '¿Qué diferencia hay entre los dos Awareness?',
]

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
  onOpenSettings,
}: {
  provider: string
  model: string
  apiKey: string
  onOpenSettings: () => void
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

  async function sendQuestion(question: string) {
    const content = question.trim()
    if (!content || busy) return
    const next = [...messages, { role: 'user' as const, content }]
    setMessages(next)
    setDraft('')
    setBusy(true)
    setNeedsKey(false)
    try {
      const token = sessionStorage.getItem('insights-token')
      const headers = new Headers({ 'Content-Type': 'application/json' })
      if (token) headers.set('Authorization', `Bearer ${token}`)
      if (apiKey) headers.set('X-LLM-API-Key', apiKey)
      const response = await fetch('/api/help/chat', {
        method: 'POST',
        headers,
        body: JSON.stringify({ provider, model, messages: next.slice(-12) }),
      })
      const payload = await response.json().catch(() => ({ detail: response.statusText }))
      if (!response.ok) {
        const detail = typeof payload.detail === 'string' ? payload.detail : 'No se pudo consultar el asistente.'
        if (/API key|clave/i.test(detail)) setNeedsKey(true)
        throw new Error(detail)
      }
      setMessages([...next, { role: 'assistant', content: payload.answer }])
    } catch (error) {
      setMessages((current) => [...current, {
        role: 'assistant',
        content: `No pude responder ahora. ${(error as Error).message}`,
      }])
    } finally {
      setBusy(false)
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    void sendQuestion(draft)
  }

  return (
    <div className="help-assistant-root">
      {open && (
        <section className="help-chat-panel" aria-label="Asistente de ayuda">
          <header className="help-chat-header">
            <span className="help-chat-mark"><Robot size={28} /></span>
            <div><b>Insy · Asistente de Insights</b><small>Guía de la plataforma · {provider}</small></div>
            <button type="button" className="help-chat-close" onClick={() => setOpen(false)} aria-label="Cerrar asistente"><X size={17} /></button>
          </header>
          <div className="help-chat-messages" aria-live="polite">
            {messages.map((message, index) => (
              <div key={`${index}-${message.role}`} className={`help-chat-message ${message.role}`}>
                <span>{message.content}</span>
                {message.role === 'assistant' && needsKey && index === messages.length - 1 && (
                  <button className="help-chat-settings-link" type="button" onClick={onOpenSettings}>
                    <Settings2 size={14} /> Abrir Ajustes <ArrowRight size={13} />
                  </button>
                )}
              </div>
            ))}
            {messages.length === 1 && !busy && (
              <div className="help-chat-suggestions">
                {SUGGESTIONS.map((question) => (
                  <button key={question} type="button" onClick={() => void sendQuestion(question)}>{question}</button>
                ))}
              </div>
            )}
            {busy && <div className="help-chat-thinking"><LoaderCircle className="spin" size={14} /> Preparando respuesta…</div>}
            <div ref={bottomRef} />
          </div>
          <form className="help-chat-composer" onSubmit={submit}>
            <textarea
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Pregunta sobre una parte de la plataforma…"
              maxLength={2000}
              rows={2}
              aria-label="Pregunta para el asistente"
            />
            <button type="submit" disabled={busy || !draft.trim()} aria-label="Enviar pregunta">
              {busy ? <LoaderCircle className="spin" size={17} /> : <Send size={16} />}
            </button>
          </form>
          <div className="help-chat-footnote">Usa el proveedor/modelo seleccionado. No compartas claves ni datos sensibles.</div>
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
