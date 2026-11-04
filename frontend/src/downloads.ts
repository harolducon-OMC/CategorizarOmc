export function downloadCsv(
  filename: string,
  headers: string[],
  rows: Array<Record<string, unknown>>,
) {
  const escapeCell = (value: unknown) => {
    let text = value == null ? '' : String(value)
    if (/^\s*[=+\-@]/.test(text)) text = `'${text}`
    return `"${text.replace(/"/g, '""')}"`
  }
  const content = [headers, ...rows.map((row) => headers.map((header) => row[header]))]
    .map((row) => row.map(escapeCell).join(','))
    .join('\r\n')
  const blob = new Blob([`\uFEFF${content}`], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export async function downloadChartPngById(elementId: string, filename: string) {
  const container = document.getElementById(elementId)
  const original = container?.querySelector('svg.recharts-surface, svg')
  if (!(original instanceof SVGSVGElement)) {
    throw new Error('No encontré el gráfico para descargar.')
  }

  const bounds = original.getBoundingClientRect()
  const width = Math.ceil(Number(original.getAttribute('width')) || bounds.width)
  const height = Math.ceil(Number(original.getAttribute('height')) || bounds.height)
  if (!width || !height) throw new Error('El gráfico aún no tiene un tamaño descargable.')

  const svg = original.cloneNode(true) as SVGSVGElement
  svg.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
  svg.setAttribute('width', String(width))
  svg.setAttribute('height', String(height))
  if (!svg.getAttribute('viewBox')) svg.setAttribute('viewBox', `0 0 ${width} ${height}`)

  const svgUrl = URL.createObjectURL(new Blob(
    [new XMLSerializer().serializeToString(svg)],
    { type: 'image/svg+xml;charset=utf-8' },
  ))

  try {
    const image = new Image()
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve()
      image.onerror = () => reject(new Error('No se pudo preparar la imagen del gráfico.'))
      image.src = svgUrl
    })

    const scale = 2
    const canvas = document.createElement('canvas')
    canvas.width = width * scale
    canvas.height = height * scale
    const context = canvas.getContext('2d')
    if (!context) throw new Error('El navegador no pudo preparar la descarga PNG.')
    context.fillStyle = '#ffffff'
    context.fillRect(0, 0, canvas.width, canvas.height)
    context.scale(scale, scale)
    context.drawImage(image, 0, 0, width, height)

    const png = await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob((blob) => {
        if (blob) resolve(blob)
        else reject(new Error('No se pudo crear el archivo PNG.'))
      }, 'image/png')
    })
    const pngUrl = URL.createObjectURL(png)
    const anchor = document.createElement('a')
    anchor.href = pngUrl
    anchor.download = filename
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    window.setTimeout(() => URL.revokeObjectURL(pngUrl), 1000)
  } finally {
    URL.revokeObjectURL(svgUrl)
  }
}
