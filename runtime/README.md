# Browser Python runtime

Python executes in a module Web Worker on the visitor's machine. Cloudflare serves static content; it does not execute Python. The published site contains the WebAssembly runtime, Python standard library, scientific packages, widget wheels, JavaScript, CSS, toolkit, and lesson data.

## Why initialization previously failed

The first cell used to run unpinned `micropip.install(['tabulate', 'ipywidgets'])`. Neither package was in the Pyodide distribution, so initialization depended on browser access to PyPI metadata and wheel hosts. A failed resolution stopped every cell before the user's code ran. Compatible pure-Python wheels exist; the reported error alone does not identify whether a corporate proxy, browser policy, or another network failure blocked them. The work-laptop network has not been inspected.

`tabulate` is unused and has been removed. `ipywidgets` is required by the interactive lessons and worker serialization. Its dependencies are retained. Scientific packages use the versions built for the selected Pyodide ABI, rather than incompatible native PyPI binaries.

## Reproducible preparation

```sh
pnpm install --frozen-lockfile
pnpm build
pnpm preview
```

`pnpm dev` and `pnpm build` run `scripts/prepare-pyodide.mjs` first. It copies the runtime from the exactly pinned npm package and downloads only the dependency closure in `runtime/pyodide-lock.json`. Every wheel is checked against its committed SHA-256; an invalid download fails preparation. Existing local assets are verified before reuse. Source wheel URLs are recorded in the committed lockfile, but stripped from the published lockfile.

Generated binaries live in `docs/public/pyodide/<version>/<lock-revision>/` and are ignored by Git. A content-derived revision changes the URL whenever the locked dependency set changes, preventing old browser/CDN manifests from being mixed with a new build. VitePress includes these assets in the deployment output. The current runtime payload is approximately 56 MiB, with no single runtime file above 14 MiB. The build machine needs upstream access on first preparation; visitors need access only to the website. Building from a clean checkout does not require previously cached wheels.

There is no runtime package resolution, CDN fallback, or installation via micropip. `loadPackage()` uses the same-origin manifest and verifies wheel integrity. Lesson-file and dependency failures are surfaced instead of silently allowing partial initialization.

## Updating versions

1. Check stable releases, then update the exact Pyodide pin in `package.json` and `runtime/config.json` together.
2. Update the widget wheel versions in `runtime/config.json`. Review their published `Requires-Dist` metadata, including any new dependencies, before changing the explicit dependency lists.
3. Run `pnpm install`, then `pnpm runtime:update`. This deliberately refreshes the runtime lockfile from the installed Pyodide distribution and the pinned PyPI wheel metadata.
4. Review both lockfile diffs and run the numerical, browser, and JavaScript checks before deployment. Commit source/configuration and lockfiles; publish the generated build output.

The standard preparation/build command never selects newer versions or rewrites the committed runtime lockfile. Replacing a Python minor version requires matching WebAssembly wheels. The current scientific versions are NumPy 2.4.6, pandas 3.0.2, SciPy 1.18.0, statsmodels 0.14.6, and Matplotlib 3.10.8; ipywidgets is 8.1.9.

## Deployment

The live site uses the Git-connected Cloudflare Pages project `investment-management-with-python-and-machine-learning`. The production branch is `production`; pushes to `uat` create branch previews. Build with `pnpm build` and publish `.vitepress/dist`, including `pyodide/`; `_headers` supplies COOP/COEP. Keep `pnpm-lock.yaml` as the only package-manager lockfile so CI uses the pinned dependency graph.

The repository also retains a legacy GitHub Pages deployment script and `cloudflare-worker.js`. They are not the current production deployment path. If that legacy proxy is used, it preserves the origin's HTTP status, content types, cache headers, and query strings while adding isolation headers; GitHub Pages does not interpret `_headers` itself.

Keep `Cross-Origin-Opener-Policy: same-origin` and `Cross-Origin-Embedder-Policy: require-corp` on page responses. The WASM response must preserve its `application/wasm` content type; missing files must remain non-200 responses. The proxy contains no Python execution or package resolution and needs no additional backend service.

After deployment, run the browser checks against the public URL too. A network must still allow the site and WebAssembly execution; self-hosting cannot override corporate policies that explicitly block either. Offline here means independence from third-party runtime hosts, not access to an unvisited website without an internet connection.

## Validation

```sh
node --test tests/test_*.mjs
python -m unittest discover -s tests -v
python -m playwright install chromium firefox
python tests/browser_runtime_loading.py --site-dir .vitepress/dist
python tests/browser_chapter_charts.py --site-dir .vitepress/dist --chapter 1.2-optimization
python tests/browser_chapter_charts.py --site-dir .vitepress/dist --chapter 1.2-optimization --browser firefox
python tests/browser_widget_regression.py --site-dir .vitepress/dist
```

Install Playwright in the test Python environment. Numerical tests also require the scientific packages and ipywidgets; use the versions above when checking the runtime upgrade. The browser checks execute the actual Python 3.14 WebAssembly packages.

The runtime check verifies the running Python/Pyodide/package versions, observes every required runtime and wheel download, imports the toolkit, checks a worked calculation, and exports widget state in Chromium and Firefox. Both it and the chapter audit create fresh browser contexts, block service workers, disable the HTTP cache through request routing, and reject every off-origin request. The chapter audit executes every cell in order and checks chart rendering at desktop/mobile widths. Use `--chapter` for the other chapters or `--base-url` to test the deployed website. The widget suite also simulates a missing runtime and an HTTP 503 wheel failure, verifying visible errors and successful dependency retry.

### Upgrade validation — 2026-10-29

- Production build and frozen-lockfile installation passed; all 31 published wheel hashes were verified.
- All 432 numerical tests passed in native Python 3.12 with the distribution's scientific-package versions. All 35 JavaScript tests passed, including proxy status/header preservation.
- Cold runtime checks passed in Chromium 156 and Firefox 157, running Python 3.14.2 and the exact locked package versions. Every required runtime/wheel file was requested from the site, with off-origin requests blocked.
- Both browsers executed all 20 optimization cells and rendered all 15 charts at 1920, 1440, 390, and 320 pixels. The broader Chromium audit passed 244 runnable cells and 115 charts across the eight teaching chapters.
- Widget controls, storage recovery, unavailable-runtime handling, HTTP 503 dependency retry, Unicode input, cancellation, and navigation checks passed across the full regression run and targeted reruns.

The SciPy upgrade exposed a finite-difference SLSQP failure on one branch of a two-asset exact-volatility problem. The toolkit now supplies analytical gradients and expresses that positive-volatility constraint as the equivalent variance equality. Existing closed-form tests and a real WebAssembly check verify that the higher-return feasible branch is retained; failed solver results are still rejected.

These are local validation results. The updated build has not been deployed or tested on the user's corporate laptop. Public-origin response headers were checked, but they do not establish that the new assets are deployed or that every corporate policy permits the site.
