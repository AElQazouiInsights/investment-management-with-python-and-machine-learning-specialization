import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import { receiveInput } from '../src/editor-input.js'

async function workerHarness() {
  const source = await readFile(new URL('../src/pyodide-worker.js', import.meta.url), 'utf8')
  const messages = []
  const state = { widget: null, beforeExecution: [], executions: [], stdout: null, release: null, interruptBuffer: null, globals: {} }
  const pyodide = {
    FS: { mkdirTree() {}, writeFile() {} },
    globals: { set(name, value) { state.globals[name] = value } },
    setStdout(handler) { state.stdout = handler }, setStderr() {}, setStdin() {},
    setInterruptBuffer(buffer) { state.interruptBuffer = buffer },
    async loadPackage() {},
    runPython(code) {
      if (code.trim() === 'widget_instance = None') state.widget = null
      if (code.includes("globals().get('widget_instance', None)") && !code.includes('dependency_state')) return state.widget
      if (code === '_widget_json_result') return state.widget ? JSON.stringify(state.widget) : ''
    },
    async runPythonAsync(code) {
      if (code.includes('import micropip')) return
      if (code.includes('await _editor_eval_code_async')) code = state.globals._editor_source
      state.executions.push(code)
      state.beforeExecution.push(state.widget)
      if (code === 'slow-code') await new Promise(resolve => { state.release = resolve })
      if (code === 'slow-code' || code === 'plain-code') state.stdout.write(new TextEncoder().encode(`${code}\n`))
      if (code === 'user-progress') {
        for (const text of ['Loading observations\n', 'Loaded 492 months\n',
          'User text: already loaded from default channel\n<ECHARTS_DATA>{"chart":{"series":{"A":[1,2]}}}\n']) {
          state.stdout.write(new TextEncoder().encode(text))
        }
      }
      if (code === 'create-widget') state.widget = { model_id: 'current-widget' }
    },
  }
  // Execute the actual worker body with transport/runtime dependencies supplied.
  const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
  const initialize = new AsyncFunction('loadPyodide', 'fetch', 'postMessage', 'TextDecoder', 'setTimeout', 'clearTimeout', 'receiveInput',
    `let onmessage;\n${source.replace(/^import .*?;\n/gm, '')}\nreturn onmessage;`)
  const handler = await initialize(async () => pyodide, async () => ({ ok: true, text: async () => '' }),
    message => messages.push(message), TextDecoder, setTimeout, clearTimeout, receiveInput)
  return { handler, messages, state }
}

test('a plain editor run does not serialize the preceding editor widget', async () => {
  const { handler, messages, state } = await workerHarness()
  await handler({ data: { id: 'interactive', code: 'create-widget' } })
  assert.equal(messages.filter(message => message.widgetState).length, 1)
  await handler({ data: { id: 'plain', code: 'plain-code' } })
  assert.equal(state.beforeExecution.at(-1), null)
  assert.equal(messages.some(message => message.id === 'plain' && message.widgetState), false)
})

test('slider updates retain their widget and do not reserialize controls', async () => {
  const { handler, messages, state } = await workerHarness()
  await handler({ data: { id: 'interactive', code: 'create-widget' } })
  const original = state.widget
  await handler({ data: { id: 'interactive', code: 'slider-code', skipWidgetState: true } })
  assert.equal(state.beforeExecution.at(-1), original)
  assert.equal(state.widget, original)
  assert.equal(messages.filter(message => message.widgetState).length, 1)
})

test('dropdown changes use the underlying option value, including zero, rather than its label or index', async () => {
  const { controlChangeEvent, controlValue } = await import('../src/widget-controls.js')
  const state = { _model_name: 'DropdownModel', _options_labels: ['None', 'Monthly', 'Weekly'],
    _echarts_option_values: [0, 12, 52], index: 0 }
  const model = { get: key => state[key] }
  assert.equal(controlChangeEvent(model), 'change:index')
  assert.equal(controlValue(model), 0)
  state.index = 2
  assert.equal(controlValue(model), 52)
  state.index = null
  assert.equal(controlValue(model), undefined)
  state._model_name = 'FloatSliderModel'
  state.value = 1.1
  assert.equal(controlChangeEvent(model), 'change:value')
  assert.equal(controlValue(model), 1.1)
})

