<!-- src/Editor.vue -->
<script lang="ts">
let worker: Worker
let inputData: Uint8Array
let waitFlag: Int32Array
let interruptBuffer: Uint8Array

const ready = ref(false)
const encoder = new TextEncoder()

let widgetSchemaModule: any | null = null
let schemaModulePromise: Promise<any> | null = null

if (typeof window !== 'undefined') {
  schemaModulePromise = import('@jupyter-widgets/schema')
    .then((mod: any) => {
      widgetSchemaModule = mod?.default ?? mod ?? null
      return widgetSchemaModule
    })
    .catch((err: unknown) => {
      console.warn('Failed to preload @jupyter-widgets/schema:', err)
      return null
    })
}
</script>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted, watchEffect, nextTick } from 'vue'
import {
  EditorView,
  highlightSpecialChars,
  drawSelection,
  keymap,
  lineNumbers,
  highlightActiveLine,
} from '@codemirror/view'
import { history, defaultKeymap, historyKeymap, indentWithTab } from '@codemirror/commands'
import { indentUnit } from '@codemirror/language'
import { styling } from './codemirror-styling'
import OutputDisplay from './OutputDisplay.vue'

interface Props {
  id: string
  maxHeight?: string
}

// Default maxHeight for the CodeMirror editor
const props = withDefaults(defineProps<Props>(), {
  maxHeight: '344px'
})

const storageKey = computed(() => `code-editor-${props.id}`)

const mounted = ref(false)
const running = ref(false)
const waitingForInput = ref(false)
const chartOutput = ref('')

const widgetContexts = new Map<string, { controls: Record<string, any>; lastCode: string }>()
const pendingEchartUpdates = new Map<string, number>()
const latestControlValues = new Map<string, Record<string, any>>()

// The CodeMirror anchor and input references
let anchor = ref<HTMLDivElement>()
let parent = ref<HTMLDivElement>()
let input = ref<HTMLInputElement>()
let widgetContainer = ref<HTMLDivElement>()
let initialCode: string
let editor: EditorView

onMounted(() => {
  // 1) Initialize one worker instance for this entire session
  if (!worker) {
    worker = new Worker(new URL('./pyodide-worker.js', import.meta.url), {
      type: 'module'
    })
    const inputBuffer = new SharedArrayBuffer(1024)
    inputData = new Uint8Array(inputBuffer)
    const waitBuffer = new SharedArrayBuffer(4)
    waitFlag = new Int32Array(waitBuffer)
    interruptBuffer = new Uint8Array(new SharedArrayBuffer(1))

    worker.addEventListener('message', () => {
      ready.value = true
      worker.postMessage({ inputBuffer, waitBuffer, interruptBuffer })
    }, { once: true })
  }

  // 2) Listen for messages from the worker
  worker.addEventListener('message', handleMessage)

  // 3) Hide the original code block from VitePress & capture its text
  const prev = anchor.value?.previousElementSibling
  const codeElement = prev?.classList.contains('language-python') ? prev : null
  initialCode = codeElement?.querySelector('pre')?.textContent ?? ''
  codeElement?.setAttribute('hidden', '')

  // 4) Create the CodeMirror editor with persisted content
  editor = new EditorView({
    extensions: [
      highlightSpecialChars(),
      history(),
      drawSelection(),
      keymap.of([...defaultKeymap, ...historyKeymap, indentWithTab]),
      lineNumbers(),
      highlightActiveLine(),
      indentUnit.of('    '),
      styling,
    ],
    parent: parent.value!,
    doc: localStorage.getItem(storageKey.value) ?? initialCode
  })

  // 5) Save doc on tab switch or page hide
  document.addEventListener('visibilitychange', () => {
    save(editor.state.doc.toString())
  })

  mounted.value = true
})

onUnmounted(() => {
  save(editor.state.doc.toString())
  worker.removeEventListener('message', handleMessage)
  editor.destroy()
})

// Worker message handler
async function handleMessage(e: MessageEvent) {
  if (e.data.id !== props.id) return

  if (e.data.input) {
    waitingForInput.value = true
    await nextTick()
    input.value?.focus()
  }
  if (e.data.output) updateOutput(e.data.output)
  if (typeof e.data.echart === 'string') updateOutput(e.data.echart)
  if (e.data.widgetState) {
    console.info('ipywidgets: widgetState received')
    await renderWidget(e.data.widgetState)
  }
  if (e.data.done) running.value = false
}

