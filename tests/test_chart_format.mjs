import assert from 'node:assert/strict'
import test from 'node:test'
import { formatChartTick, formatChartValue } from '../src/chart-format.js'

test('axis ticks stay compact without changing the chart data units', () => {
  assert.equal(formatChartTick(1000000), '1M')
  assert.equal(formatChartTick(3500), '3.5K')
  assert.equal(formatChartTick(191.3905245277), '191.4')
  assert.equal(formatChartTick(-0.25), '-0.25')
  assert.equal(formatChartTick(0.0001234), '0.0001234')
})

test('tooltips retain useful precision and display percentage units exactly once', () => {
  assert.equal(formatChartValue(3908.881947, 'Wealth ($)'), '3,908.8819')
  assert.equal(formatChartValue(60, 'Risky allocation (%)'), '60%')
  assert.equal(formatChartValue(0.6305901, 'Correlation'), '0.6306')
  assert.equal(formatChartValue([0.5, 104.937747], 'Price'), '104.9377')
  assert.equal(formatChartValue(null, 'Return (%)'), '—')
})
