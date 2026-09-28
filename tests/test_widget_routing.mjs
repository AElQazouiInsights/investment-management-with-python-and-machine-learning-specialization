import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

async function workerHarness() {
  const source = await readFile(new URL('../src/pyodide-worker.js', import.meta.url), 'utf8')
  const messages = []
  const state = { widget: null, beforeExecution: [], executions: [], stdout: null, release: null }
  const pyodide = {
    FS: { mkdirTree() {}, writeFile() {} },
    globals: { set() {} },
    setStdout(handler) { state.stdout = handler }, setStderr() {}, setStdin() {},
    async loadPackage() {},
    runPython(code) {
      if (code.trim() === 'widget_instance = None') state.widget = null
      if (code.includes("globals().get('widget_instance', None)") && !code.includes('dependency_state')) return state.widget
      if (code === '_widget_json_result') return state.widget ? JSON.stringify(state.widget) : ''
    },
    async runPythonAsync(code) {
      if (code.includes('import micropip')) return
      state.executions.push(code)
      state.beforeExecution.push(state.widget)
      if (code === 'slow-code') await new Promise(resolve => { state.release = resolve })
      if (code === 'slow-code' || code === 'plain-code') state.stdout.write(new TextEncoder().encode(`${code}\n`))
      if (code === 'create-widget') state.widget = { model_id: 'current-widget' }
    },
  }
  // Execute the actual worker body with transport/runtime dependencies supplied.
  const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
  const initialize = new AsyncFunction('loadPyodide', 'fetch', 'postMessage', 'TextDecoder', 'setTimeout', 'clearTimeout',
    `let onmessage;\n${source.replace(/^import .*?;\n/, '')}\nreturn onmessage;`)
  const handler = await initialize(async () => pyodide, async () => ({ ok: true, text: async () => '' }),
    message => messages.push(message), TextDecoder, setTimeout, clearTimeout)
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

test('the editor forwards seed zero to the correct Python chart helper', async () => {
  const source = await readFile(new URL('../src/Editor.vue', import.meta.url), 'utf8')
  const allowed = source.match(/const allowedParamsByFunction: Record<string, Set<string>> = (\{[\s\S]*?\n\})/)[1]
  const builder = source.match(/function buildEchartCode\(values: Record<string, any>\) \{[\s\S]*?\n\}/)[0]
    .replace('values: Record<string, any>', 'values')
  // Remove only the type annotation; run the editor's actual filtering/build logic.
  const createBuilder = new Function('widgetContexts', 'props', `const allowedParamsByFunction = ${allowed};\n${builder};\nreturn buildEchartCode;`)
  for (const helper of ['show_gbm_echart', 'show_cppi_echart']) {
    const contexts = new Map([['editor', { lastCode: `pok.${helper}(seed=42)` }]])
    const build = createBuilder(contexts, { id: 'editor' })
    assert.equal(build({ seed: 0, mu: 0.07, unsupported: 1 }),
      `import PortfolioOptimizationKit as pok\npok.${helper}(seed=0, mu=0.07)`)
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