const inputText = ref('')
watchEffect(() => {
  if (input.value) {
    input.value.style.width = `${inputText.value.length + 1}ch`
  }
})

function handleInput() {
  waitingForInput.value = false
  const inputArry = encoder.encode(inputText.value ?? '')
  inputText.value = ''

  Atomics.store(inputData, 0, inputArry.length)
  for (let i = 0; i < inputArry.length; i++)
    Atomics.store(inputData, i + 1, inputArry[i])

  Atomics.store(waitFlag, 0, 1)
  Atomics.notify(waitFlag, 0)
  Atomics.store(waitFlag, 0, 0)
}

// Button text changes depending on whether Pyodide is loaded/running
const buttonText = computed(() =>
  ready.value ? (running.value ? 'Running code...' : 'Run code') : 'Loading Pyodide...'
)

// The raw console text is stored in a 2D array
const output = ref<string[][]>([])
const outputWidth = 72
let outputRow = 0
let outputCol = 0

const outputLines = computed(() => {
  const lines = output.value.map(l => l.join(''))
  // if the last line is empty and we're not waiting for input, remove it
  if (lines[lines.length - 1] === '' && !waitingForInput.value) lines.pop()
  return lines.length === 0 ? [''] : lines
})

// Run the code from the editor
function run() {
  const code = editor.state.doc.toString()
  save(code)
  resetOutput()
  running.value = true
  interruptBuffer[0] = 0
  widgetContexts.set(props.id, { controls: {}, lastCode: code })
  // Run via in-page Pyodide worker for both normal and ipywidgets code.
  // The worker serializes widget state which we render in-page.
  worker.postMessage({ id: props.id, code, skipWidgetState: false })
}

// If code is still running, we "interrupt" it; otherwise, reset editor
function reset() {
  if (running.value) {
    // If the code is blocked for input, handle it first
    if (waitingForInput.value) handleInput()
    // Send a SIGINT (2)
    interruptBuffer[0] = 2
    return
  }
  localStorage.removeItem(storageKey.value)
  editor.dispatch({
    changes: { from: 0, to: editor.state.doc.length, insert: initialCode },
    selection: { anchor: 0 },
    scrollIntoView: true,
  })
  editor.focus()
  resetOutput()
}

// Save doc in local storage (unless it's the original text)
function save(code: string) {
  if (code === initialCode) localStorage.removeItem(storageKey.value)
  else localStorage.setItem(storageKey.value, code)
}

/**
 * If we detect "<ECHARTS_DATA>", we store that entire chunk in chartOutput.
 * Otherwise, we treat each character as normal console text.
 */
function updateOutput(raw: string) {
  if (raw.includes('<ECHARTS_DATA>')) {
    // We'll let <OutputDisplay> parse the actual JSON
    chartOutput.value = raw
    return
  }

  for (const c of raw) {
    if (c === '\n') {
      outputRow++
      outputCol = 0
      output.value[outputRow] = Array.from({ length: outputWidth })
      continue
    }
    if (c === '\b') {
      outputCol--
      if (outputCol < 0) {
        outputRow--
        outputCol = outputWidth - 1
      }
      if (outputRow < 0) {
        outputRow = 0
        outputCol = 0
      }
      continue
    }
    output.value[outputRow][outputCol] = c
    outputCol++
  }
}

