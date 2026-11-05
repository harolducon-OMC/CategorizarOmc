import { useState } from 'react'
import { PageHeading } from '../components/common'
import { AwarenessPage } from '../pages/AwarenessIntegrated'
import AwarenessStandalone from '../AwarenessStandalone'

export function AwarenessHub({ study, onNotice }: any) {
  // Dos formas de usar Awareness, sin iframes ni servicios aparte:
  //  - Integrado: toma marcas y alias de las clasificaciones del estudio activo.
  //  - Independiente: carga un CSV/XLSX propio y genera el Excel de resultados.
  const [tab, setTab] = useState<'flow' | 'standalone'>(() => (sessionStorage.getItem('awareness-tab') as 'flow' | 'standalone') || 'flow')
  const choose = (next: 'flow' | 'standalone') => { setTab(next); sessionStorage.setItem('awareness-tab', next) }
  return <>
    <div className="segmented awa-tabs">
      <button className={tab === 'flow' ? 'selected' : ''} onClick={() => choose('flow')}>Integrado al flujo de categorización</button>
      <button className={tab === 'standalone' ? 'selected' : ''} onClick={() => choose('standalone')}>Independiente · CSV / Excel</button>
    </div>
    {tab === 'flow'
      ? <AwarenessPage study={study} onNotice={onNotice} />
      : <>
          <PageHeading eyebrow="RECORDACIÓN DE MARCA" title="Awareness independiente" text="Carga una base CSV o Excel, configura marcas y columnas, y descarga el reporte. No requiere crear un estudio ni ejecutar el flujo de categorización." />
          <AwarenessStandalone onNotice={onNotice} />
        </>}
  </>
}
