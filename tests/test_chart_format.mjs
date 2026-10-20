import assert from 'node:assert/strict'
import test from 'node:test'
import { formatChartTick, formatChartValue } from '../src/chart-format.js'
import { buildChartSeries } from '../src/chart-series.js'

test('allocation targets use endpoint steps while ordinary price lines stay continuous', () => {
  const targets = [[0, 80], [0.5, 20], [1, 20]]
  const series = buildChartSeries('Glide path', targets, 'line', true, { step: 'end' })
  assert.equal(series.step, 'end')
  assert.deepEqual(series.data, targets)
  assert.equal(buildChartSeries('Wealth', targets, 'line', true).step, undefined)
  assert.equal(buildChartSeries('Wealth', targets, 'line', true, { step: 'invalid' }).step, undefined)
})

test('single selected points remain visible within a line chart', () => {
  const data = [[5, 94.491875]]
  const selected = buildChartSeries('Selected bond', data, 'line', true,
    { type: 'scatter', symbol: 'diamond', symbolSize: 11 })
  assert.equal(selected.type, 'scatter')
  assert.equal(selected.showSymbol, true)
  assert.equal(selected.symbol, 'diamond')
  assert.equal(selected.symbolSize, 11)
  assert.deepEqual(selected.encode, { x: 0, y: 1 })
  assert.equal(selected.data, data)
  assert.equal(buildChartSeries('Bond price', data, 'line', true).showSymbol, false)
})

test('series extraction preserves existing portfolio markers and floor styles', () => {
  for (const [name, color, symbol] of [['GMV', 'black', 'diamond'], ['MSR', 'red', 'rect'],
    ['MinVolForTarget', 'black', 'diamond'], ['MaxSharpePort', 'red', 'diamond'], ['EWP', 'goldenrod', 'rect']]) {
    const series = buildChartSeries(name, [], 'line', true)
    assert.equal(series.type, 'scatter')
    assert.deepEqual(series.itemStyle, { color })
    assert.equal(series.symbol, symbol)
    assert.equal(series.z, 10)
  }
  assert.equal(buildChartSeries('Frontier', [], 'scatter', true).type, 'line')
  assert.equal(buildChartSeries('CML', [], 'scatter', true).type, 'line')
  assert.equal(buildChartSeries('Floor', [], 'line', false).lineStyle.type, 'dashed')
  assert.equal(buildChartSeries('Fixed floor', [], 'line', false).lineStyle.type, 'dashed')
  assert.equal(buildChartSeries('Floor for next allocation', [], 'line', false).lineStyle.type, 'dashed')
  assert.equal(buildChartSeries('Floor PV', [], 'line', true).lineStyle.type, 'dashed')
  assert.equal(buildChartSeries('Floor allocator', [], 'line', true).lineStyle.type, undefined)
  assert.equal(buildChartSeries('High-water floor', [], 'line', true).lineStyle.type, 'dashed')
  assert.equal(buildChartSeries('Drawdown limit', [], 'line', true).lineStyle.type, 'dashed')
  assert.equal(buildChartSeries('Policy + ZCB', [], 'line', true).lineStyle.type, undefined)
  assert.equal(buildChartSeries('Target', [], 'line', true).lineStyle.type, 'dashed')
  assert.equal(buildChartSeries('Face value', [], 'line', true, { lineStyle: { type: 'dashed' } }).lineStyle.type, 'dashed')
})

test('axis ticks stay compact without changing the chart data units', () => {
  assert.equal(formatChartTick(1000000), '1M')
  assert.equal(formatChartTick(3500), '3.5K')
  assert.equal(formatChartTick(191.3905245277), '191.4')
  assert.equal(formatChartTick(-0.25), '-0.25')
  assert.equal(formatChartTick(0.0001234), '0.0001234')
})

test('ordinary series names cannot inherit portfolio marker styles', () => {
  for (const name of ['constructor', 'toString', '__proto__', 'hasOwnProperty']) {
    const series = buildChartSeries(name, [1, 2], 'line', false)
    assert.equal(series.type, 'line')
    assert.equal(series.showSymbol, false)
    assert.equal(series.z, 1)
    assert.deepEqual(series.itemStyle, {})
  }
})

test('portfolio names remain ordinary series in bar and categorical time charts', () => {
  for (const name of ['GMV', 'MSR', 'EWP', 'Portfolios', 'Frontier', 'CML']) {
    for (const numericAxis of [true, false]) {
      const series = buildChartSeries(name, [20, 80], 'bar', numericAxis)
      assert.equal(series.type, 'bar')
      assert.deepEqual(series.itemStyle, {})
    }
    assert.equal(buildChartSeries(name, [100, 110], 'line', false).type, 'line')
  }
  assert.equal(buildChartSeries('GMV', [[10, 8]], 'line', true).type, 'scatter')
})

test('tooltips retain useful precision and display percentage units exactly once', () => {
  assert.equal(formatChartValue(3908.881947, 'Wealth ($)'), '3,908.8819')
  assert.equal(formatChartValue(60, 'Risky allocation (%)'), '60%')
  assert.equal(formatChartValue(0.6305901, 'Correlation'), '0.6306')
  assert.equal(formatChartValue([0.5, 104.937747], 'Price'), '104.9377')
  assert.equal(formatChartValue(null, 'Return (%)'), '—')
})
