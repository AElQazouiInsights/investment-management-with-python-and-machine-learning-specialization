const tickFormat = new Intl.NumberFormat('en-US', { notation: 'compact', maximumSignificantDigits: 4 })
const valueFormat = new Intl.NumberFormat('en-US', { maximumFractionDigits: 4 })

export function formatChartTick(value) {
  return typeof value === 'number' && Number.isFinite(value) ? tickFormat.format(value) : String(value)
}

export function formatChartValue(value, unit = '') {
  // Numeric-axis line data is [x, y]; the axis tooltip already identifies x.
  const y = Array.isArray(value) ? value[1] : value
  if (y === null || y === undefined || !Number.isFinite(y)) return '—'
  return valueFormat.format(y) + (unit.includes('%') ? '%' : '')
}
