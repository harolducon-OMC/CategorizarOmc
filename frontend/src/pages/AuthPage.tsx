import { type FormEvent, useEffect, useRef, useState } from 'react'
import { Activity, BarChart3, Eye, EyeOff, KeyRound, Tags, UploadCloud, Users } from 'lucide-react'
import { api } from '../api'
import '../auth.css'

const PASOS = [
  { icono: KeyRound, titulo: 'Configura tu IA', texto: 'Guarda la API key del proveedor que uses. Se cifra y se reutiliza.' },
  { icono: UploadCloud, titulo: 'Importa tu encuesta', texto: 'Sube un CSV o Excel y queda guardado como estudio.' },
  { icono: Tags, titulo: 'Categoriza respuestas abiertas', texto: 'Clasifica por temas, marcas o sentimiento y corrige etiquetas.' },
  { icono: BarChart3, titulo: 'Explora resultados', texto: 'Frecuencias, cruces por segmento e insights con citas.' },
  { icono: Users, titulo: 'Mide awareness de marca', texto: 'Calcula TOM, espontáneo y ayudado, integrado o con una base aparte.' },
]

export function AuthPage({ onAuthenticated, notice = '' }: { onAuthenticated: (email: string, token: string, info?: { role?: string; must_change_password?: boolean }) => void; notice?: string }) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [passwordActive, setPasswordActive] = useState(false)
  const [error, setError] = useState(notice)
  const [busy, setBusy] = useState(false)
  const eyeLeft = useRef<SVGCircleElement>(null)
  const eyeRight = useRef<SVGCircleElement>(null)

  // Los ojos del robot siguen el cursor mientras no se escribe la contraseña
  useEffect(() => {
    if (passwordActive) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return

    function follow(event: MouseEvent) {
      for (const eye of [eyeLeft.current, eyeRight.current]) {
        if (!eye) continue
        const rect = eye.getBoundingClientRect()
        const cx = rect.left + rect.width / 2
        const cy = rect.top + rect.height / 2
        const angle = Math.atan2(event.clientY - cy, event.clientX - cx)
        const distance = Math.min(3.2, Math.hypot(event.clientX - cx, event.clientY - cy) / 38)
        eye.style.transform = `translate(${Math.cos(angle) * distance}px, ${Math.sin(angle) * distance}px)`
      }
    }

    document.addEventListener('mousemove', follow)
    return () => document.removeEventListener('mousemove', follow)
  }, [passwordActive])

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      const data = await api<{ access_token: string; email: string; role?: string; must_change_password?: boolean }>(`/api/auth/${mode}`, {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      })
      onAuthenticated(data.email, data.access_token, { role: data.role, must_change_password: data.must_change_password })
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="ix-shell">
      <div className="ix-card">
        {/* Panel informativo: explica para qué sirve la plataforma */}
        <aside className="ix-aside" aria-label="Qué hace Insights Studio">
          <span className="ix-glow ix-glow-a" aria-hidden="true" />
          <span className="ix-glow ix-glow-b" aria-hidden="true" />

          <div className="ix-aside-body">
            <div className="ix-brand">
              <span className="ix-brand-mark"><Activity size={20} /></span>
              <div>
                <p className="ix-brand-name">insights</p>
                <p className="ix-brand-sub">STUDIO</p>
              </div>
            </div>

            <h2 className="ix-headline">De la encuesta cruda a los insights.</h2>
            <p className="ix-lead">
              Convierte respuestas abiertas en datos listos para analizar. Este es el camino recomendado:
            </p>

            <ol className="ix-steps">
              {PASOS.map(({ icono: Icono, titulo, texto }, i) => (
                <li key={titulo} className="ix-step">
                  <span className="ix-step-icon"><Icono size={16} /></span>
                  <div>
                    <h3><span className="ix-step-n">{i + 1}</span>{titulo}</h3>
                    <p>{texto}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </aside>

        {/* Formulario */}
        <section className="ix-formwrap" aria-label={mode === 'login' ? 'Inicio de sesión' : 'Crear cuenta'}>
          <form className="ix-form" onSubmit={submit}>
            <div className="ix-robot" aria-hidden="true">
              <svg viewBox="0 0 280 220">
                <defs>
                  <linearGradient id="ixBg" x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0" stopColor="#e8edfc" />
                    <stop offset="1" stopColor="#dfe6f7" />
                  </linearGradient>
                  <linearGradient id="ixBody" x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0" stopColor="#24324f" />
                    <stop offset="1" stopColor="#16213a" />
                  </linearGradient>
                </defs>
                <ellipse cx="140" cy="207" rx="70" ry="8" fill="#14213d" opacity="0.12" />
                <circle cx="140" cy="110" r="91" fill="url(#ixBg)" />
                {/* Antena */}
                <path d="M140 30v17M140 30l-7-9M140 30l7-9" fill="none" stroke="#8a96b0" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
                <circle cx="140" cy="19" r="5" fill="#2f5adf" />
                {/* Pantalla */}
                <rect x="78" y="48" width="124" height="138" rx="25" fill="url(#ixBody)" />
                <rect x="91" y="64" width="98" height="96" rx="15" fill="#0e1628" />
                <rect x="128" y="53" width="24" height="5" rx="2.5" fill="#3a4a6b" />
                {/* Ojos */}
                {passwordActive ? (
                  <g fill="none" stroke="#8fa6f5" strokeWidth="3.5" strokeLinecap="round">
                    <path d="M111 98c5 -5 13 -5 18 0" />
                    <path d="M151 98c5 -5 13 -5 18 0" />
                  </g>
                ) : (
                  <>
                    <circle ref={eyeLeft} cx="120" cy="96" r="9" fill="#8fa6f5" style={{ transition: 'transform 80ms linear' }} />
                    <circle ref={eyeRight} cx="160" cy="96" r="9" fill="#8fa6f5" style={{ transition: 'transform 80ms linear' }} />
                    <circle cx="123" cy="93" r="2.5" fill="#fff" opacity="0.85" />
                    <circle cx="163" cy="93" r="2.5" fill="#fff" opacity="0.85" />
                  </>
                )}
                {/* Boca */}
                <path d={passwordActive ? 'M126 122c8 3 20 3 28 0' : 'M120 120c12 9 28 9 40 0'} fill="none" stroke="#2fbf8a" strokeWidth="3.5" strokeLinecap="round" />
                {/* Mini gráfico: el robot "lee" resultados */}
                <g fill="#5b7cf0">
                  <rect x="108" y="142" width="9" height="10" rx="2" opacity="0.7" />
                  <rect x="122" y="136" width="9" height="16" rx="2" opacity="0.85" />
                  <rect x="136" y="130" width="9" height="22" rx="2" />
                  <rect x="150" y="138" width="9" height="14" rx="2" opacity="0.8" />
                  <rect x="164" y="133" width="9" height="19" rx="2" opacity="0.9" />
                </g>
                <rect x="116" y="174" width="48" height="6" rx="3" fill="#8fa6f5" opacity="0.9" />
                {/* Brazos */}
                <path d="M82 169c-23 3-31 15-37 30" fill="none" stroke="#24324f" strokeWidth="9" strokeLinecap="round" />
                <path d="M198 169c23 3 31 15 37 30" fill="none" stroke="#24324f" strokeWidth="9" strokeLinecap="round" />
                <path d="M55 195l-10 5M225 195l10 5" stroke="#5b7cf0" strokeWidth="4" strokeLinecap="round" />
              </svg>
            </div>

            <div className="ix-title">
              <h1>{mode === 'login' ? 'Bienvenido a Insights Studio' : 'Crea tu cuenta en Insights Studio'}</h1>
              <p>
                {mode === 'login'
                  ? 'Inicia sesión con tu cuenta corporativa para analizar tus encuestas.'
                  : 'Registra tu correo autorizado @omc para empezar.'}
              </p>
            </div>

            <div className="ix-fields">
              <label className="ix-label" htmlFor="ix-email">Correo corporativo</label>
              <input
                id="ix-email"
                className="ix-input"
                type="text"
                inputMode="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="corre@omc"
              />

              <label className="ix-label" htmlFor="ix-password">Contraseña</label>
              <div className="ix-pass">
                <input
                  id="ix-password"
                  className="ix-input"
                  type={showPassword ? 'text' : 'password'}
                  required
                  minLength={12}
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onFocus={() => setPasswordActive(true)}
                  onBlur={() => setPasswordActive(false)}
                  placeholder="Mínimo 12 caracteres"
                />
                <button
                  type="button"
                  className="ix-eye"
                  // evita que el input pierda el foco al pulsar el ojo
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {error && <p role="alert" className="ix-error">{error}</p>}

            <button className="ix-submit" disabled={busy}>
              {busy ? 'Procesando…' : mode === 'login' ? 'Iniciar sesión' : 'Crear cuenta'}
            </button>
            <button
              type="button"
              className="ix-switch"
              onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}
            >
              {mode === 'login' ? '¿Primera vez? Crear cuenta' : '¿Ya tienes cuenta? Iniciar sesión'}
            </button>

            <small className="ix-note">
              Acceso protegido con token de sesión. El registro requiere el dominio corporativo permitido.
            </small>
          </form>
        </section>
      </div>
    </main>
  )
}