test('the editor forwards seed zero to the correct Python chart helper', async () => {
  const { buildChartCode } = await import('../src/widget-controls.js')
  for (const helper of ['show_gbm_echart', 'show_cppi_echart', 'show_cir_echart']) {
    const values = helper === 'show_cir_echart' ? { seed: 0, a: 0.5, r0: 0.05, unsupported: 1 } : { seed: 0, mu: 0.07, unsupported: 1 }
    const parameters = helper === 'show_cir_echart' ? 'seed=0, a=0.5, r0=0.05' : 'seed=0, mu=0.07'
    assert.equal(buildChartCode(`pok.${helper}(seed=42)`, values), `import PortfolioOptimizationKit as pok\npok.${helper}(${parameters})`)
  }
  assert.equal(buildChartCode('pok.show_liability_hedging_echart(seed=42)',
    { seed: 0, initial_assets: 0, liability: 2, periods_per_year: 52, r0: 0.03, unsupported: 1 }),
    'import PortfolioOptimizationKit as pok\npok.show_liability_hedging_echart(seed=0, initial_assets=0, liability=2, periods_per_year=52, r0=0.03)')
  assert.equal(buildChartCode('pok.show_coupon_bond_echart()',
    { coupon_rate: 0, ytm: -0.01, coupons_per_year: 4, reinvestment_rate: 0, seed: 42 }),
    'import PortfolioOptimizationKit as pok\npok.show_coupon_bond_echart(coupon_rate=0, ytm=-0.01, coupons_per_year=4, reinvestment_rate=0)')
  assert.equal(buildChartCode('widgets.interactive(pok.show_duration_echart)',
    { principal: 100, ytm: 0, coupons_per_year: 12, shift_bps: -50, reinvestment_rate: 0 }),
    'import PortfolioOptimizationKit as pok\npok.show_duration_echart(principal=100, ytm=0, coupons_per_year=12, shift_bps=-50)')
})

test('unknown helpers and empty supported controls do not generate widget reruns', async () => {
  const { buildChartCode, chartHelperName } = await import('../src/widget-controls.js')
  assert.equal(chartHelperName('print(42)'), undefined)
  assert.equal(buildChartCode('print(42)', { seed: 1 }), '')
  assert.equal(buildChartCode('pok.show_duration_echart()', { maturity: undefined, seed: 42 }), '')
  assert.equal(buildChartCode('pok.show_cir_echart()', { r0: null }),
    'import PortfolioOptimizationKit as pok\npok.show_cir_echart(r0=None)')
  assert.equal(buildChartCode('pok.show_psp_lhp_echart()', { psp_weight: 0, sigma: 0, seed: 0, unsupported: true }),
    'import PortfolioOptimizationKit as pok\npok.show_psp_lhp_echart(psp_weight=0, sigma=0, seed=0)')
  assert.equal(buildChartCode('pok.show_cppi_echart()', { floor: false }),
    'import PortfolioOptimizationKit as pok\npok.show_cppi_echart(floor=False)')
  assert.equal(buildChartCode('pok.show_glidepath_echart()', { start: 0, end: 1, periods_per_year: 12, seed: 0, mu: 0.07 }),
    'import PortfolioOptimizationKit as pok\npok.show_glidepath_echart(start=0, end=1, periods_per_year=12, seed=0)')
  assert.equal(buildChartCode('pok.show_floor_echart()', { floor: 0, m: 0, scenario: 2, seed: 0, mu: 0.07 }),
    'import PortfolioOptimizationKit as pok\npok.show_floor_echart(floor=0, m=0, scenario=2, seed=0)')
  assert.equal(buildChartCode('pok.show_drawdown_echart()', { hedge: 'zcb', maxdd: 0.1, scenario: 2, seed: 0, m: 5 }),
    'import PortfolioOptimizationKit as pok\npok.show_drawdown_echart(hedge="zcb", maxdd=0.1, scenario=2, seed=0)')
  assert.equal(buildChartCode('pok.show_historical_drawdown_echart()', { start_year: 2000, end_year: 2018, maxdd: 0.2, cash_rate: 0, seed: 42 }),
    'import PortfolioOptimizationKit as pok\npok.show_historical_drawdown_echart(start_year=2000, end_year=2018, maxdd=0.2, cash_rate=0)')
  assert.equal(buildChartCode('pok.show_duration_echart()', { quote: 'continuous', ytm: 0, shift_bps: -10 }),
    'import PortfolioOptimizationKit as pok\npok.show_duration_echart(quote="continuous", ytm=0, shift_bps=-10)')
  assert.equal(buildChartCode('pok.show_risk_parity_echart()', { correlation: 0, equity_budget: 0.1, seed: 42 }),
    'import PortfolioOptimizationKit as pok\npok.show_risk_parity_echart(correlation=0, equity_budget=0.1)')
})

