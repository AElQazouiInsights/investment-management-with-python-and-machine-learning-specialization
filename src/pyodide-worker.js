import { loadPyodide } from 'pyodide';

// Load Pyodide with the specified indexURL
const pyodide = await loadPyodide({ indexURL: "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/" });
const decoder = new TextDecoder();

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

onmessage = async (e) => {
  // If buffers are provided for input, assign them and return.
  if (e.data.inputBuffer && e.data.waitBuffer && e.data.interruptBuffer) {
    inputData = new Uint8Array(e.data.inputBuffer);
    waitFlag = new Int32Array(e.data.waitBuffer);
    interruptBuffer = new Uint8Array(e.data.interruptBuffer);
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

  // Load required packages.
  try {
    await pyodide.loadPackage([
      "pandas",
      "numpy",
      "scipy",
      "statsmodels",
      "matplotlib",
      "micropip",
    ]);

    // Install additional packages
    await pyodide.runPythonAsync(`
      import micropip
      await micropip.install([
      'tabulate',
      'ipywidgets',
      'yfinance'
      ])
    `);
    
    // Add /assets to sys.path so custom modules can be imported.
    pyodide.runPython(`
      import sys
      sys.path.append('/assets')
    `);

        // --- Initialize the Widget Manager ---
    // Import the widget manager from Jupyter Widgets HTML manager.
    // This step creates a global widget manager that will automatically render any created widgets.
    // await pyodide.runPythonAsync(`
    //   import ipywidgets as widgets
    //   from jupyterlite import widget_manager
    //   wm = widget_manager.WidgetManager()
    //   `);

    // Execute the provided code.
    await pyodide.runPythonAsync(code);
    
    // OPTIONAL: Try to capture widget HTML if a widget was created.
    // ipywidgets in Pyodide don't automatically render, so you might want to call _repr_html_().
    let widgetHTML = "";
    try {
      // Assumes that your code stored the widget in a global variable "widget_instance"
      widgetHTML = pyodide.runPython(`widget_instance._repr_html_()`);
    } catch (err) {
      widgetHTML = "";
    }
    if (widgetHTML) {
      postMessage({ id, widgetHTML });
    }
  } catch (err) {
    postMessage({ id, output: err.message });
  } finally {
    postMessage({ id, done: true });
  }
};

postMessage({ ready: true });
