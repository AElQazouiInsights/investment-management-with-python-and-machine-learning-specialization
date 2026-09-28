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
- Numerical checks: Run `python -m unittest discover -s tests -v` from the repository root in a Python environment with NumPy, pandas, SciPy, statsmodels, Matplotlib, and ipywidgets installed. The tests execute the full `docs/1.1-risks.md`, `docs/1.2-optimization.md`, and `docs/1.3-diversification.md` chapters in document order. They cover metrics and bundled data across the existing toolkit copies, constrained optimization, rolling analytics, CPPI accounting, exact/Euler GBM, Monte Carlo breach definitions, and native widget callbacks and serialization.
- Editor persistence: Saved code records the lesson source it was edited from. When that source changes, the current example loads and the old code is preserved locally with a restore option. Same-version edits continue to persist. Python variables belong to the current worker session; reloads require running prerequisite cells again.
- JavaScript checks: Run `node --test tests/test_chart_format.mjs tests/test_editor_state.mjs tests/test_widget_routing.mjs` to check chart number formatting, saved-code migration, streamed output, per-editor widget export, ordered execution, and generated Python arguments.
- Browser regression: Run `python tests/browser_widget_regression.py --base-url http://localhost:5173` against a running VitePress dev server, or run `python tests/browser_widget_regression.py --site-dir .vitepress/dist` after `pnpm build`. Install Playwright and Chromium first with `python -m pip install playwright` and `python -m playwright install chromium`. The test uses real Chromium and Pyodide to check returning-browser saved code, rolling-correlation prerequisites, GBM/CPPI rendering, slider updates, and editor routing. Network access is required for runtime packages; broader layout and performance checks remain separate.
- Chapter chart audit: Run `python tests/browser_chapter_charts.py --base-url http://localhost:5173` to execute all 37 diversification cells and check all 26 charts at 1920, 1440, 390, and 320 pixels. It checks measured axes and legends, wrapping headers, canvas sizes, page overflow, and tooltip units. Add `--screenshots /tmp/opencode/chapter-charts` for visual inspection, or `--chapter 1.2-optimization` to check the shared renderer against portfolio/frontier charts.
