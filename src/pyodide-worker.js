import { loadPyodide } from 'pyodide';
import { receiveInput } from './editor-input.js';
import runtime from '../runtime/config.json';
import { revision, packages } from '../runtime/pyodide-lock.json';

const siteURL = new URL(import.meta.env.BASE_URL, self.location.origin);
const indexURL = new URL(`pyodide/${runtime.version}/${revision.slice(0, 12)}/`, siteURL).href;
let pyodide;
try {
  pyodide = await loadPyodide({ indexURL });
} catch (error) {
  throw new Error(`Python runtime could not load from ${indexURL}. Reload the page; if it persists, report this URL and check that WebAssembly is allowed. ${error.message}`);
}
let initialized = false;
let executionQueue = Promise.resolve();
const pendingRequests = new Set();

let inputData = null;
let waitFlag = null;
let interruptBuffer = null;

const filesToMount = [
  {
    url: '/assets/data/brka_d_ret.csv',
    path: '/assets/data/brka_d_ret.csv',
    type: 'text'
  },
  {
    url: '/assets/data/F-F_Research_Data_Factors_m.csv',
    path: '/assets/data/F-F_Research_Data_Factors_m.csv',
    type: 'text'
  },
  {
    url: '/assets/data/ind49_m_vw_rets.csv',
    path: '/assets/data/ind49_m_vw_rets.csv',
    type: 'text'
  },
  {
    url: '/assets/data/ind49_m_nfirms.csv',
    path: '/assets/data/ind49_m_nfirms.csv',
    type: 'text'
  },
  {
    url: '/assets/data/ind49_m_size.csv',
    path: '/assets/data/ind49_m_size.csv',
    type: 'text'
  },
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
    const url = new URL(file.url.slice(1), siteURL);
    const response = await fetch(url, { signal: AbortSignal.timeout(60000) }).catch(error => {
      throw new Error(`Failed to fetch ${url}: ${error.message}`);
    });
    if (!response.ok) throw new Error(`Failed to fetch ${url} (HTTP ${response.status})`);
    const content = await response.text();
    
    const dir = file.path.split('/').slice(0, -1).join('/');
    if (dir) pyodide.FS.mkdirTree(dir);
    
    pyodide.FS.writeFile(file.path, content);
  }));
} catch (error) {
  throw new Error(`Python lesson files could not load. Reload the page; if it persists, report the failed URL. ${error.message}`);
}

async function ensureInitialized() {
  if (initialized) return;
  try {
    const failures = [];
    await pyodide.loadPackage(runtime.packages, {
      errorCallback: message => failures.push(message),
      checkIntegrity: true,
    });
    if (failures.length) {
      const missing = Object.entries(packages).filter(([name]) => !pyodide.loadedPackages[name]);
      // Fetch integrity failures hide the HTTP status; inspect only failed assets.
      const details = await Promise.all(missing.map(async ([, pkg]) => {
        const url = new URL(pkg.file_name, indexURL).href;
        try {
          const response = await fetch(url, { method: 'HEAD', signal: AbortSignal.timeout(5000) });
          return `${url} (HEAD HTTP ${response.status}; package download or integrity check failed)`;
        } catch (error) {
          return `${url}: ${error.message}`;
        }
      }));
      throw new Error([...failures, ...details].join('\n'));
    }
    pyodide.runPython(`
import sys
if '/assets' not in sys.path:
    sys.path.append('/assets')
import numpy, pandas, scipy, statsmodels, matplotlib, ipywidgets, PortfolioOptimizationKit
    `);
  } catch (error) {
    throw new Error(`Python dependencies could not load from ${indexURL}. Retry the cell or reload the page. If it persists, report the failed URL and status to the site administrator. ${error.message}`);
  }
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
      const inputText = receiveInput(inputData, waitFlag, interruptBuffer);
      pyodide.checkInterrupt();
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

    // The timer handles yielding code; synchronous Python can still be stopped
    // through the shared interrupt buffer written by the UI.
    const TIMEOUT_MS = 15000;
    let timer = null;
    try {
      timer = setTimeout(() => {
        try { if (interruptBuffer) interruptBuffer[0] = 2; } catch {}
        postMessage({ id, output: "\n[Execution timed out]\n" });
      }, TIMEOUT_MS);
      // Catch cancellation before KeyboardInterrupt reaches asyncio's task boundary.
      // Evaluate the original source separately to retain top-level await, globals,
      // future imports, and its own line numbers without indenting user code.
      pyodide.globals.set('_editor_source', code);
      await pyodide.runPythonAsync(`
from pyodide.code import eval_code_async as _editor_eval_code_async
try:
    await _editor_eval_code_async(_editor_source, globals(), filename="<editor>")
except KeyboardInterrupt:
    print("\\n[Execution interrupted]")
      `);
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
    # Python and JavaScript widget defaults can differ (e.g. FloatSlider.step).
    st = dependency_state(all_widgets, drop_defaults=False)
    callback = getattr(w, 'f', None)
    if callable(callback):
        st[w._model_id]['state']['_echarts_callback'] = (
            getattr(callback, '__name__', '')
            if getattr(callback, '__module__', '') == 'PortfolioOptimizationKit' else ''
        )
    if isinstance(getattr(w, 'kwargs', None), dict):
        st[w._model_id]['state']['_echarts_kwargs'] = {
            key: value for key, value in w.kwargs.items()
            if value is None or isinstance(value, (str, int, float, bool))
        }
    for widget in all_widgets:
        parameter = getattr(widget, '_kwarg', None)
        if isinstance(parameter, str):
            st[widget._model_id]['state']['_echarts_parameter'] = parameter
        if isinstance(widget, widgets.Dropdown):
            st[widget._model_id]['state']['_echarts_option_values'] = list(widget._options_values)
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