function attachOutputListeners(model: any, manager: any, context: { controls: Record<string, any>; lastCode: string }) {
  if (!model || typeof model.get !== 'function') return
  if ((model as any)._echartsAttached) return
  (model as any)._echartsAttached = true

  const handleOutputs = () => {
    const outputs = model.get('outputs')
    if (!Array.isArray(outputs)) return
    for (const item of outputs) {
      if (!item) continue
      if (item.output_type === 'stream' && typeof item.text === 'string' && item.text.includes('<ECHARTS_DATA>')) {
        updateOutput(item.text)
      } else if ((item.output_type === 'display_data' || item.output_type === 'execute_result') && item.data) {
        const text = item.data['text/plain'] || item.data['text']
        if (typeof text === 'string' && text.includes('<ECHARTS_DATA>')) {
          updateOutput(text)
        }
      }
    }
  }

  if (model.get('_model_name') === 'OutputModel') {
    model.on('change:outputs', handleOutputs)
    handleOutputs()
  }

  attachValueObservers(model, manager, context)

  const children = model.get('children')
  if (Array.isArray(children)) {
    children.forEach((child: any) => {
      if (!child) return
      if (typeof child.then === 'function') {
        child.then((resolved: any) => attachOutputListeners(resolved, manager, context)).catch(() => {})
      } else if (typeof child.get === 'function') {
        attachOutputListeners(child, manager, context)
      } else if (typeof child === 'string' && child.startsWith('IPY_MODEL_') && manager?.get_model) {
        manager.get_model(child.slice(10)).then((resolved: any) => attachOutputListeners(resolved, manager, context)).catch(() => {})
      }
    })
  }

  model.on?.('change:children', () => {
    (model as any)._echartsAttached = false
    attachOutputListeners(model, manager, context)
  })
}

const controlModelNames = new Set(['IntSliderModel', 'FloatSliderModel', 'DropdownModel'])

function attachValueObservers(model: any, manager: any, context: { controls: Record<string, any>; lastCode: string }) {
  if (!model || typeof model.get !== 'function') return
  if ((model as any)._echartsValueAttached) return
  (model as any)._echartsValueAttached = true

  const modelName = model.get('_model_name')
  if (controlModelNames.has(modelName)) {
    const label = model.get('description') || modelName
    context.controls[label] = model
    model.on('change:value', () => queueEchartUpdate(context))
  }

  const children = model.get('children')
  if (Array.isArray(children)) {
    children.forEach((child: any) => {
      if (!child) return
      if (typeof child.then === 'function') {
        child.then((resolved: any) => attachValueObservers(resolved, manager, context)).catch(() => {})
      } else if (typeof child.get === 'function') {
        attachValueObservers(child, manager, context)
      } else if (typeof child === 'string' && child.startsWith('IPY_MODEL_') && manager?.get_model) {
        manager.get_model(child.slice(10)).then((resolved: any) => attachValueObservers(resolved, manager, context)).catch(() => {})
      }
    })
  }
}

const allowedParams = new Set(['n_years', 'n_scenarios', 'mu', 'sigma', 'periods_per_year', 'start'])

function queueEchartUpdate(context: { controls: Record<string, any>; lastCode: string }) {
  const values: Record<string, any> = {}
  for (const [label, model] of Object.entries(context.controls)) {
    if (!allowedParams.has(label)) continue
    try {
      const value = model.get?.('value')
      if (value === undefined || value === null) continue
      values[label] = value
    } catch (err) {
      console.warn('Failed to read control value', label, err)
    }
  }

  latestControlValues.set(props.id, values)
  if (pendingEchartUpdates.has(props.id)) return

  const handle = window.setTimeout(() => {
    pendingEchartUpdates.delete(props.id)
    const latestValues = latestControlValues.get(props.id) || {}
    const code = buildEchartCode(latestValues)
    if (!code) return
    worker.postMessage({ id: props.id, code, skipWidgetState: true })
  }, 120)

  pendingEchartUpdates.set(props.id, handle)
}

function buildEchartCode(values: Record<string, any>) {
  const entries = Object.entries(values)
    .filter(([key, value]) => allowedParams.has(key) && value !== undefined && value !== null)
    .map(([key, value]) => `${key}=${JSON.stringify(value)}`)

  if (entries.length === 0) return ''

  const args = entries.join(', ')
  return `import PortfolioOptimizationKit as pok\npok.show_gbm_echart(${args})`
}

// Clear out console lines & chart JSON
function resetOutput() {
  output.value = [Array.from({ length: outputWidth })]
  outputRow = 0
  outputCol = 0
  chartOutput.value = ''
  if (widgetContainer.value) widgetContainer.value.innerHTML = ''
}

