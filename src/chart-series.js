const referenceLines = new Set(['Floor', 'Fixed floor', 'Floor for next allocation', 'Floor PV', 'High-water floor', 'Drawdown limit', 'Target'])

const markerStyles = {
  GMV: { color: 'black', symbol: 'diamond', size: 12 },
  MSR: { color: 'red', symbol: 'rect', size: 12 },
  MinVolForTarget: { color: 'black', symbol: 'diamond', size: 12 },
  MaxSharpePort: { color: 'red', symbol: 'diamond', size: 12 },
  EWP: { color: 'goldenrod', symbol: 'rect', size: 12 },
}

export function buildChartSeries(name, data, chartType, numericAxis, options = {}) {
  const marker = markerStyles[name]
  const legacyType = marker || name === 'Portfolios' ? 'scatter'
    : ['Frontier', 'CML'].includes(name) ? 'line' : chartType
  const type = ['line', 'bar', 'scatter'].includes(options.type) ? options.type : legacyType
  return {
    name, type, data, encode: numericAxis ? { x: 0, y: 1 } : {},
    itemStyle: { ...(marker ? { color: marker.color } : {}), ...options.itemStyle },
    symbol: options.symbol || marker?.symbol || 'circle',
    symbolSize: options.symbolSize ?? marker?.size ?? 8,
    z: marker ? 10 : 1,
    showSymbol: type !== 'line',
    ...(type === 'line' && ['start', 'middle', 'end'].includes(options.step) ? { step: options.step } : {}),
    lineStyle: { width: 2, ...(type === 'line' && referenceLines.has(name)
      ? { type: 'dashed' } : {}), ...options.lineStyle },
  }
}
