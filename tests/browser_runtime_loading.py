"""Verify actual runtime versions and cold same-origin downloads in two browsers."""

import argparse
import functools
import http.server
import json
from pathlib import Path
import threading
from urllib.parse import unquote, urlsplit

from playwright.sync_api import sync_playwright
from browser_widget_regression import IsolatedSiteHandler


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / 'runtime/config.json').read_text())
LOCK = json.loads((ROOT / 'runtime/pyodide-lock.json').read_text())


def verify(base_url, browser_name):
    with sync_playwright() as playwright:
        browser = getattr(playwright, browser_name).launch()
        context = browser.new_context(service_workers='block')
        requests, external = set(), []

        def route_request(route):
            url = urlsplit(route.request.url)
            if url[:2] != urlsplit(base_url)[:2]:
                external.append(route.request.url)
                route.abort()
            else:
                requests.add(unquote(url.path).rsplit('/', 1)[-1])
                route.continue_()

        context.route('**/*', route_request)
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.add_init_script('''
            window.runtimeMessages = [];
            const NativeWorker = window.Worker;
            window.Worker = class extends NativeWorker {
                constructor(...args) {
                    super(...args);
                    window.runtimeWorker = this;
                    this.addEventListener('message', event => window.runtimeMessages.push(event.data));
                }
            };
        ''')
        page.goto(f'{base_url}/1.2-optimization.html', wait_until='domcontentloaded')
        page.wait_for_function('window.runtimeMessages.some(message => message.ready)', timeout=120000)
        expected = {name: LOCK['packages'][name]['version'] for name in CONFIG['packages']}
        code = f'''
import sys, json, pyodide, importlib.metadata
import PortfolioOptimizationKit as pok
import ipywidgets as widgets
import numpy as np
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error
assert pyodide.__version__ == {CONFIG['version']!r}
assert sys.version.split()[0] == {LOCK['info']['python']!r}
expected = {expected!r}
actual = {{name: importlib.metadata.version(name) for name in expected}}
assert actual == expected, actual
assert abs(pok.portfolio_return([0.6, 0.4], [0.08, 0.12]) - 0.096) < 1e-12
covariance = np.array([[0.01, 0.005], [0.005, 0.04]])
roots = np.roots([0.04, -0.07, 0.04 - 0.099 ** 2])
weights = pok.maximize_sharpe_ratio(np.array([0.12, 0.08]), covariance, 0.0, 1, 0.099)
np.testing.assert_allclose(weights, [roots.max(), 1 - roots.max()], atol=1e-6)
X = np.array([-1., 0., 1., 2.]).reshape(-1, 1)
y = np.array([-1., 1., 1., 3.])
model = make_pipeline(PolynomialFeatures(1, include_bias=False), LinearRegression())
model.fit(X, y)
np.testing.assert_allclose(model.predict(X), [-0.8, 0.4, 1.6, 2.8], atol=1e-12)
assert abs(mean_squared_error(y, model.predict(X)) - 0.2) < 1e-12
widget_instance = widgets.IntSlider(value=7)
print('RUNTIME_VERIFIED', json.dumps(actual, sort_keys=True))
'''
        page.evaluate("code => window.runtimeWorker.postMessage({id: 'runtime-probe', code})", code)
        page.wait_for_function("window.runtimeMessages.some(message => message.id === 'runtime-probe' && message.done)", timeout=180000)
        messages = page.evaluate("window.runtimeMessages.filter(message => message.id === 'runtime-probe')")
        assert not [message for message in messages if message.get('error')], messages
        assert any('RUNTIME_VERIFIED' in message.get('output', '') for message in messages), messages
        assert any(message.get('widgetState') for message in messages), messages
        expected_files = {pkg['file_name'] for pkg in LOCK['packages'].values()}
        expected_files.update(['pyodide.asm.wasm', 'pyodide.asm.mjs', 'python_stdlib.zip', 'pyodide-lock.json'])
        assert expected_files <= requests, f'Assets not fetched in cold context: {expected_files - requests}'
        assert not external, external
        assert not errors, errors
        print(f'PASS: {browser_name} {browser.version}: Python {LOCK["info"]["python"]}, Pyodide {CONFIG["version"]}, '
              f'{len(LOCK["packages"])} cold wheel requests, toolkit and scikit-learn calculations, widget serialization, no off-site requests.', flush=True)
        browser.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument('--site-dir', type=Path)
    target.add_argument('--base-url')
    args = parser.parse_args()
    if args.site_dir:
        with http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(
                IsolatedSiteHandler, directory=str(args.site_dir.resolve()))) as server:
            threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                for name in ('chromium', 'firefox'):
                    verify(f'http://127.0.0.1:{server.server_port}', name)
            finally:
                server.shutdown()
    else:
        for name in ('chromium', 'firefox'):
            verify(args.base_url.rstrip('/'), name)
