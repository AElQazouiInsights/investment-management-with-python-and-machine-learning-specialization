import { loadPyodide } from 'pyodide';

// Load Pyodide with the specified indexURL
const pyodide = await loadPyodide({ indexURL: "https://cdn.jsdelivr.net/pyodide/v0.28.2/full/" });
const decoder = new TextDecoder();
let initialized = false;
let executionQueue = Promise.resolve();
const pendingRequests = new Set();

let inputData = null;
let waitFlag = null;
let interruptBuffer = null;

const filesToMount = [
  {
    url: '/assets/PortfolioOptimizationKit.py',
    path: '/assets/PortfolioOptimizationKit.py',
    type: 'text'
  },
  {
    url: '/assets/data/Portfolios_Formed_on_ME_monthly_EW.csv',
    path: '/assets/data/Portfolios_Formed_on_ME_monthly_EW.csv',
    type: 'text'
  },
  {
    url: '/assets/data/edhec-hedgefundindices.csv',
    path: '/assets/data/edhec-hedgefundindices.csv',
    type: 'text'
  },
  {
    url: '/assets/data/stocks_dynamic.csv',
    path: '/assets/data/stocks_dynamic.csv',
    type: 'text'
  },
  {
    url: '/assets/data/ind30_m_ew_rets.csv',
    path: '/assets/data/ind30_m_ew_rets.csv',
    type: 'text'
  },
  {
    url: '/assets/data/ind30_m_nfirms.csv',
    path: '/assets/data/ind30_m_nfirms.csv',
    type: 'text'
  },
  {
    url: '/assets/data/ind30_m_size.csv',
    path: '/assets/data/ind30_m_size.csv',
    type: 'text'
  },
  {
    url: '/assets/data/ind30_m_vw_rets.csv',
    path: '/assets/data/ind30_m_vw_rets.csv',
    type: 'text'
  },
  {
    url: '/assets/data/ind49_m_ew_rets.csv',
    path: '/assets/data/ind49_m_ew_rets.csv',
    type: 'text'
  }
];

try {
  await Promise.all(filesToMount.map(async file => {
    const response = await fetch(file.url);
    if (!response.ok) throw new Error(`Failed to fetch ${file.url}`);
    const content = await response.text();
    
    const dir = file.path.split('/').slice(0, -1).join('/');
    if (dir) pyodide.FS.mkdirTree(dir);
    
    pyodide.FS.writeFile(file.path, content);
  }));
} catch (error) {
  console.error("Error mounting files:", error);
}

async function ensureInitialized() {
  if (initialized) return;
  await pyodide.loadPackage([
    "pandas",
    "numpy",
    "scipy",
    "statsmodels",
    "matplotlib",
    "micropip",
  ]);
  await pyodide.runPythonAsync(`
import micropip
await micropip.install(['tabulate','ipywidgets'], keep_going=True)
await micropip.install(['traitlets'])
  `);
  pyodide.runPython(`
import sys
if '/assets' not in sys.path:
    sys.path.append('/assets')
  `);
  initialized = true;
}

onmessage = (e) => {
  // If buffers are provided for input, assign them and return.
  if (e.data.inputBuffer && e.data.waitBuffer && e.data.interruptBuffer) {
    inputData = new Uint8Array(e.data.inputBuffer);
    waitFlag = new Int32Array(e.data.waitBuffer);
    interruptBuffer = new Uint8Array(e.data.interruptBuffer);
    try { pyodide.setInterruptBuffer?.(interruptBuffer); } catch {}
    return;
  }

  if (e.data.cancel) {
    for (const request of pendingRequests) {
      if (request.id === e.data.cancel) request.cancelled = true;
    }
    return;
  }
  if (typeof e.data.id !== 'string' || typeof e.data.code !== 'string') return;
  const request = { ...e.data };
  pendingRequests.add(request);
  const execution = executionQueue.then(async () => {
    pendingRequests.delete(request);
    if (request.cancelled) {
      postMessage({ id: request.id, done: true });
      return;
    }
    await execute(request);
  });
  executionQueue = execution.catch(error => {
    postMessage({ id: request.id, error: true, output: error.message, done: true });
  });
  return execution;
};

