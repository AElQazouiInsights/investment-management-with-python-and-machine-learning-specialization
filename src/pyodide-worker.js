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

  const { id, code } = e.data;

  // Set up stdout and stderr to post messages back.
  pyodide.setStdout({
    write: (buf) => {
      postMessage({ id, output: decoder.decode(buf) });
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
    try {
      console.log('[DEBUG JS] Starting widget serialization...');
      
      // First, let's get the widget instance directly
      const widgetInstance = pyodide.runPython(`globals().get('widget_instance', None)`);
      console.log('[DEBUG JS] widget_instance from Python:', widgetInstance);
      
      if (!widgetInstance) {
        console.log('[DEBUG JS] No widget_instance found');
        postMessage({ id, output: "[DEBUG] No widget_instance found in Python globals\n" });
        return;
      }
      
      // Get the widget and serialize it in one step
      pyodide.runPython(`
import json
import ipywidgets as widgets
from ipywidgets.embed import dependency_state

# Initialize result variable
_widget_json_result = ""

# Get the widget_instance and extract the actual widget
obj = globals().get('widget_instance', None)
if obj is not None:
    print(f"[DEBUG] Found widget_instance, type: {type(obj)}")
    
    # Handle different types of widget objects
    w = None
    if isinstance(obj, widgets.Widget):
        # Direct widget instance
        w = obj
        print(f"[DEBUG] Direct widget instance")
    elif hasattr(obj, 'widget') and isinstance(obj.widget, widgets.Widget):
        # Interactive widget with .widget attribute
        w = obj.widget
        print(f"[DEBUG] Interactive widget with .widget attribute")
    elif hasattr(obj, 'children'):
        # Look for widgets in children (for interactive objects)
        for child in getattr(obj, 'children', []):
            if isinstance(child, widgets.Widget):
                w = child
                print(f"[DEBUG] Found widget in children: {type(child)}")
                break
    
    if w is not None and isinstance(w, widgets.Widget):
        print(f"[DEBUG] Found widget with ID: {w._model_id}")
        try:
            # Get all widgets (including children) for dependency state
            all_widgets = []
            def collect_widgets(widget):
                all_widgets.append(widget)
                if hasattr(widget, 'children'):
                    for child in widget.children:
                        if isinstance(child, widgets.Widget):
                            collect_widgets(child)
            
            collect_widgets(w)
            print(f"[DEBUG] Collected {len(all_widgets)} widgets for serialization")
            
            st = dependency_state(all_widgets)
            result = json.dumps({'state': st, 'model_id': w._model_id})
            print(f"[DEBUG] Serialized state length: {len(result)}")
            print(f"[DEBUG] JSON preview: {result[:200]}...")
            _widget_json_result = result
            print(f"[DEBUG] Stored result in _widget_json_result")
        except Exception as e:
            print(f"[ERROR] Serialization failed: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"[DEBUG] No valid widget found. Object type: {type(obj)}")
        if hasattr(obj, '__dict__'):
            print(f"[DEBUG] Object attributes: {list(obj.__dict__.keys())}")
else:
    print("[DEBUG] No widget_instance found")
      `);
      
      // Get the result from the global variable
      const stateJSON = pyodide.runPython('_widget_json_result');
      console.log('[DEBUG JS] stateJSON result:', stateJSON, 'type:', typeof stateJSON, 'length:', stateJSON?.length);
      if (stateJSON) {
        // Debug line to help verify widget pipeline
        postMessage({ id, output: "[ipywidgets] state received\n" });
        postMessage({ id, widgetState: stateJSON });
      } else {
        postMessage({ id, output: "[DEBUG] No widget state JSON returned from Python\n" });
      }
    } catch (e) {
      // ignore widget serialization errors
    }
  } catch (err) {
    postMessage({ id, output: err.message });
  } finally {
    postMessage({ id, done: true });
  }
};

postMessage({ ready: true });