async function renderWidget(stateJSON: string) {
  try {
    
    // Fix for webpack public path issue in Vite environment
    if (typeof (window as any).__webpack_public_path__ === 'undefined') {
      (window as any).__webpack_public_path__ = '/'
    }
    
    if (!widgetSchemaModule && schemaModulePromise) {
      try {
        await schemaModulePromise
      } catch (_) {
        /* already logged */
      }
    }

    // Set up global exports and require for CommonJS compatibility
    if (typeof (window as any).exports === 'undefined') {
      (window as any).exports = {}
    }
    if (typeof (window as any).module === 'undefined') {
      (window as any).module = { exports: {} }
    }
    // Create/replace a minimal require function for browser environment
    ;(window as any).require = (id: string) => {
      console.warn(`require('${id}') called in browser - returning shimmed object`)
      if (id === 'fs') {
        return { existsSync: () => false, readFileSync: () => '' }
      }
      if (id === 'path') {
        return { resolve: () => '', sep: '/' }
      }
      if (id === 'postcss') {
        return { parse: () => ({ nodes: [], toString: () => '' }) }
      }
      if (id === 'sanitize-html') {
        const sanitizeHtml = (dirty?: string) => (typeof dirty === 'string' ? dirty : '')
        sanitizeHtml.defaults = {
          allowedTags: ['div', 'span', 'p', 'b', 'i', 'em', 'strong', 'a', 'img'],
          allowedAttributes: {},
          allowedSchemes: ['http', 'https', 'ftp', 'mailto', 'tel']
        }
        sanitizeHtml.simpleTransform = (newTagName?: string, newAttribs: Record<string, string> = {}) => {
          return (tagName?: string, attribs: Record<string, string> = {}) => ({
            tagName: newTagName || tagName || 'div',
            attribs: { ...attribs, ...newAttribs }
          })
        }
        return sanitizeHtml
      }
      if (id === '@jupyter-widgets/schema') {
        if (widgetSchemaModule) return widgetSchemaModule
        console.warn('Falling back to minimal @jupyter-widgets/schema stub')
        return {
          v1: { state: {}, view: {} },
          v2: { state: {}, view: {} }
        }
      }
      return {}
    }
    
    const parsed = JSON.parse(stateJSON)
    
    const { state, model_id } = parsed
    
    // Try dynamic imports with fallback
    let htmlManagerModule, baseModule, controlsModule, outputModule
    
    try {
      // Ensure sanitize-html shim exposes the helper expected by html-manager
      try {
        const sanitizeMod = await import('sanitize-html')
        const sanitizeDefault = (sanitizeMod as any).default ?? sanitizeMod
        if (typeof sanitizeDefault.simpleTransform !== 'function') {
          sanitizeDefault.simpleTransform = (newTagName: string, newAttribs: Record<string, string> = {}) => {
            return (tagName: string, attribs: Record<string, string> = {}) => ({
              tagName: newTagName || tagName,
              attribs: { ...attribs, ...newAttribs }
            })
          }
        }
      } catch (err) {
        console.warn('[DEBUG] Unable to prime sanitize-html shim:', err)
      }

      // Import one at a time with better error isolation
      htmlManagerModule = await import('@jupyter-widgets/html-manager')

      baseModule = await import('@jupyter-widgets/base')

      controlsModule = await import('@jupyter-widgets/controls')

      outputModule = await import('@jupyter-widgets/output')

    } catch (err) {
      console.error('Failed to import ipywidgets modules:', err)
      throw new Error(`Module import failed: ${(err as Error).message}`)
    }

    const { HTMLManager } = htmlManagerModule
    const base = baseModule
    const controls = controlsModule
    const output = outputModule

    const resolveModule = (name: string) => {
      // Handle both exact matches and module paths
      if (name === '@jupyter-widgets/controls' || name.startsWith('@jupyter-widgets/controls')) {
        return controls as any
      }
      if (name === '@jupyter-widgets/base' || name.startsWith('@jupyter-widgets/base')) {
        return base as any
      }
      if (name === '@jupyter-widgets/output' || name.startsWith('@jupyter-widgets/output')) {
        return output as any
      }
      console.error(`[DEBUG] Unknown widget module requested: ${name}`)
      throw new Error(`Unknown widget module requested: ${name}`)
    }

    const manager = new HTMLManager({ 
      loader: (name: string) => {
        return Promise.resolve(resolveModule(name))
      }
    })

    // Pass the full dependency_state wrapper (includes version info)
    await manager.set_state(parsed as any)
    
    let model: any = await (manager as any).get_model(model_id)
    if (!model) {
      console.error('[DEBUG] Model not found for ID:', model_id)
      // Try to wait a bit and retry
      await new Promise(resolve => setTimeout(resolve, 100))
      model = await (manager as any).get_model(model_id)
      if (!model) {
        console.error('[DEBUG] Model still not found after retry')
        return
      }
    }
    
    const view = await manager.create_view(model)
    const existing = widgetContexts.get(props.id)
    const context = existing ? { controls: existing.controls, lastCode: editor.state.doc.toString() } : { controls: {}, lastCode: editor.state.doc.toString() }
    widgetContexts.set(props.id, context)
    attachOutputListeners(model, manager, context)

    if (widgetContainer.value) {
      widgetContainer.value.innerHTML = ''
      await manager.display_view(view, widgetContainer.value)
    } else {
      console.error('[DEBUG] Widget container not available')
    }
  } catch (err) {
    console.error('ipywidgets render error:', err)
    console.error('Error stack:', (err as Error).stack)
    
    // Show error message to user
    if (widgetContainer.value) {
      widgetContainer.value.innerHTML = `
        <div style="padding: 16px; background-color: #fee; border: 1px solid #fcc; border-radius: 4px; color: #c66;">
          <strong>Widget Rendering Error:</strong><br>
          ${(err as Error).message}<br>
          <small>Check the browser console for more details.</small>
        </div>
      `
    }
  }
}
</script>

