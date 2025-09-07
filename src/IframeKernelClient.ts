export type ExecHandlers = {
  onStdout?: (s: string) => void
  onStderr?: (s: string) => void
}

export class IframeKernelClient {
  private container: HTMLElement
  private iframe: HTMLIFrameElement | null = null
  private ready = false
  private readyWaiters: Array<() => void> = []
  private pending = new Map<string, { resolve: () => void; reject: (e: any) => void; handlers: ExecHandlers }>()

  constructor(container: HTMLElement) {
    this.container = container
    window.addEventListener('message', this.onMessage)
  }

  private onMessage = (evt: MessageEvent) => {
    if (!this.iframe || evt.source !== this.iframe.contentWindow) return
    const data = evt.data || {}
    const { type, id } = data
    if (type === 'ready') {
      this.ready = true
      this.readyWaiters.splice(0).forEach(fn => fn())
      return
    }
    const req = id ? this.pending.get(id) : undefined
    if (!req) return
    if (type === 'stream') {
      const name = data.name || 'stdout'
      const text = data.text || ''
      if (name === 'stderr') req.handlers.onStderr?.(text)
      else req.handlers.onStdout?.(text)
      return
    }
    if (type === 'status' && data.state === 'idle') {
      req.resolve()
      this.pending.delete(id)
      return
    }
    if (type === 'error') {
      req.reject(new Error(data.evalue || 'Execution error'))
      this.pending.delete(id)
      return
    }
  }

  private ensureIframe() {
    if (this.iframe) return
    this.container.innerHTML = ''
    const iframe = document.createElement('iframe')
    // Load our embed endpoint that boots Pyodide and ipywidgets manager
    const src = new URL(`${import.meta.env.BASE_URL || '/'}jlite/embed.html`, window.location.href)
    iframe.src = src.toString()
    iframe.style.width = '100%'
    iframe.style.height = '420px'
    iframe.style.border = '1px solid var(--vp-c-divider)'
    this.container.appendChild(iframe)
    this.iframe = iframe
  }

  private async waitReady(timeoutMs = 15000) {
    if (this.ready) return
    await new Promise<void>((resolve, reject) => {
      const t = setTimeout(() => reject(new Error('JupyterLite iframe not ready')), timeoutMs)
      this.readyWaiters.push(() => {
        clearTimeout(t)
        resolve()
      })
    })
  }

  async execute(code: string, handlers: ExecHandlers = {}) {
    this.ensureIframe()
    await this.waitReady()
    const id = Math.random().toString(36).slice(2)
    await new Promise<void>((resolve, reject) => {
      this.pending.set(id, { resolve, reject, handlers })
      this.iframe!.contentWindow!.postMessage({ type: 'execute', id, code }, '*')
    })
  }
}
