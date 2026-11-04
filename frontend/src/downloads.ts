/**
 * Descargas de Awareness como imagen PNG.
 * El gráfico y la tabla se dibujan directamente en un canvas (no se copia el DOM),
 * así el resultado siempre sale nítido, con etiquetas y con el mismo estilo.
 */

export type AwarenessImageRow = {
  name: string
  tom: number
  esp: number
  ayu: number
  awa: number
}

type ImageOptions = {
  title: string
  subtitle?: string
  filename: string
}

const FONT = "'DM Sans','Manrope','Segoe UI',Arial,sans-serif"
const SCALE = 2
const C = {
  tom: '#315bdb',
  esp: '#18a994',
  ayu: '#ef9b46',
  ink: '#172235',
  text: '#3a465c',
  muted: '#7f8a9c',
  grid: '#e6eaf0',
  band: '#f6f8fb',
  line: '#e1e6ee',
  navy: '#182337',
  tint: '#eef2ff',
}

const pct = (value: number) => `${(value * 100).toFixed(1)}%`

/** Convierte las filas del backend (Entidad, 'TOM %', ...) en filas ordenadas por AWA. */
export function toAwarenessImageRows(rows: any[]): AwarenessImageRow[] {
  return rows
    .map((row) => ({
      name: String(row.Entidad ?? ''),
      tom: Number(row['TOM %']) || 0,
      esp: Number(row['Espontaneo %']) || 0,
      ayu: Number(row['Ayudado %']) || 0,
      awa: Number(row['AWA %']) || 0,
    }))
    .sort((a, b) => (b.awa - a.awa) || a.name.localeCompare(b.name, 'es'))
}

function roundRectPath(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  const radius = Math.max(0, Math.min(r, w / 2, h / 2))
  ctx.beginPath()
  ctx.moveTo(x + radius, y)
  ctx.arcTo(x + w, y, x + w, y + h, radius)
  ctx.arcTo(x + w, y + h, x, y + h, radius)
  ctx.arcTo(x, y + h, x, y, radius)
  ctx.arcTo(x, y, x + w, y, radius)
  ctx.closePath()
}

function fitText(ctx: CanvasRenderingContext2D, text: string, maxWidth: number) {
  if (ctx.measureText(text).width <= maxWidth) return text
  let current = text
  while (current.length > 1 && ctx.measureText(`${current}…`).width > maxWidth) current = current.slice(0, -1)
  return `${current.trimEnd()}…`
}

function measureLabels(rows: AwarenessImageRow[], font: string) {
  const probe = document.createElement('canvas').getContext('2d')
  if (!probe) return 160
  probe.font = font
  return Math.max(...rows.map((row) => probe.measureText(row.name).width), 60)
}

async function createCanvas(width: number, height: number) {
  try { await document.fonts?.ready } catch { /* si falla, se usa la fuente de respaldo */ }
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(width * SCALE)
  canvas.height = Math.round(height * SCALE)
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('El navegador no pudo preparar la imagen.')
  ctx.scale(SCALE, SCALE)
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, width, height)
  ctx.textBaseline = 'middle'
  return { canvas, ctx }
}

function drawHeader(ctx: CanvasRenderingContext2D, options: ImageOptions) {
  ctx.textAlign = 'left'
  ctx.fillStyle = C.ink
  ctx.font = `700 22px ${FONT}`
  ctx.fillText(options.title, 40, 38)
  if (options.subtitle) {
    ctx.fillStyle = C.muted
    ctx.font = `400 13px ${FONT}`
    ctx.fillText(options.subtitle, 40, 64)
  }
}

function drawFooter(ctx: CanvasRenderingContext2D, width: number, height: number) {
  ctx.fillStyle = C.muted
  ctx.font = `400 11px ${FONT}`
  ctx.textAlign = 'left'
  ctx.fillText('Insights Studio · OMC', 40, height - 24)
  ctx.textAlign = 'right'
  ctx.fillText(new Date().toLocaleDateString('es-CO', { day: '2-digit', month: 'long', year: 'numeric' }), width - 40, height - 24)
}

async function savePng(canvas: HTMLCanvasElement, filename: string) {
  const blob = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((result) => {
      if (result) resolve(result)
      else reject(new Error('No se pudo crear la imagen.'))
    }, 'image/png')
  })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

