# Courses 3 and 4: implementation roadmap

## Current state

Courses 1 and 2 have developed lessons. Chapter 2.3 now introduces mean uncertainty, equal-return and equal-Sharpe shrinkage targets, and factor-based expected returns before Black–Litterman. Chapter 2.5 is an original portfolio capstone.

`docs/3.0-overview.md` and `docs/4.0-overview.md` provide student-facing preparation and the planned learning sequences. The nine lessons below are not implemented yet. Add navigation links when their pages are ready, rather than publishing empty chapter pages.

## Delivery sequence

The topic mapping follows the official [Course 3](https://www.coursera.org/learn/python-machine-learning-for-investment-management) and [Course 4](https://www.coursera.org/learn/machine-learning-asset-management-alternative-data) syllabi checked on 2026-10-29. Filenames and experiments below are this website's implementation plan.

| Planned file in `docs/` | Core teaching question | Data / computational foundation | Chart and interaction |
| --- | --- | --- | --- |
| `3.1-ml-fundamentals.md` | Does a fitted relationship generalize? | Seeded small synthetic example, explicit baseline and chronological splits; validate scikit-learn in Pyodide before use | Fit and error curves; model-complexity control |
| `3.2-regularized-factors.md` | How does regularization stabilize factor estimates? | Reuse documented factor/industry data where appropriate; distinguish contemporaneous explanation from forecasting; training-only scaling and tuning | Coefficient paths and validation error; LASSO/Elastic Net penalty |
| `3.3-learned-diversification.md` | What dependence structure supports diversification? | Common-date return panel; clustering, precision matrices and graphical lasso | Correlation heatmap and sparse graph; sparsity control |
| `3.4-regime-analysis.md` | What changes when risk and return depend on regimes? | Clearly labeled synthetic scenarios followed by a dated historical example; separate retrospective smoothing from causal estimation | Regime overlays and scenario paths; filtering/scenario controls |
| `3.5-recession-prediction.md` | Can available features predict a specified event? | Dated predictors and event labels with publication/revision policy; chronological classifier comparison and feature selection | Probabilities, confusion matrix and ROC; threshold control |
| `4.1-consumption.md` | What does observed activity actually measure? | Small documented activity snapshot; coverage/cohort and seasonality calculations | Activity lines and seasonal heatmap; aggregation window |
| `4.2-text-analysis.md` | How do words become comparable numerical features? | Tiny transparent corpus first, then a permitted document snapshot; training-only vocabulary/IDF for predictive work | Term-weight bars and similarity heatmap; preprocessing selection |
| `4.3-corporate-filings.md` | What do reported text and holdings reveal, and when? | Permitted 10-K and 13-F snapshots with report, publication and amendment dates; entity mapping | Similarity, sentiment and overlap charts; document/institution selection |
| `4.4-media-networks.md` | What relationship does a media signal or graph measure? | Documented permitted media snapshot or explicitly synthetic teaching records; dated aggregation and explicit edge meaning | Sentiment lines and company graph; time window/edge threshold |

## Lesson construction contract

Follow the [teaching standard for all chapters](TEACHING_GUIDE.md): financial question → small numerical example → worked calculation → explained graph → Python → focused experiment → exercise with feedback. Introduce each term and symbol before use, and explain units, horizons, indexes, baseline, and information timing beside the example. Use existing typography, layout, Editor and OutputDisplay components.

- Use a unique, descriptive Editor ID for each Python cell. Run a chapter from a fresh worker in document order; make independent widgets self-contained.
- Keep financial logic in visible cells when it is short. Extract a toolkit helper only when reuse or a widget callback justifies it. Changes to `PortfolioOptimizationKit.py` must be synchronized with its five distributed copies and checked by the existing parity tests.
- Print `<ECHARTS_DATA>` followed by finite JSON from the same arrays used for numerical tables. Preserve dates, asset order, missing-data semantics, and percent versus percentage-point units.
- Add ipywidgets only where changing an assumption answers a specific question. Route callbacks through the existing allowlist in `src/widget-controls.js`; verify the exported callback identity, argument binding, repeated updates, and cleanup on rerun/navigation.
- Distinguish fitting, model selection, and final evaluation. Fit imputers, scalers, vocabulary, IDF and feature selectors on each training block only. Explain label availability and gaps for overlapping forecast horizons.
- Report prediction metrics separately from portfolio results. Portfolio evaluation must specify constraints, signal lag, rebalancing, turnover, and costs.

## Runtime and chart dependencies

The current pinned runtime requests NumPy, pandas, SciPy, statsmodels, Matplotlib and ipywidgets. It does not yet request scikit-learn. When implementing 3.1, validate a compatible scikit-learn package and its dependency closure using `runtime/config.json`, `scripts/prepare-pyodide.mjs`, and the process in `runtime/README.md`. Exercise fit/predict and the intended preprocessing in the actual browser worker, then self-host checksum-verified assets. Document cold-load impact. Keep execution client-side.

Reference notebooks import desktop libraries including CVXPY, XGBoost and Folium. For each lesson, verify package support and cost before selecting an implementation. Use browser-compatible formulations where appropriate and explain any change in mathematical objective or model family. A simpler model is not an equivalent implementation merely because it produces a similar chart.

`src/OutputDisplay.vue` currently supports line, bar and scatter payloads. Before 3.3, extend the shared payload handling and ECharts registrations for heatmaps and graph series with explicit axis/category and node/edge semantics. Test responsive layout, color scales, labels, and tooltip values. Add geographic support only for an example that needs it. Avoid dormant renderer branches for charts no lesson exercises.

## Dataset contract

Each new snapshot should have a companion data dictionary recording source URL, attribution and reuse terms, retrieval/version date, observation dates, available-at dates (or explicit timing assumptions), identifiers, units, timezone, missing values, transformations, and any synthetic construction/seed. Preserve historical vintages when the exercise claims point-in-time evaluation; otherwise label the analysis as retrospective.

Serve approved snapshots from `public/assets/data/`, mount required files through the existing worker data-loading path, and maintain native/browser fixture parity. Verify this path rather than assuming every public file is mounted automatically. Students should be able to run lessons without credentials, live scraping, or third-party requests. Keep datasets small enough for the browser and retain only fields the example needs.

## Acceptance checks for each delivered chapter

1. Execute all source cells in order and compare the worked answers with an independent calculation or invariant. For learned models, check split timing, training-only transformations, baseline behavior, and evaluation metrics.
2. Reconcile chart series with computed results, including labels, units, dates, and documented rounding. Check widget endpoints and meaningful parameter changes.
3. Run `pnpm build`, then the chapter/browser checks in fresh Chromium and Firefox contexts with empty caches and off-site requests blocked. Check desktop and narrow mobile layouts, mathematical rendering, widget updates, and navigation.
4. Run measured axis/legend checks against the dev server separately from the build. Avoid building while browser audits use the dev server.
5. Update the course overview, sidebar, README counts and chapter-audit registry only for delivered content. Record exactly which browser/package combinations were verified.

## Companion references

- [PeterSchuld / EDHEC_Investment-Management-with-Python-and-Machine-Learning-](https://github.com/PeterSchuld/EDHEC_Investment-Management-with-Python-and-Machine-Learning-): verified notebook directories across all four courses, including Course 3 Module 5 and Course 4 consumption, text mining, 10-K, 13F and network notebooks.
- [z4ir3 / finance-courses](https://github.com/z4ir3/finance-courses): useful Course 1–2 references and Course 3 weeks 2, 4 and 5. Course 2 week 3 develops the expected-return targets that precede Black–Litterman.

Use these to cross-check coverage and methods. Explicit repository reuse licenses were not established during the audit; write original explanations and implementations and establish permissions for any reused notebook or dataset. The website's worked examples and validation remain the source of truth for its behavior.
