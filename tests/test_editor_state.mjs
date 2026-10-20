import assert from 'node:assert/strict'
import test from 'node:test'
import { createEditorStorage, loadEditorCode, saveEditorCode, restoreEditorCode, useCurrentExample } from '../src/editor-storage.js'
import { createOutputParser, parseChartOutput } from '../src/editor-output.js'

function storage() {
  const values = new Map()
  return {
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: key => values.delete(key),
  }
}

test('legacy saved snippets cannot silently replace revised examples', () => {
  const store = storage()
  const key = 'code-editor-calculating-indexes-7'
  const old = 'tmi_trail_36_rets = total_market_return.rolling(36).mean()'
  const current = 'rolling_months = 36\nrolling_growth = ...'
  store.setItem(key, old)
  assert.deepEqual(loadEditorCode(store, key, current), { code: current, recoveredCode: old })
  saveEditorCode(store, key, current, current)
  assert.deepEqual(loadEditorCode(store, key, current), { code: current, recoveredCode: old })
  assert.equal(restoreEditorCode(store, key, current, current), old)
  assert.deepEqual(loadEditorCode(store, key, current), { code: old, recoveredCode: null })
})

test('same-version edits survive navigation, and new lesson versions preserve their history', () => {
  const store = storage()
  const key = 'code-editor-gbm-4'
  loadEditorCode(store, key, 'source v1')
  saveEditorCode(store, key, 'source v1', 'my edits v1')
  assert.deepEqual(loadEditorCode(store, key, 'source v1'), { code: 'my edits v1', recoveredCode: null })
  assert.deepEqual(loadEditorCode(store, key, 'source v2'), { code: 'source v2', recoveredCode: 'my edits v1' })
  saveEditorCode(store, key, 'source v2', 'my edits v2')
  assert.equal(restoreEditorCode(store, key, 'source v2', 'my edits v2'), 'my edits v1')
  const state = JSON.parse(store.getItem(`${key}:state`))
  assert.deepEqual(state.history.map(entry => entry.code), ['my edits v1', 'my edits v2'])
})

test('reset preserves edited code without reloading it on the next visit', () => {
  const store = storage()
  const key = 'code-editor-example'
  loadEditorCode(store, key, 'source')
  saveEditorCode(store, key, 'source', 'custom code')
  assert.equal(useCurrentExample(store, key, 'source', 'custom code'), 'source')
  assert.deepEqual(loadEditorCode(store, key, 'source'), { code: 'source', recoveredCode: null })
  assert.equal(JSON.parse(store.getItem(`${key}:state`)).history[0].code, 'custom code')
})

function outputHarness() {
  const text = [], charts = [], errors = []
  const parser = createOutputParser({ onText: part => text.push(part), onChart: chart => charts.push(chart), onError: error => errors.push(error) })
  return { parser, text, charts, errors }
}

test('blocked storage keeps drafts editable and restorable within the session', () => {
  let notices = 0
  const store = createEditorStorage(() => { throw new Error('SecurityError') }, () => notices++)
  const key = 'code-editor-example'
  assert.equal(loadEditorCode(store, key, 'source v1').code, 'source v1')
  saveEditorCode(store, key, 'source v1', 'my draft')
  assert.equal(loadEditorCode(store, key, 'source v1').code, 'my draft')
  assert.equal(loadEditorCode(store, key, 'source v2').recoveredCode, 'my draft')
  assert.equal(restoreEditorCode(store, key, 'source v2', 'source v2'), 'my draft')
  assert.equal(notices, 1)
})

test('full storage cannot delete an old draft before its archive is persisted', () => {
  const disk = storage()
  const key = 'code-editor-example'
  disk.setItem(key, 'legacy draft')
  disk.setItem = () => { throw new Error('QuotaExceededError') }
  const store = createEditorStorage(() => disk, () => {})
  assert.deepEqual(loadEditorCode(store, key, 'new source'), {
    code: 'new source', recoveredCode: 'legacy draft',
  })
  assert.equal(disk.getItem(key), 'legacy draft')
  assert.equal(restoreEditorCode(store, key, 'new source', 'new source'), 'legacy draft')
})

test('malformed source metadata cannot prevent recovery of the legacy draft', () => {
  const store = storage()
  const key = 'code-editor-example'
  store.setItem(key, 'legacy draft')
  store.setItem(`${key}:state`, JSON.stringify({ version: 1, history: [null], pending: 0 }))
  assert.deepEqual(loadEditorCode(store, key, 'source'), { code: 'source', recoveredCode: 'legacy draft' })
})

test('streamed chart markers and JSON can be split at every character', () => {
  const { parser, text, charts, errors } = outputHarness()
  const json = JSON.stringify({ plot: { series: { Portfolio: [100, 110] } } })
  for (const char of `Summary\n<ECHARTS_DATA>${json}\nDone\n`) parser.push(char)
  parser.finish()
  assert.equal(text.join(''), 'Summary\nDone\n')
  assert.deepEqual(charts, [`<ECHARTS_DATA>${json}`])
  assert.deepEqual(errors, [])
})

test('widget clear-output escape sequences do not leak [2K into the console', () => {
  const { parser, text, errors } = outputHarness()
  for (const part of ['\x1b', '[2', 'K\r', '\x1b[2K\r', 'Ready\n']) parser.push(part)
  parser.finish()
  assert.equal(text.join(''), '\r\rReady\n')
  assert.deepEqual(errors, [])
})

test('malformed and incomplete chart messages report errors and recover', () => {
  const { parser, text, charts, errors } = outputHarness()
  parser.push('<ECHARTS_DATA>{broken}\nNext line\n')
  parser.push('<ECHARTS_DATA>{"plot":')
  parser.finish()
  parser.push('<ECHARTS_DATA>{"good":true}')
  parser.finish()
  assert.equal(errors.length, 2)
  assert.equal(text.join(''), 'Next line\n')
  assert.deepEqual(charts, ['<ECHARTS_DATA>{"good":true}'])
})

test('chart labels containing the protocol marker survive streamed and direct parsing', () => {
  const payload = { chart: { title: 'Literal <ECHARTS_DATA> label', series: { Portfolio: [100, 110] } } }
  const raw = '<ECHARTS_DATA>' + JSON.stringify(payload)
  const { parser, text, charts, errors } = outputHarness()
  for (const character of raw + '\n') parser.push(character)
  parser.finish()
  assert.deepEqual(charts, [raw])
  assert.equal(text.join(''), '')
  assert.deepEqual(errors, [])
  assert.deepEqual(parseChartOutput('Summary\n' + charts[0]), { text: 'Summary', chart: payload, error: '' })
})

test('invalid direct chart messages yield a displayable error and no stale chart data', () => {
  for (const json of ['{broken}', 'null', '[]', '42', '']) {
    const parsed = parseChartOutput('Summary\n<ECHARTS_DATA>' + json)
    assert.equal(parsed.text, 'Summary')
    assert.equal(parsed.chart, null)
    assert.match(parsed.error, /^Invalid chart data:/)
  }
  assert.deepEqual(parseChartOutput('<ECHARTS_DATA>{"valid":true}'), {
    text: '', chart: { valid: true }, error: '',
  })
})

test('plain text and cleared chart output remain plain text without a chart error', () => {
  assert.deepEqual(parseChartOutput('  Summary\n'), { text: 'Summary', chart: null, error: '' })
  assert.deepEqual(parseChartOutput(''), { text: '', chart: null, error: '' })
})