/** Gráfico de barras apiladas (TOM + Espontáneo + Ayudado) con etiquetas de marca y de valor. */
export async function downloadAwarenessChartImage(rows: AwarenessImageRow[], options: ImageOptions) {
  if (!rows.length) throw new Error('No hay marcas para graficar.')

  const width = 1200
  const left = Math.min(300, Math.max(150, Math.ceil(measureLabels(rows, `600 13px ${FONT}`)) + 44))
  const right = 84
  const top = 118
  const rowH = 42
  const barH = 24
  const bottom = 64
  const height = top + rows.length * rowH + bottom
  const plotW = width - left - right

  const maxAwa = Math.max(...rows.map((row) => row.awa), 0.05)
  const step = maxAwa <= 0.3 ? 0.05 : maxAwa <= 0.6 ? 0.1 : 0.2
  const axisMax = Math.min(1, Math.max(step * 2, Math.ceil(maxAwa / step - 1e-9) * step))
  const xAt = (value: number) => left + (value / axisMax) * plotW
  const plotBottom = top + rows.length * rowH

  const { canvas, ctx } = await createCanvas(width, height)
  drawHeader(ctx, options)

  // Leyenda
  const legend: Array<[string, string]> = [['TOM', C.tom], ['Espontáneo', C.esp], ['Ayudado', C.ayu]]
  let legendX = 40
  ctx.font = `500 12px ${FONT}`
  ctx.textAlign = 'left'
  for (const [label, color] of legend) {
    ctx.fillStyle = color
    roundRectPath(ctx, legendX, 86, 12, 12, 3)
    ctx.fill()
    ctx.fillStyle = C.text
    ctx.fillText(label, legendX + 19, 92.5)
    legendX += 19 + ctx.measureText(label).width + 24
  }
  ctx.fillStyle = C.muted
  ctx.font = `400 12px ${FONT}`
  ctx.textAlign = 'right'
  ctx.fillText('Total de la barra = AWA', width - 40, 92.5)

  // Franjas alternas
  rows.forEach((_, index) => {
    if (index % 2 !== 0) return
    ctx.fillStyle = C.band
    roundRectPath(ctx, 24, top + index * rowH, width - 48, rowH, 6)
    ctx.fill()
  })

  // Rejilla y eje
  ctx.font = `400 11px ${FONT}`
  ctx.textAlign = 'center'
  for (let k = 0; k * step <= axisMax + 1e-9; k += 1) {
    const value = k * step
    const x = xAt(value)
    ctx.strokeStyle = k === 0 ? '#b9c2d0' : C.grid
    ctx.lineWidth = 1
    ctx.beginPath()
    ctx.moveTo(x, top - 4)
    ctx.lineTo(x, plotBottom)
    ctx.stroke()
    ctx.fillStyle = C.muted
    ctx.fillText(`${Math.round(value * 100)}%`, x, plotBottom + 16)
  }

  // Barras y etiquetas
  rows.forEach((row, index) => {
    const cy = top + index * rowH + rowH / 2
    const barY = cy - barH / 2

    ctx.fillStyle = C.ink
    ctx.font = `600 13px ${FONT}`
    ctx.textAlign = 'right'
    ctx.fillText(fitText(ctx, row.name, left - 42), left - 14, cy)

    const segments: Array<[number, string]> = [[row.tom, C.tom], [row.esp, C.esp], [row.ayu, C.ayu]]
    const total = row.tom + row.esp + row.ayu
    const totalW = (total / axisMax) * plotW
    if (totalW > 0) {
      ctx.save()
      roundRectPath(ctx, left, barY, Math.max(totalW, 2), barH, 6)
      ctx.clip()
      let cursor = left
      segments.forEach(([value, color], segmentIndex) => {
        const segmentW = (value / axisMax) * plotW
        if (segmentW <= 0) return
        ctx.fillStyle = color
        ctx.fillRect(cursor, barY, segmentW, barH)
        if (segmentIndex < segments.length - 1) {
          ctx.fillStyle = '#ffffff'
          ctx.fillRect(cursor + segmentW - 0.5, barY, 1, barH)
        }
        cursor += segmentW
      })
      ctx.restore()

      // Etiqueta dentro de cada tramo, solo si cabe
      let labelCursor = left
      ctx.font = `600 11px ${FONT}`
      ctx.textAlign = 'center'
      ctx.fillStyle = '#ffffff'
      segments.forEach(([value]) => {
        const segmentW = (value / axisMax) * plotW
        if (segmentW >= 40) ctx.fillText(pct(value), labelCursor + segmentW / 2, cy)
        labelCursor += segmentW
      })
    }

    // Total AWA al final de la barra
    ctx.fillStyle = C.ink
    ctx.font = `700 13px ${FONT}`
    ctx.textAlign = 'left'
    ctx.fillText(pct(row.awa), left + totalW + 10, cy)
  })

  drawFooter(ctx, width, height)
  await savePng(canvas, options.filename)
}

