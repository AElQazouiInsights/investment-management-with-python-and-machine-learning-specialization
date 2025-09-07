# Investment Management with Python & Machine Learning Specialization

After earning a specialization in **Investment Management with Python and Machine Learning** from EDHEC Business School ([**`Credential ID: WUTZABL42PW8`**](https://www.coursera.org/account/accomplishments/specialization/WUTZABL42PW8)), I compiled key financial and mathematical concepts into a Python module. This project is documented in Jupyter notebooks and here on Vitepress.

The main goal of this project is to provide an accessible, structured, and practical approach to modern investment strategies and portfolio management techniques. It aims to bridge the gap between academic theory and real-world application, enabling users—from students to professional investors—to implement and test various investment strategies using Python.

The content spans several core areas:

- **Fundamental Analysis**: Introducing basic concepts such as returns calculations and risk assessments.
- **Quantitative Methods**: Covering advanced statistical and mathematical techniques to optimize portfolios and manage risks effectively.
- **Machine Learning Applications**: Demonstrating how machine learning can be applied to enhance predictive accuracy in investment decisions.
- **Interactive Learning**: Each module includes interactive Jupyter notebooks that allow users to experiment with real data, tweak parameters, and observe the outcomes in real-time.

This educational toolkit is not just a passive learning resource but an active framework for engaging with and mastering the complexities of financial markets through technology.

## Developer Notes

- Pyodide: The site runs Python in-browser via Pyodide `v0.28.2`. For performance and reliability, packages are initialized once per session in the web worker.
- Running locally: Use `pnpm` (`pnpm dev`, `pnpm build`, `pnpm preview`). Headers for SharedArrayBuffer are already configured.
- Charts: ECharts data is emitted by printing a single line starting with `<ECHARTS_DATA>` followed by JSON. `OutputDisplay.vue` renders this.
- ipywidgets: Create a widget and either assign it to `widget_instance` or rely on auto-detection. Example:
  - `import ipywidgets as widgets`  
    `widget_instance = widgets.IntSlider(description='x', value=42)`
- Data: Public datasets are served from `public/assets/data/` and mounted into the Pyodide FS at `/assets/data/`.
- Versions: Keep `echarts@^5.5.x` with `vue-echarts@7.x`. Avoid broad auto-upgrades; pin critical deps.