async function execute({ id, code, skipWidgetState }) {
  if (interruptBuffer) interruptBuffer[0] = 0;
  postMessage({ id, started: true });
  const outputDecoder = new TextDecoder();
  const errorDecoder = new TextDecoder();
  // Install output handlers only when this request owns the Python session.
  pyodide.setStdout({
    write: (buf) => {
      const text = outputDecoder.decode(buf, { stream: true })
      if (!text) return buf.length
      if (/^(Loading|Loaded)\s/.test(text)) return buf.length
      if (text.includes('already loaded from default channel')) return buf.length
      postMessage({ id, output: text })
      return buf.length
    },
  });
  pyodide.setStderr({
    write: (buf) => {
      const text = errorDecoder.decode(buf, { stream: true });
      if (text) postMessage({ id, error: true, output: text });
      return buf.length;
    },
  });

  pyodide.setStdin({
    stdin: () => {
      postMessage({ id, input: true });
      Atomics.wait(waitFlag, 0, 0);
      const inputArray = new Uint8Array(Atomics.load(inputData, 0));
      for (let i = 0; i < inputArray.length; i++) {
        inputArray[i] = Atomics.load(inputData, i + 1);
      }
      const inputText = decoder.decode(inputArray);
      postMessage({ id, output: `${inputText}\n` });
      return inputText;
    },
  });

  // Load required packages once, then run code.
  try {
    await ensureInitialized();

    // Only widgets exported by this editor run should be serialized below.
    // Slider-only updates retain the existing control object.
    if (!skipWidgetState) pyodide.runPython('widget_instance = None');

    pyodide.globals.set('_current_run_id', id);
    pyodide.runPython(`
import js
from pyodide.ffi import to_js
def _emit_echarts(payload):
    # postMessage needs a cloneable JavaScript object, not a Python dict proxy.
    js.postMessage(to_js({"id": _current_run_id, "echart": payload}, dict_converter=js.Object.fromEntries))
    `);

    // Execute the provided code with a timeout and interrupt fallback
    const TIMEOUT_MS = 15000;
    let timer = null;
    try {
      timer = setTimeout(() => {
        try { if (interruptBuffer) interruptBuffer[0] = 2; } catch {}
        postMessage({ id, output: "\n[Execution timed out]\n" });
      }, TIMEOUT_MS);
      await pyodide.runPythonAsync(code);
    } finally {
      if (timer) clearTimeout(timer);
    }
    
    // Serialize a widget instance (if provided by user code) and post its state
    if (!skipWidgetState) {
      try {
        
        // Query a boolean rather than retaining an unused widget PyProxy.
        const widgetInstance = pyodide.runPython(`globals().get('widget_instance', None) is not None`);
        
      if (!widgetInstance) {
        return;
      }
      
      // Get the widget and serialize it in one step
      pyodide.runPython(`
import json
import ipywidgets as widgets
from ipywidgets.embed import dependency_state

_widget_json_result = ""
obj = globals().get('widget_instance', None)

w = None
if isinstance(obj, widgets.Widget):
    w = obj
elif hasattr(obj, 'widget') and isinstance(obj.widget, widgets.Widget):
    w = obj.widget
elif hasattr(obj, 'children'):
    for child in getattr(obj, 'children', []):
        if isinstance(child, widgets.Widget):
            w = child
            break

if w is not None:
    all_widgets = []
    def collect(widget):
        all_widgets.append(widget)
        for child in getattr(widget, 'children', []):
            if isinstance(child, widgets.Widget):
                collect(child)
    collect(w)
    st = dependency_state(all_widgets)
    _widget_json_result = json.dumps({
        'version_major': 2,
        'version_minor': 0,
        'state': st,
        'model_id': w._model_id
    })
else:
    _widget_json_result = ""
      `);
      
      // Get the result from the global variable
      const stateJSON = pyodide.runPython('_widget_json_result');
      if (stateJSON) {
        postMessage({ id, widgetState: stateJSON });
      }
      } catch (e) {
        postMessage({ id, error: true, output: `Widget serialization failed: ${e.message}\n` });
      }
    }
  } catch (err) {
    postMessage({ id, error: true, output: err.message });
  } finally {
    postMessage({ id, done: true });
  }
}

postMessage({ ready: true });
