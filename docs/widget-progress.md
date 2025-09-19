# GBM Widget Integration Notes

## Status

- **Streaming helper**: `PortfolioOptimizationKit.show_gbm_echart` now emits `<ECHARTS_DATA>` JSON (mirrored across assets/public/docs/data copies) so the GBM example renders with ECharts instead of Matplotlib when running in the browser.
- **Docs**: the diversification chapter calls `pok.show_gbm_echart`, keeping the Matplotlib version for notebooks but wiring the interactive block to the streaming helper.
- **Worker**: Pyodide pre-installs the required packages, exposes a lightweight `_emit_echarts` hook, filters load-time chatter, and serialises widget state once per run (skipping it on slider-driven updates so the widget tree no longer regenerates in a loop).
- **Front-end**: the editor strips debug logging, attaches value listeners to slider/dropdown models, throttles reruns, and pushes trimmed `<ECHARTS_DATA>` payloads straight into `updateOutput`, giving instant chart refreshes without duplicate output widgets or console noise.

Moving any control now re-runs `pok.show_gbm_echart(...)` under the hood and refreshes the chart in place.

## Open items

- If further widgets adopt the same pattern, factor the shared code (context management, debounce, `_emit_echarts`) into a small utility.
- Confirm we leave no residual debug lines before shipping (current console output is clean, but worth re-checking when new helpers land).