<template>
  <div ref="anchor" class="wrapper">
    <!-- CodeMirror editor will mount here -->
    <div ref="parent" />
    <button
      v-if="mounted"
      class="run"
      @click="run"
      :disabled="running || !ready"
      :title="buttonText"
    >
      <span class="sr-only">{{ buttonText }}</span>
      <!-- Spinner when running, 'play' icon if ready, etc. -->
      <svg v-if="running" xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24">
        <path fill="currentColor" d="M12 2A10 10 0 1 0 22 12A10 10 0 0 0 12 2Zm0 18a8 8 0 1 1 8-8A8 8 0 0 1 12 20Z" opacity=".5"/>
        <path fill="currentColor" d="M20 12h2A10 10 0 0 0 12 2V4A8 8 0 0 1 20 12Z">
          <animateTransform
            attributeName="transform"
            dur="1s"
            from="0 12 12"
            repeatCount="indefinite"
            to="360 12 12"
            type="rotate"
          />
        </path>
      </svg>
      <svg v-else-if="ready" xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24">
        <path fill="currentColor" d="M8 17.175V6.825q0-.425.3-.713t.7-.287q.125 0 .263.037t.262.113l8.15 5.175q.225.15.338.375t.112.475t-.112.475t-.338.375l-8.15 5.175q-.125.075-.262.113T9 18.175q-.4 0-.7-.288t-.3-.712"/>
      </svg>
      <svg v-else xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24">
        <circle cx="18" cy="12" r="0" fill="currentColor">
          <animate
            attributeName="r"
            begin=".67"
            calcMode="spline"
            dur="1.5s"
            keySplines="0.2 0.2 0.4 0.8;0.2 0.2 0.4 0.8;0.2 0.2 0.4 0.8"
            repeatCount="indefinite"
            values="0;2;0;0"
          />
        </circle>
        <circle cx="12" cy="12" r="0" fill="currentColor">
          <animate
            attributeName="r"
            begin=".33"
            calcMode="spline"
            dur="1.5s"
            keySplines="0.2 0.2 0.4 0.8;0.2 0.2 0.4 0.8;0.2 0.2 0.4 0.8"
            repeatCount="indefinite"
            values="0;2;0;0"
          />
        </circle>
        <circle cx="6" cy="12" r="0" fill="currentColor">
          <animate
            attributeName="r"
            begin="0"
            calcMode="spline"
            dur="1.5s"
            keySplines="0.2 0.2 0.4 0.8;0.2 0.2 0.4 0.8;0.2 0.2 0.4 0.8"
            repeatCount="indefinite"
            values="0;2;0;0"
          />
        </circle>
      </svg>
    </button>
  </div>

  <div class="wrapper">
    <!-- Console-like text output -->
    <div class="output">
      <code v-for="line, i in outputLines" :key="i">
        {{ line }}
        <br v-if="i != outputLines.length - 1">
      </code>
      <input
        v-if="waitingForInput"
        ref="input"
        v-model="inputText"
        @keydown.enter="handleInput"
        type="text"
      />
    </div>

    <!-- Our ECharts-based OutputDisplay component to handle <ECHARTS_DATA> JSON -->
    <OutputDisplay v-if="chartOutput" :output="chartOutput" class="mt-4" />

    <!-- ipywidgets container -->
    <div ref="widgetContainer" class="mt-4" />

    <!-- Reset/Stop button -->
    <button v-if="mounted" class="reset" @click="reset">
      {{ running ? 'stop running' : 'reset editor' }}
    </button>
  </div>