test('friendly widget labels route through their Python parameter metadata', async () => {
  const { controlParameterName, controlValue, buildChartCode } = await import('../src/widget-controls.js')
  const state = { _model_name: 'IntSliderModel', description: 'Assets ($)', _echarts_parameter: 'asset_value', value: 131000 }
  const model = { get: key => state[key] }
  assert.equal(controlParameterName(model), 'asset_value')
  assert.equal(buildChartCode('widgets.interactive(pok.show_duration_matching_echart)',
    { [controlParameterName(model)]: controlValue(model), liability_delay: 0, seed: 42 }),
    'import PortfolioOptimizationKit as pok\npok.show_duration_matching_echart(asset_value=131000, liability_delay=0)')
  state.description = 'Starting capital'
  assert.equal(controlParameterName(model), 'asset_value')
  delete state._echarts_parameter
  state.description = 'Zoom Y axis'
  assert.equal(controlParameterName(model), 'ymax')
  state.description = 'seed'
  assert.equal(controlParameterName(model), 'seed')
})

test('serialized callback identity overrides misleading source references and supports aliases', async () => {
  const { chartHelperName, buildChartCode } = await import('../src/widget-controls.js')
  const source = '# Example copied from pok.show_black_litterman_echart\nwidgets.interactive(actual_callback)'
  assert.equal(chartHelperName(source, 'show_duration_echart'), 'show_duration_echart')
  assert.equal(buildChartCode(source, { quote: 'continuous', confidence: 0 }, 'show_duration_echart'),
    'import PortfolioOptimizationKit as pok\npok.show_duration_echart(quote="continuous")')
  assert.equal(buildChartCode('widgets.interactive(callback_alias)',
    { confidence: 0, tau: 0.05, risk_model: 'predictive' }, 'show_black_litterman_echart'),
    'import PortfolioOptimizationKit as pok\npok.show_black_litterman_echart(confidence=0, tau=0.05, risk_model="predictive")')
  for (const callback of ['', 'constructor', '__proto__', 'unknown_callback', null]) {
    assert.equal(buildChartCode(source, { confidence: 1 }, callback), '')
  }
})

test('asynchronous cell runs are serialized and keep their own stdout routing', async () => {
  const { handler, messages, state } = await workerHarness()
  const first = handler({ data: { id: 'first', code: 'slow-code' } })
  const second = handler({ data: { id: 'second', code: 'plain-code' } })
  while (!state.release) await new Promise(resolve => setImmediate(resolve))
  assert.deepEqual(state.executions, ['slow-code'])
  state.release()
  await Promise.all([first, second])
  assert.deepEqual(state.executions, ['slow-code', 'plain-code'])
  assert.deepEqual(messages.filter(message => message.output).map(({ id, output }) => [id, output]),
    [['first', 'slow-code\n'], ['second', 'plain-code\n']])
})

test('cancelling a queued cell does not interrupt the cell that is running', async () => {
  const { handler, messages, state } = await workerHarness()
  const first = handler({ data: { id: 'first', code: 'slow-code' } })
  const second = handler({ data: { id: 'second', code: 'plain-code' } })
  while (!state.release) await new Promise(resolve => setImmediate(resolve))
  await handler({ data: { cancel: 'second' } })
  state.release()
  await Promise.all([first, second])
  assert.deepEqual(state.executions, ['slow-code'])
  assert.ok(messages.some(message => message.id === 'second' && message.done))
})

test('user progress text is preserved even when it resembles package-loader messages', async () => {
  const { handler, messages } = await workerHarness()
  await handler({ data: { id: 'progress', code: 'user-progress' } })
  assert.equal(messages.filter(message => message.output).map(message => message.output).join(''),
    'Loading observations\nLoaded 492 months\nUser text: already loaded from default channel\n<ECHARTS_DATA>{"chart":{"series":{"A":[1,2]}}}\n')
  assert.ok(messages.filter(message => message.output).every(message => message.id === 'progress'))
})

test('the worker interrupt view shares the supplied buffer rather than copying its values', async () => {
  const { handler, state } = await workerHarness()
  const inputBuffer = new SharedArrayBuffer(1024)
  const waitBuffer = new SharedArrayBuffer(8)
  const interruptBuffer = new SharedArrayBuffer(1)
  await handler({ data: { inputBuffer, waitBuffer, interruptBuffer } })
  const mainThreadView = new Uint8Array(interruptBuffer)
  Atomics.store(mainThreadView, 0, 2)
  assert.equal(Atomics.load(state.interruptBuffer, 0), 2)
  Atomics.store(state.interruptBuffer, 0, 0)
  assert.equal(Atomics.load(mainThreadView, 0), 0)
})