/** Tabla de resultados (TOM, Espontáneo, Ayudado, AWA) como imagen, lista para pegar en un informe. */
export async function downloadAwarenessTableImage(rows: AwarenessImageRow[], options: ImageOptions) {
  if (!rows.length) throw new Error('No hay datos para la tabla.')

  const pad = 40
  const numberW = 130
  const nameW = Math.min(360, Math.max(210, Math.ceil(measureLabels(rows, `500 13px ${FONT}`)) + 56))
  const width = pad * 2 + nameW + numberW * 4
  const top = 100
  const headH = 46
  const rowH = 40
  const bottom = 56
  const tableH = headH + rows.length * rowH
  const height = top + tableH + bottom

  const { canvas, ctx } = await createCanvas(width, height)
  drawHeader(ctx, options)

  const x0 = pad
  const columns = [
    { label: 'Marca', x: x0, w: nameW, align: 'left' as const },
    { label: 'TOM', x: x0 + nameW, w: numberW, align: 'center' as const },
    { label: 'Espontáneo', x: x0 + nameW + numberW, w: numberW, align: 'center' as const },
    { label: 'Ayudado', x: x0 + nameW + numberW * 2, w: numberW, align: 'center' as const },
    { label: 'AWA', x: x0 + nameW + numberW * 3, w: numberW, align: 'center' as const },
  ]
  const tableW = nameW + numberW * 4

  ctx.save()
  roundRectPath(ctx, x0, top, tableW, tableH, 10)
  ctx.clip()

  // Cabecera
  ctx.fillStyle = C.navy
  ctx.fillRect(x0, top, tableW, headH)

  // Filas
  rows.forEach((row, index) => {
    const y = top + headH + index * rowH
    ctx.fillStyle = index % 2 === 0 ? '#ffffff' : C.band
    ctx.fillRect(x0, y, tableW, rowH)
    ctx.fillStyle = C.tint
    ctx.fillRect(columns[4].x, y, columns[4].w, rowH)
    ctx.fillStyle = C.line
    ctx.fillRect(x0, y + rowH - 1, tableW, 1)
  })
  ctx.restore()

  // Texto de cabecera
  ctx.font = `700 12px ${FONT}`
  ctx.fillStyle = '#ffffff'
  columns.forEach((column) => {
    ctx.textAlign = column.align
    const tx = column.align === 'left' ? column.x + 18 : column.x + column.w / 2
    ctx.fillText(column.label, tx, top + headH / 2)
  })

  // Texto de filas
  rows.forEach((row, index) => {
    const cy = top + headH + index * rowH + rowH / 2
    ctx.textAlign = 'left'
    ctx.fillStyle = C.ink
    ctx.font = `600 13px ${FONT}`
    ctx.fillText(fitText(ctx, row.name, nameW - 36), columns[0].x + 18, cy)

    const values = [row.tom, row.esp, row.ayu, row.awa]
    ctx.textAlign = 'center'
    values.forEach((value, valueIndex) => {
      const column = columns[valueIndex + 1]
      const isAwa = valueIndex === 3
      ctx.fillStyle = isAwa ? C.ink : (value > 0 ? C.text : '#a7b0bf')
      ctx.font = isAwa ? `700 13px ${FONT}` : `400 13px ${FONT}`
      ctx.fillText(pct(value), column.x + column.w / 2, cy)
    })
  })

  // Borde exterior
  ctx.strokeStyle = C.line
  ctx.lineWidth = 1
  roundRectPath(ctx, x0 + 0.5, top + 0.5, tableW - 1, tableH - 1, 10)
  ctx.stroke()

  drawFooter(ctx, width, height)
  await savePng(canvas, options.filename)
}
