import { Component } from 'react'
import type { ErrorInfo, ReactNode } from 'react'

type Props = { children: ReactNode }
type State = { error: Error | null }

/** Red de seguridad: si un componente falla, muestra un aviso en lugar de dejar la pantalla en blanco. */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Error de la aplicación:', error, info.componentStack)
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div role="alert" style={{ maxWidth: 520, margin: '12vh auto', padding: 28, fontFamily: 'system-ui, sans-serif', textAlign: 'center' }}>
        <h2 style={{ margin: '0 0 8px' }}>Algo salió mal</h2>
        <p style={{ color: '#5d6980', lineHeight: 1.5 }}>
          La pantalla tuvo un error inesperado. Tus datos guardados no se perdieron. Recarga la página para continuar;
          si se repite, cuéntanos qué estabas haciendo.
        </p>
        <pre style={{ textAlign: 'left', whiteSpace: 'pre-wrap', background: '#f3f6fb', padding: 12, borderRadius: 8, fontSize: 12, color: '#354258' }}>
          {this.state.error.message}
        </pre>
        <button onClick={() => window.location.reload()} style={{ padding: '9px 18px', border: 0, borderRadius: 8, background: '#315bdb', color: '#fff', fontWeight: 700, cursor: 'pointer' }}>
          Recargar
        </button>
      </div>
    )
  }
}
