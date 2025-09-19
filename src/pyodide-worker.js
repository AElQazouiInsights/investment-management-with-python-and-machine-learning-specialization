import { loadPyodide } from 'pyodide';

// Load Pyodide with the specified indexURL
const pyodide = await loadPyodide({ indexURL: "https://cdn.jsdelivr.net/pyodide/v0.28.2/full/" });
const decoder = new TextDecoder();
let initialized = false;

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
try:
    await micropip.install(['tabulate','ipywidgets'], keep_going=True)
    await micropip.install(['traitlets'])
except Exception:
    pass
  `);
  pyodide.runPython(`
import sys
if '/assets' not in sys.path:
    sys.path.append('/assets')
  `);
  initialized = true;
}

onmessage = async (e) => {
  // If buffers are provided for input, assign them and return.
  if (e.data.inputBuffer && e.data.waitBuffer && e.data.interruptBuffer) {
    inputData = new Uint8Array(e.data.inputBuffer);
    waitFlag = new Int32Array(e.data.waitBuffer);
    interruptBuffer = new Uint8Array(e.data.interruptBuffer);
    try { pyodide.setInterruptBuffer?.(interruptBuffer); } catch {}
    return;
  }

  const { id, code, skipWidgetState } = e.data;

  // Set up stdout and stderr to post messages back.
  pyodide.setStdout({
    write: (buf) => {
      const text = decoder.decode(buf)
      if (!text.trim()) return buf.length
      if (/^(Loading|Loaded)\s/.test(text)) return buf.length
      if (text.includes('already loaded from default channel')) return buf.length
      postMessage({ id, output: text })
      return buf.length
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

    pyodide.globals.set('_current_run_id', id);
    pyodide.runPython(`
import js
def _emit_echarts(payload):
    try:
        js.postMessage({"id": _current_run_id, "echart": payload})
    except Exception:
        js.postMessage(payload)
    `);

        // --- Initialize the Widget Manager ---
    // Import the widget manager from Jupyter Widgets HTML manager.
    // This step creates a global widget manager that will automatically render any created widgets.
    // await pyodide.runPythonAsync(`
    //   import ipywidgets as widgets
    //   from jupyterlite import widget_manager
    //   wm = widget_manager.WidgetManager()
    //   `);

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
        
        // First, let's get the widget instance directly
        const widgetInstance = pyodide.runPython(`globals().get('widget_instance', None)`);
        
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
if obj is None:
    try:
        from ipywidgets.widgets import widget as widget_module
        instances = getattr(widget_module, '_instances', {})
        obj = next(reversed(instances.values())) if instances else None
        if obj is not None:
            globals()['widget_instance'] = obj
    except Exception:
        obj = None

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
        // ignore widget serialization errors during normal runs
      }
    }
  } catch (err) {
    postMessage({ id, output: err.message });
  } finally {
    postMessage({ id, done: true });
  }
};

postMessage({ ready: true });
