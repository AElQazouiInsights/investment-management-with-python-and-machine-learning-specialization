const chartMarker = '<ECHARTS_DATA>'

// Parse the first protocol boundary only: marker text inside a JSON string is data.
export function parseChartOutput(output) {
  const marker = output.indexOf(chartMarker)
  if (marker === -1) return { text: output.trim(), chart: null, error: '' }
  const text = output.slice(0, marker).trim()
  try {
    const chart = JSON.parse(output.slice(marker + chartMarker.length))
    if (chart === null || typeof chart !== 'object' || Array.isArray(chart)) {
      throw new Error('Expected a JSON object for chart data')
    }
    return { text, chart, error: '' }
  } catch (error) {
    return { text, chart: null, error: `Invalid chart data: ${error.message}` }
  }
}

// stdout is a byte stream: neither ANSI escapes nor chart JSON must fit one write.
export function createOutputParser({ onText, onChart, onError }) {
  let buffer = ''
  let escapeTail = ''
  let readingChart = false
  let skipChartNewline = false

  function clean(text) {
    text = escapeTail + text
    escapeTail = ''
    const escape = text.lastIndexOf('\x1b')
    if (escape !== -1 && /^\x1b(?:\[[0-?]*[ -/]*)?$/.test(text.slice(escape))) {
      escapeTail = text.slice(escape)
      text = text.slice(0, escape)
    }
    return text.replace(/\x1b\[[0-?]*[ -/]*[@-~]/g, '')
  }

  function push(text) {
    buffer += clean(text)
    while (buffer) {
      if (skipChartNewline) {
        if (buffer.startsWith('\n')) buffer = buffer.slice(1)
        skipChartNewline = false
        if (!buffer) return
      }
      if (readingChart) {
        const newline = buffer.indexOf('\n')
        const candidate = newline === -1 ? buffer : buffer.slice(0, newline)
        try {
          JSON.parse(candidate)
          onChart(chartMarker + candidate)
          skipChartNewline = newline === -1
        } catch (error) {
          if (newline === -1) return
          onError(`Invalid chart JSON: ${error.message}`)
        }
        buffer = newline === -1 ? '' : buffer.slice(newline + 1)
        readingChart = false
        continue
      }
      const marker = buffer.indexOf(chartMarker)
      if (marker !== -1) {
        if (marker) onText(buffer.slice(0, marker))
        buffer = buffer.slice(marker + chartMarker.length)
        readingChart = true
        continue
      }
      let partial = Math.min(buffer.length, chartMarker.length - 1)
      while (partial && !chartMarker.startsWith(buffer.slice(-partial))) partial--
      const available = buffer.length - partial
      if (available) onText(buffer.slice(0, available))
      buffer = buffer.slice(available)
      return
    }
  }

  function finish() {
    if (readingChart) onError('Incomplete chart JSON received')
    else if (buffer) onText(buffer)
    reset()
  }

  function reset() {
    buffer = ''
    escapeTail = ''
    readingChart = false
    skipChartNewline = false
  }

  return { push, finish, reset }
}