</template>

<style scoped>
div.wrapper {
  position: relative;
  margin: 16px -24px;
}

:deep(.cm-editor) {
  font-size: var(--vp-code-font-size);
  background-color: var(--vp-code-block-bg);
  max-height: v-bind('props.maxHeight');
}

:deep(.cm-editor.cm-focused) {
  outline: 1px solid var(--vp-c-brand-1);
}

:deep(.cm-scroller) {
  scrollbar-width: thin;
  overflow: auto;
}

:deep(.cm-editor .cm-content) {
  font-family: var(--vp-font-family-mono);
  padding: 20px 0;
}

:deep(.cm-editor .cm-gutters) {
  font-family: var(--vp-font-family-mono);
  color: var(--vp-code-line-number-color);
  background-color: var(--vp-code-block-bg);
  border-right: 1px solid var(--vp-code-block-divider-color);
  width: 32px;
  justify-content: center;
  border-top-left-radius: 8px;
  border-bottom-left-radius: 8px;
}

:deep(.cm-editor .cm-gutterElement) {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 0;
  padding: 0;
}

:deep(.cm-editor .cm-line) {
  padding: 0 72px 0 24px;
  line-height: var(--vp-code-line-height);
}

:deep(.cm-editor .cm-activeLine) {
  background-color: var(--vp-code-line-highlight-color);
}

button.run {
  position: absolute;
  top: 12px;
  right: 12px;
  border: 1px solid var(--vp-code-copy-code-border-color);
  border-radius: 4px;
  background-color: var(--vp-code-copy-code-bg);
  width: 40px;
  height: 40px;
  display: flex;
  justify-content: center;
  align-items: center;
  color: var(--vp-c-brand-1);
  z-index: 1;
}

button.run:hover {
  color: var(--vp-c-brand-2);
  background-color: var(--vp-code-copy-code-hover-bg);
  border: 1px solid var(--vp-code-copy-code-hover-border-color);
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
}

div.output {
  background-color: var(--vp-code-block-bg);
  line-height: var(--vp-code-line-height);
  margin-top: -8px;
  padding: 20px 0;
  box-sizing: content-box;
  overflow: auto;
  white-space: nowrap;
}

div.output:has(input:focus) {
  outline: 1px solid var(--vp-c-brand-1);
}

div.output code {
  color: revert;
  background: none;
  width: 100%;
  padding: 0 24px;
  white-space: pre;
  cursor: default;
}

div.output code:last-of-type {
  width: fit-content;
  padding-right: 0;
}

div.output input {
  font-family: var(--vp-font-family-mono);
  font-size: var(--vp-code-font-size);
  box-sizing: content-box;
  padding-right: 24px;
  outline: none;
}

div.output input:only-child {
  padding-left: 24px;
}

button.reset {
  position: absolute;
  top: 2px;
  right: 5px;
  font-size: 12px;
  font-weight: 500;
  padding: 0 3px;
  text-decoration: underline;
  color: var(--vp-c-brand-1);
}

button.reset:hover {
  color: var(--vp-c-brand-2);
}

button:focus-visible {
  outline: revert;
}

@media(min-width: 640px) {
  div.wrapper {
    margin: 16px 0;
  }

  :deep(.cm-editor), div.output {
    border-radius: 8px;
  }
}
</style>
