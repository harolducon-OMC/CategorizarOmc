import { FormEvent, useEffect, useRef, useState } from 'react'
import { ArrowRight, Bot, LoaderCircle, MessageCircle, Send, Settings2, X } from 'lucide-react'
import './HelpAssistant.css'

type Message = { role: 'user' | 'assistant'; content: string }

const STARTER: Message = {
  role: 'assistant',
  content: 'Puedo explicarte cómo usar Insights Studio: categorización, claves de IA, Awareness, edición e insights. ¿Por dónde empezamos?',
}

const SUGGESTIONS = [
  '¿Cómo se categorizan las marcas?',
  '¿Dónde guardo o cambio mi API key?',
  '¿Qué diferencia hay entre los dos Awareness?',
]

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
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
  if (open) bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
}, [messages, busy, open])

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
            <span className="help-chat-mark"><Bot size={18} /></span>
            <div><b>Asistente de Insights</b><small>Guía de la plataforma · {provider}</small></div>
            <button type="button" className="help-chat-close" onClick={() => setOpen(false)} aria-label="Cerrar asistente"><X size={17} /></button>
          </header>
          <div className="help-chat-messages" aria-live="polite">
            {messages.map((message, index) => (
              <div key={`${index}-${message.role}`} className={`help-chat-message ${message.role}`}>
                {message.content}
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
      <button
        type="button"
        className={`help-assistant-toggle ${open ? 'open' : ''}`}
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-label={open ? 'Cerrar asistente de ayuda' : 'Abrir asistente de ayuda'}
      >
        {open ? <X size={19} /> : <><MessageCircle size={19} /><span>Ayuda</span></>}
      </button>
    </div>
  )
}
