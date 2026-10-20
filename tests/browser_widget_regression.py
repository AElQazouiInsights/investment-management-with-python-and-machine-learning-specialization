"""Exercise the built site with Chromium, real Pyodide, and real widget controls.

Run explicitly with --site-dir pointing to a fresh VitePress production build.
Requires Playwright, its Chromium browser, and network access for Pyodide packages.
"""

import argparse
import functools
import http.server
import json
import math
from pathlib import Path
import re
import threading

from playwright.sync_api import sync_playwright


class IsolatedSiteHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        super().end_headers()

    def log_message(self, *args):
        pass


def check_unavailable_storage(browser, base_url):
    for mode in ('blocked', 'quota'):
        page = browser.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(error.stack))
        page.add_init_script("""
            const mode = MODE;
            const key = 'code-editor-simple-and-total-returns';
            if (mode === 'quota') {
                localStorage.setItem(key, 'print("legacy draft survives")');
                const setItem = Storage.prototype.setItem;
                Storage.prototype.setItem = function(...args) {
                    if (this === localStorage) throw new DOMException('Storage full', 'QuotaExceededError');
                    return setItem.apply(this, args);
                };
            } else {
                // Deny the editor namespace, leaving VitePress/devtools' own
                // storage initialization outside this component regression.
                // A throwing localStorage getter is also covered in Node tests.
                const getItem = Storage.prototype.getItem;
                Storage.prototype.getItem = function(key) {
                    if (key.startsWith('code-editor-')) throw new DOMException('Storage blocked', 'SecurityError');
                    return getItem.call(this, key);
                };
            }
        """.replace('MODE', json.dumps(mode)))
        page.goto(f"{base_url.rstrip('/')}/1.1-risks.html", wait_until='domcontentloaded', timeout=120000)
        editor = page.locator('[data-editor-id="simple-and-total-returns"]')
        output = page.locator('[data-editor-output="simple-and-total-returns"]')
        editor.get_by_text('Browser storage is unavailable.', exact=False).wait_for()
        page.wait_for_function("document.querySelector('button.run:not(:disabled)')", timeout=120000)
        editor.locator('button.run').click()
        output.get_by_text('Total return: 6.00%', exact=False).wait_for(timeout=180000)
        page.wait_for_function("!document.querySelector('[data-editor-id=\"simple-and-total-returns\"] button.run').disabled")
        if mode == 'quota':
            assert page.evaluate("localStorage.getItem('code-editor-simple-and-total-returns')") == 'print("legacy draft survives")'
            editor.get_by_role('button', name='Restore saved code').click()
        else:
            editor.locator('.cm-content').click()
            page.keyboard.press('Control+a')
            page.keyboard.insert_text('print("session draft runs")')
        editor.locator('button.run').click()
        output.get_by_text('legacy draft survives' if mode == 'quota' else 'session draft runs', exact=False).wait_for(timeout=30000)
        assert not errors, errors
        page.close()
        print(f'PASS: {mode} storage does not break editor mounting, execution, or draft recovery.', flush=True)


def check_chart_protocol(browser, base_url):
    page = browser.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
    page.goto(f"{base_url.rstrip('/')}/1.1-risks.html", wait_until='domcontentloaded', timeout=120000)
    editor = page.locator('[data-editor-id="simple-and-total-returns"]')
    output = page.locator('[data-editor-output="simple-and-total-returns"]')
    page.wait_for_function("document.querySelector('button.run:not(:disabled)')", timeout=120000)

    def execute(code):
        editor.locator('.cm-content').click()
        page.keyboard.press('Control+a')
        page.keyboard.insert_text(code)
        editor.locator('button.run').click()
        page.wait_for_function("!document.querySelector('[data-editor-id=\"simple-and-total-returns\"] button.run').disabled", timeout=180000)

    execute('''import json
print("Loading observations")
print("Loaded 492 months")
print("<ECHARTS_DATA>" + json.dumps({"plot": {"title": "Literal <ECHARTS_DATA> label",
    "series": {"constructor": [1, 2]}, "xAxis": {"data": ["A", "B"]}}}))''')
    output.locator('canvas').wait_for(timeout=30000)
    assert 'Loading observations' in output.inner_text()
    assert 'Loaded 492 months' in output.inner_text()
    assert output.locator('.chart-title').inner_text() == 'Literal <ECHARTS_DATA> label'

    execute('_emit_echarts("Summary\\n<ECHARTS_DATA>null")')
    output.get_by_role('alert').get_by_text('Invalid chart data:', exact=False).wait_for()
    assert output.locator('canvas').count() == 0
    assert 'Summary' in output.inner_text()

    execute('''_emit_echarts('<ECHARTS_DATA>{"plot":{"title":"Recovered chart","series":{"A":[1,2]}}}')''')
    output.locator('canvas').wait_for(timeout=30000)
    assert output.get_by_role('alert').count() == 0
    assert output.locator('.chart-title').inner_text() == 'Recovered chart'
    execute('print("Plain output after chart")')
    assert output.locator('.chart-panel').count() == 0
    assert output.get_by_role('alert').count() == 0
    assert not errors, errors
    page.close()
    print('PASS: progress text, literal protocol-marker labels, visible chart errors, recovery, and plain reruns work.', flush=True)


def check_runtime_failure(browser, base_url):
    context = browser.new_context()
    context.route('https://cdn.jsdelivr.net/pyodide/**', lambda route: route.abort())
    page = context.new_page()
    page.goto(f"{base_url.rstrip('/')}/2.3-black-litterman.html", wait_until='domcontentloaded', timeout=120000)
    editor = page.locator('[data-editor-id="black-litterman-setup"]')
    editor.get_by_role('alert').get_by_text('Python runtime unavailable.', exact=False).wait_for(timeout=60000)
    assert editor.locator('button.run').is_disabled()
    assert editor.locator('.cm-content').count() == 1
    context.close()
    print('PASS: an unavailable Python runtime produces a visible reload message while code remains editable.', flush=True)


def check_python_input(browser, base_url):
    page = browser.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script("""
        window.inputMessages = [];
        const NativeWorker = window.Worker;
        window.Worker = class extends NativeWorker {
            constructor(...args) {
                super(...args);
                this.addEventListener('message', event => window.inputMessages.push(event.data));
            }
        };
    """)
    page.goto(f"{base_url.rstrip('/')}/2.4-robust-portfolios.html", wait_until='domcontentloaded', timeout=120000)
    editor = page.locator('[data-editor-id="robust-portfolios-setup"]')
    output = page.locator('[data-editor-output="robust-portfolios-setup"]')
    page.wait_for_function("document.querySelector('button.run:not(:disabled)')", timeout=120000)

    def run_code(code):
        editor.locator('.cm-content').click()
        page.keyboard.press('Control+a')
        page.keyboard.insert_text(code)
        editor.locator('button.run').click()

    def wait_for_prompt(count):
        page.wait_for_function("count => window.inputMessages.filter(message => message.input).length >= count", arg=count, timeout=180000)
        output.get_by_role('textbox', name='Python input').wait_for()

    def wait_for_done(count):
        page.wait_for_function("count => window.inputMessages.filter(message => message.id === 'robust-portfolios-setup' && message.done).length >= count", arg=count, timeout=30000)

    run_code("first = input('First: ')\nsecond = input('Second: ')\nprint('Lengths:', len(first), len(second))\nprint('Unicode correct:', first == 'é' * 300)")
    wait_for_prompt(1)
    output.get_by_role('textbox', name='Python input').fill('é' * 300)
    output.get_by_role('textbox', name='Python input').press('Enter')
    wait_for_prompt(2)
    output.get_by_role('textbox', name='Python input').press('Enter')
    wait_for_done(1)
    assert 'Lengths: 300 0' in output.inner_text()
    assert 'Unicode correct: True' in output.inner_text()

    run_code("response = input('Capacity: ')\nprint('Capacity length:', len(response))")
    wait_for_prompt(3)
    output.get_by_role('textbox', name='Python input').fill('🙂' * 257)
    output.get_by_role('textbox', name='Python input').press('Enter')
    output.get_by_role('alert').get_by_text('Input exceeds 1024 UTF-8 bytes.', exact=False).wait_for()
    assert editor.locator('button.run').is_disabled()
    output.get_by_role('textbox', name='Python input').fill('🙂' * 256)
    output.get_by_role('textbox', name='Python input').press('Enter')
    wait_for_done(2)
    assert 'Capacity length: 256' in output.inner_text()
    assert output.get_by_role('alert').count() == 0

    run_code("input('Stop test: ')\nprint('Must not run after stop')")
    wait_for_prompt(4)
    output.get_by_role('textbox', name='Python input').fill('x' * 1025)
    output.get_by_role('textbox', name='Python input').press('Enter')
    output.get_by_role('alert').wait_for()
    output.locator('button.reset').click()
    wait_for_done(3)
    assert output.get_by_role('textbox', name='Python input').count() == 0
    assert 'Must not run after stop' not in output.inner_text()

    run_code("from __future__ import annotations\nimport asyncio\nawait asyncio.sleep(0.01)\ndef identity(value: NotDefinedYet):\n    return value\nshared_input_result = identity(7)\nprint('Await and future:', shared_input_result)")
    wait_for_done(4)
    assert 'Await and future: 7' in output.inner_text()
    run_code("print('Shared state:', shared_input_result)")
    wait_for_done(5)
    assert 'Shared state: 7' in output.inner_text()

    run_code("input('Navigation test: ')")
    wait_for_prompt(5)
    page.evaluate('window.inputNavigationSentinel = true')
    page.locator('a[href="/2.3-black-litterman"]').first.click()
    replacement = page.locator('[data-editor-id="black-litterman-setup"]')
    replacement.locator('button.run').wait_for()
    assert page.evaluate('window.inputNavigationSentinel === true'), 'Exercise client-side navigation with the shared worker'
    replacement.locator('button.run').click()
    page.wait_for_function("window.inputMessages.some(message => message.id === 'black-litterman-setup' && message.done)", timeout=30000)
    assert not errors, errors
    page.close()
    print('PASS: Unicode/1024-byte input, retry, Stop, top-level await/future imports, shared globals, and navigation are verified.', flush=True)


def run(site_dir=None, base_url=None):
    server = None
    if base_url is None:
        server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), functools.partial(IsolatedSiteHandler, directory=str(site_dir))
        )
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
            page.add_init_script("""
                if (!sessionStorage.getItem('editor-regression-seeded')) {
                    localStorage.setItem('code-editor-calculating-indexes-7',
                        'tmi_trail_36_rets = total_market_return.rolling(36).mean()');
                    localStorage.setItem('code-editor-calculating-indexes-9',
                        'ind_trail_36_corr = rets_trail_36_corr.groupby(level="date").mean()');
                    localStorage.setItem('code-editor-gbm-3',
                        'gbm_controls = widgets.interact(pok.show_gbm)');
                    sessionStorage.setItem('editor-regression-seeded', '1');
                }
                window.widgetMessages = []; window.widgetRequests = [];
                const NativeWorker = window.Worker;
                window.Worker = class extends NativeWorker {
                    constructor(...args) {
                        super(...args);
                        this.addEventListener('message', event => window.widgetMessages.push(event.data));
                    }
                    postMessage(data, ...rest) {
                        if (data?.code) window.widgetRequests.push(data);
                        return super.postMessage(data, ...rest);
                    }
                };
            """)
            page.goto(f"{base_url.rstrip('/')}/1.3-diversification.html",
                      wait_until="domcontentloaded", timeout=120000)
            page.wait_for_function("document.querySelector('button.run:not(:disabled)')", timeout=120000)

            def editor_with(code):
                return page.locator("div.wrapper").filter(has=page.locator(".cm-content", has_text=code))

            def output_for(editor):
                return editor.locator("xpath=following-sibling::div[contains(@class, 'wrapper')][1]")

            def chart_messages(editor_id):
                return page.evaluate("id => window.widgetMessages.filter(m => m.id === id && m.echart).map(m => m.echart)", editor_id)

            def wait_for_chart(editor_id, previous_count=0):
                page.wait_for_function("""({id, count}) =>
                    window.widgetMessages.filter(m => m.id === id && m.echart).length > count ||
                    window.widgetMessages.some(m => typeof m === 'string' && m.includes('<ECHARTS_DATA>'))
                """, arg={"id": editor_id, "count": previous_count}, timeout=180000)
                raw = page.evaluate("window.widgetMessages.filter(m => typeof m === 'string' && m.includes('<ECHARTS_DATA>'))")
                assert not raw, "Chart bridge sent an unrouted string instead of an editor-tagged JavaScript object"
                return json.loads(chart_messages(editor_id)[-1].split("<ECHARTS_DATA>", 1)[1])

            def editor_by_id(editor_id):
                return page.locator(f'[data-editor-id="{editor_id}"]')

            def wait_for_done(editor_id, count=0):
                page.wait_for_function("({id, count}) => window.widgetMessages.filter(m => m.id === id && m.done).length > count",
                                       arg={"id": editor_id, "count": count}, timeout=180000)

            assert 'rolling_months = 36' in editor_by_id('calculating-indexes-7').inner_text()
            assert 'pair_mask' in editor_by_id('calculating-indexes-9').inner_text()
            assert 'pok.show_gbm_echart(' in editor_by_id('gbm-3').inner_text()
            assert editor_by_id('gbm-3').get_by_text('Restore saved code', exact=True).count() == 1
            backup = page.evaluate("JSON.parse(localStorage.getItem('code-editor-gbm-3:state')).history[0].code")
            assert backup == 'gbm_controls = widgets.interact(pok.show_gbm)'
            print('PASS: returning-browser legacy snippets are preserved and current examples load.', flush=True)

            # Submit prerequisites quickly while packages initialize: the worker must queue them.
            for editor_id in ('diversification-strategies-python-modules', 'utility-helpers',
                              'load-kenneth-french-industry-portfolios'):
                editor_by_id(editor_id).locator('button.run').click()
            wait_for_done('load-kenneth-french-industry-portfolios')
            editor_by_id('calculating-indexes-8').locator('button.run').click()
            wait_for_done('calculating-indexes-8')
            missing_output = output_for(editor_by_id('calculating-indexes-8'))
            missing_output.get_by_text("Python variable 'rolling_months' is missing.", exact=False).wait_for()
            assert missing_output.get_by_role('link', name='Go to prerequisite cell').get_attribute('href') == '#editor-calculating-indexes-7'
            for editor_id in ('calculating-indexes-1', 'calculating-indexes-2', 'calculating-indexes-3',
                              'calculating-indexes-5', 'calculating-indexes-7', 'calculating-indexes-8',
                              'calculating-indexes-9', 'calculating-indexes-10'):
                editor_by_id(editor_id).locator('button.run').click()
            wait_for_done('calculating-indexes-10')
            assert '-0.286' in output_for(editor_by_id('calculating-indexes-10')).inner_text()
            output_for(editor_by_id('calculating-indexes-9')).locator('canvas').first.wait_for(timeout=30000)
            assert output_for(editor_by_id('calculating-indexes-9')).locator('canvas').count() == 2
            assert 'NameError' not in missing_output.inner_text()
            print('PASS: missing prerequisites are identified; the queued rolling-correlation sequence renders both charts and its result.', flush=True)

            # Hold the first widget's lazy JS imports while its Python run ends.
            # A subsequent plain rerun must retire that pending view, too.
            held_imports = []
            hold_widget_imports = True
            import_pattern = re.compile(r'\.js(?:\?|$)')
            def hold_import(route):
                if hold_widget_imports:
                    held_imports.append(route)
                else:
                    route.continue_()
            page.route(import_pattern, hold_import)
            pending_widget = editor_by_id('gbm-4')
            pending_output = output_for(pending_widget)
            pending_widget.locator('button.run').click()
            wait_for_done('gbm-4')
            pending_widget.locator('.cm-content').click()
            page.keyboard.press('Control+a')
            page.keyboard.insert_text('print("Replacement while widget imports are pending")')
            pending_widget.locator('button.run').click()
            wait_for_done('gbm-4', 1)
            assert held_imports, 'The widget import must actually be delayed to exercise the race'
            hold_widget_imports = False
            for route in tuple(held_imports):
                route.continue_()
            page.unroute(import_pattern, hold_import)
            page.wait_for_function("Boolean(window.__widgetRequireCache?.['@jupyter-widgets/controls'])", timeout=60000)
            page.wait_for_timeout(1000)
            assert pending_output.get_by_role('slider').count() == 0
            assert pending_output.locator('canvas').count() == 0
            assert 'Replacement while widget imports are pending' in pending_output.inner_text()
            pending_output.locator('button.reset').click()
            page.evaluate("window.widgetMessages = window.widgetMessages.filter(message => message.id !== 'gbm-4')")
            print('PASS: a delayed widget render cannot replace the output of a newer plain run.', flush=True)

            gbm_editor = editor_with("widget_instance = widgets.interactive").filter(has_text="pok.show_gbm_echart")
            gbm_output = output_for(gbm_editor)
            gbm_editor.locator("button.run").click()
            gbm_before = wait_for_chart("gbm-4")
            gbm_output.locator("canvas").first.wait_for(timeout=30000)
            gbm_output.get_by_role("slider").first.wait_for(timeout=30000)
            assert gbm_output.get_by_role("slider").count() == 5
            assert '[2K' not in gbm_output.inner_text()
            seed_slider = gbm_output.locator("label.widget-label").filter(has_text=re.compile(r"^seed$")).locator("..").get_by_role("slider")
            count = len(chart_messages("gbm-4"))
            seed_slider.press("ArrowRight")
            gbm_after = wait_for_chart("gbm-4", count)
            assert gbm_before["gbmPrices"]["series"] != gbm_after["gbmPrices"]["series"]
            request = page.evaluate("window.widgetRequests.at(-1)")
            assert request["id"] == "gbm-4" and request["skipWidgetState"]
            assert "seed=43" in request["code"]
            print("PASS: GBM controls render; changing the seed updates its chart.", flush=True)

            gbm_count = len(chart_messages("gbm-4"))
            cppi_editor = editor_with("widget_instance = widgets.interactive").filter(has_text="pok.show_cppi_echart")
            cppi_output = output_for(cppi_editor)
            cppi_editor.locator("button.run").click()
            cppi_before = wait_for_chart("cppi-widget")
            cppi_output.locator("canvas").first.wait_for(timeout=30000)
            cppi_output.get_by_role("slider").first.wait_for(timeout=30000)
            assert cppi_output.get_by_role("slider").count() == 8
            assert cppi_output.locator("canvas").count() == 2
            multiplier = cppi_output.locator("label.widget-label").filter(has_text=re.compile(r"^m$")).locator("..").get_by_role("slider")
            count = len(chart_messages("cppi-widget"))
            multiplier.press("ArrowRight")
            cppi_after = wait_for_chart("cppi-widget", count)
            assert cppi_before["cppiWealth"]["series"]["CPPI Median"] != cppi_after["cppiWealth"]["series"]["CPPI Median"]
            assert cppi_before["cppiWealth"]["series"]["Risky Median"] == cppi_after["cppiWealth"]["series"]["Risky Median"]
            assert len(chart_messages("gbm-4")) == gbm_count
            assert cppi_output.get_by_text("Observed-path breaches:", exact=False).count() > 0
            print("PASS: CPPI controls, charts, and summary render; multiplier updates preserve the risky sample and route correctly.", flush=True)

            baseline_editor = editor_by_id("gbm-3")
            baseline_output = output_for(baseline_editor)
            baseline_editor.locator("button.run").click()
            wait_for_chart("gbm-3")
            baseline_output.locator("canvas").first.wait_for(timeout=30000)
            assert baseline_output.get_by_role("slider").count() == 0

            # Preserve intentional same-version edits through a reload, then restore the lesson.
            content = baseline_editor.locator('.cm-content')
            content.click()
            content.press('ControlOrMeta+a')
            page.keyboard.insert_text("print('my saved tweak')")
            count = page.evaluate("window.widgetMessages.filter(m => m.id === 'gbm-3' && m.done).length")
            baseline_editor.locator('button.run').click()
            wait_for_done('gbm-3', count)
            page.reload(wait_until='domcontentloaded')
            editor_by_id('gbm-3').locator('.cm-content').wait_for()
            assert 'my saved tweak' in editor_by_id('gbm-3').inner_text()
            editor_by_id('gbm-3').get_by_role('button', name='Use current example').click()
            assert 'pok.show_gbm_echart(' in editor_by_id('gbm-3').inner_text()
            history = page.evaluate("JSON.parse(localStorage.getItem('code-editor-gbm-3:state')).history")
            assert any(entry['code'] == "print('my saved tweak')" for entry in history)
            assert not errors, errors
            print("PASS: non-widget runs do not copy controls; intentional edits survive reload/reset; no browser errors.", flush=True)

            page.goto(f"{base_url.rstrip('/')}/1.4-alm.html", wait_until='domcontentloaded', timeout=120000)
            page.wait_for_function("document.querySelector('button.run:not(:disabled)')", timeout=120000)
            cir_editor = editor_by_id('cir-widget')
            cir_output = output_for(cir_editor)
            cir_editor.locator('button.run').click()
            cir_before = wait_for_chart('cir-widget')
            cir_output.locator('canvas').first.wait_for(timeout=30000)
            cir_output.get_by_role('slider').first.wait_for(timeout=30000)
            assert cir_output.get_by_role('slider').count() == 7
            assert cir_output.locator('canvas').count() == 2
            initial_rate = cir_output.locator('label.widget-label').filter(has_text=re.compile(r'^r0$')).locator('..').get_by_role('slider')
            count = len(chart_messages('cir-widget'))
            initial_rate.press('ArrowRight')
            cir_after = wait_for_chart('cir-widget', count)
            assert cir_after['cirBondPrices']['series']['Scenario 1'][0][1] < cir_before['cirBondPrices']['series']['Scenario 1'][0][1]
            assert cir_after['cirRates']['series']['Scenario 1'][0][1] > cir_before['cirRates']['series']['Scenario 1'][0][1]
            request = page.evaluate('window.widgetRequests.at(-1)')
            assert request['id'] == 'cir-widget' and 'pok.show_cir_echart(' in request['code']
            assert 'r0=' in request['code'] and 'seed=42' in request['code']
            volatility = cir_output.locator('label.widget-label').filter(has_text=re.compile(r'^sigma$')).locator('..').get_by_role('slider')
            count = len(chart_messages('cir-widget'))
            volatility.press('Home')
            deterministic = wait_for_chart('cir-widget', count)
            assert deterministic['cirRates']['series']['Scenario 1'] == deterministic['cirRates']['series']['Scenario 5']
            for points in deterministic['cirBondPrices']['series'].values():
                assert points[-1] == [5, 1]
            for name, keys in (('a', ['Home']), ('b', ['Home', 'ArrowRight']), ('sigma', ['End'])):
                control = cir_output.locator('label.widget-label').filter(has_text=re.compile(f'^{name}$')).locator('..').get_by_role('slider')
                for key in keys:
                    control.press(key)
            page.wait_for_function("window.widgetMessages.filter(m => m.id === 'cir-widget' && m.echart).at(-1)?.echart.includes('not satisfied')", timeout=180000)
            stress = json.loads(chart_messages('cir-widget')[-1].split('<ECHARTS_DATA>', 1)[1])
            assert all(point[1] >= 0 for points in stress['cirRates']['series'].values() for point in points)
            assert not errors, errors
            print('PASS: CIR controls update both charts; initial-rate pricing, zero volatility, and nonnegative rates with a failed Feller condition are verified.', flush=True)

            cir_count = len(chart_messages('cir-widget'))
            hedging_editor = editor_by_id('hedging-widget')
            hedging_output = output_for(hedging_editor)
            hedging_editor.locator('button.run').click()
            hedging_before = wait_for_chart('hedging-widget')
            hedging_output.locator('canvas').first.wait_for(timeout=30000)
            hedging_output.get_by_role('slider').first.wait_for(timeout=30000)
            assert hedging_output.get_by_role('slider').count() == 9
            assert hedging_output.locator('canvas').count() == 2
            assert '294/500 (58.8%)' in chart_messages('hedging-widget')[-1]

            def hedging_control(name):
                return hedging_output.locator('label.widget-label').filter(has_text=re.compile(f'^{name}$')).locator('..').get_by_role('slider')

            count = len(chart_messages('hedging-widget'))
            hedging_control('initial_assets').press('ArrowRight')
            funded = wait_for_chart('hedging-widget', count)
            for name in ('Cash 1', 'Matching bond'):
                for old, new in zip(hedging_before['hedgingFunding']['series'][name], funded['hedgingFunding']['series'][name]):
                    assert old[0] == new[0] and math.isclose(new[1], old[1] * 0.80 / 0.75, rel_tol=1e-12)
            assert 'fully funded or in surplus' in chart_messages('hedging-widget')[-1]
            request = page.evaluate('window.widgetRequests.at(-1)')
            assert request['id'] == 'hedging-widget' and 'pok.show_liability_hedging_echart(' in request['code']
            assert 'initial_assets=0.8' in request['code'] and 'liability=1' in request['code']

            count = len(chart_messages('hedging-widget'))
            hedging_control('seed').press('ArrowRight')
            reseeded = wait_for_chart('hedging-widget', count)
            assert reseeded['hedgingFunding']['series']['Matching bond'] == funded['hedgingFunding']['series']['Matching bond']
            assert reseeded['hedgingFunding']['series']['Cash 1'] != funded['hedgingFunding']['series']['Cash 1']
            count = len(chart_messages('hedging-widget'))
            hedging_control('liability').press('ArrowRight')
            larger_liability = wait_for_chart('hedging-widget', count)
            before_ratio = reseeded['hedgingFunding']['series']['Matching bond'][0][1]
            after_ratio = larger_liability['hedgingFunding']['series']['Matching bond'][0][1]
            assert math.isclose(after_ratio, before_ratio / 1.1, rel_tol=1e-12), (
                before_ratio, after_ratio, page.evaluate('window.widgetRequests.slice(-3)'),
                [message.split('<ECHARTS_DATA>')[0] for message in chart_messages('hedging-widget')[-3:]],
            )

            count = len(chart_messages('hedging-widget'))
            hedging_output.locator('select').select_option(label='52')
            weekly = wait_for_chart('hedging-widget', count)
            assert len(weekly['hedgingFunding']['series']['Cash 1']) == 521
            assert weekly['hedgingFunding']['series']['Matching bond'] == larger_liability['hedgingFunding']['series']['Matching bond']
            count = len(chart_messages('hedging-widget'))
            hedging_control('sigma').press('Home')
            deterministic_hedge = wait_for_chart('hedging-widget', count)
            fixed_ratio = deterministic_hedge['hedgingFunding']['series']['Matching bond'][0][1]
            for name, points in deterministic_hedge['hedgingFunding']['series'].items():
                if name.startswith('Cash'):
                    assert all(math.isclose(value, fixed_ratio, rel_tol=1e-12) for _, value in points)
            count = len(chart_messages('hedging-widget'))
            hedging_control('initial_assets').press('Home')
            no_capital = wait_for_chart('hedging-widget', count)
            assert all(value == 0 for _, value in no_capital['hedgingFunding']['series']['Cash 1'])
            assert no_capital['hedgingTerminal']['series']['Matching bond'][1:3] == [[0, 0], [0, 100]]
            assert len(chart_messages('cir-widget')) == cir_count
            assert not errors, errors
            print('PASS: hedging controls update capital, liability, seed, and rollover frequency; deterministic matching, zero capital, CDFs, and independent editor routing are verified.', flush=True)

            hedge_count = len(chart_messages('hedging-widget'))
            coupon_editor = editor_by_id('coupon-widget')
            coupon_output = output_for(coupon_editor)
            coupon_editor.locator('button.run').click()
            coupon_before = wait_for_chart('coupon-widget')
            coupon_output.locator('canvas').first.wait_for(timeout=30000)
            coupon_output.get_by_role('slider').first.wait_for(timeout=30000)
            assert coupon_output.get_by_role('slider').count() == 5
            assert coupon_output.locator('canvas').count() == 2
            assert math.isclose(coupon_before['couponYield']['series']['Selected bond'][0][1], 94.49187463842017)

            def coupon_control(name):
                return coupon_output.locator('label.widget-label').filter(has_text=re.compile(f'^{name}$')).locator('..').get_by_role('slider')

            count = len(chart_messages('coupon-widget'))
            coupon_control('ytm').press('ArrowRight')
            higher_yield = wait_for_chart('coupon-widget', count)
            assert higher_yield['couponYield']['series']['Selected bond'][0][1] < coupon_before['couponYield']['series']['Selected bond'][0][1]
            count = len(chart_messages('coupon-widget'))
            coupon_control('reinvestment_rate').press('ArrowRight')
            reinvested = wait_for_chart('coupon-widget', count)
            assert reinvested['couponYield'] == higher_yield['couponYield']
            assert reinvested['couponReinvestment']['series']['Selected reinvestment'][0][1] > 109
            count = len(chart_messages('coupon-widget'))
            coupon_output.locator('select').select_option(label='Quarterly')
            quarterly = wait_for_chart('coupon-widget', count)
            request = page.evaluate('window.widgetRequests.at(-1)')
            assert request['id'] == 'coupon-widget' and 'pok.show_coupon_bond_echart(' in request['code']
            assert 'coupons_per_year=4' in request['code']
            assert 'coupon 0.75' in chart_messages('coupon-widget')[-1]
            assert quarterly['couponYield']['series'] != reinvested['couponYield']['series']
            count = len(chart_messages('coupon-widget'))
            coupon_control('coupon_rate').press('Home')
            zero_coupon = wait_for_chart('coupon-widget', count)
            assert all(value == 100 for _, value in zero_coupon['couponReinvestment']['series']['Terminal wealth'])
            count = len(chart_messages('coupon-widget'))
            coupon_control('ytm').press('Home')
            negative_yield = wait_for_chart('coupon-widget', count)
            assert negative_yield['couponYield']['series']['Selected bond'][0][0] == -2
            assert math.isclose(negative_yield['couponYield']['series']['Selected bond'][0][1], 100 / 0.995 ** 12, rel_tol=1e-12)
            assert len(chart_messages('hedging-widget')) == hedge_count
            assert not errors, errors
            print('PASS: coupon-bond controls update YTM, reinvestment, and labeled coupon-frequency choices; zero coupons, negative yields, and editor routing are verified.', flush=True)

            coupon_count = len(chart_messages('coupon-widget'))
            duration_editor = editor_by_id('duration-widget')
            duration_output = output_for(duration_editor)
            duration_editor.locator('button.run').click()
            duration_before = wait_for_chart('duration-widget')
            duration_output.locator('canvas').first.wait_for(timeout=30000)
            duration_output.get_by_role('slider').first.wait_for(timeout=30000)
            assert duration_output.get_by_role('slider').count() == 5
            assert duration_output.locator('canvas').count() == 2
            assert 'Macaulay duration: 2.887555 years' in chart_messages('duration-widget')[-1]

            def duration_control(name):
                return duration_output.locator('label.widget-label').filter(has_text=re.compile(f'^{name}$')).locator('..').get_by_role('slider')

            count = len(chart_messages('duration-widget'))
            duration_control('principal').press('ArrowRight')
            scaled_duration = wait_for_chart('duration-widget', count)
            for old, new in zip(duration_before['durationWeights']['series']['PV weight'], scaled_duration['durationWeights']['series']['PV weight']):
                assert old[0] == new[0] and math.isclose(old[1], new[1], rel_tol=1e-12)
            assert 'Full price: 188.983749' in chart_messages('duration-widget')[-1]
            assert 'Macaulay duration: 2.887555 years' in chart_messages('duration-widget')[-1]
            count = len(chart_messages('duration-widget'))
            duration_control('shift_bps').press('Home')
            negative_shift = wait_for_chart('duration-widget', count)
            point = negative_shift['durationSensitivity']['series']['Selected exact'][0]
            assert point[0] == -200 and point[1] > 0
            assert negative_shift['durationSensitivity']['xAxis']['min'] == -200
            assert negative_shift['durationWeights'] == scaled_duration['durationWeights']
            request = page.evaluate('window.widgetRequests.at(-1)')
            assert request['id'] == 'duration-widget' and 'pok.show_duration_echart(' in request['code']
            assert 'shift_bps=-200' in request['code']
            count = len(chart_messages('duration-widget'))
            duration_output.locator('select').select_option(label='Monthly')
            monthly_duration = wait_for_chart('duration-widget', count)
            assert len(monthly_duration['durationWeights']['series']['PV weight']) == 36
            assert 'coupons_per_year=12' in page.evaluate('window.widgetRequests.at(-1).code')
            count = len(chart_messages('duration-widget'))
            duration_control('coupon_rate').press('Home')
            zero_duration = wait_for_chart('duration-widget', count)
            weights = zero_duration['durationWeights']['series']['PV weight']
            assert all(value == 0 for _, value in weights[:-1])
            assert math.isclose(weights[-1][1], 100, rel_tol=1e-12)
            assert 'Macaulay duration: 3.000000 years' in chart_messages('duration-widget')[-1]
            assert len(chart_messages('coupon-widget')) == coupon_count
            assert not errors, errors
            print('PASS: duration controls preserve scale invariance, use signed basis-point shifts, update monthly timing weights, and recover the zero-coupon duration; routing is independent.', flush=True)

            duration_count = len(chart_messages('duration-widget'))
            matching_editor = editor_by_id('ldi-matching-widget')
            matching_output = output_for(matching_editor)
            matching_editor.locator('button.run').click()
            matching_before = wait_for_chart('ldi-matching-widget')
            matching_output.locator('canvas').first.wait_for(timeout=30000)
            matching_output.get_by_role('slider').first.wait_for(timeout=30000)
            assert matching_output.get_by_role('slider').count() == 5
            assert matching_output.locator('select').count() == 2
            assert matching_output.locator('canvas').count() == 2
            assert 'PV surplus / deficit: -16.12' in chart_messages('ldi-matching-widget')[-1]

            def matching_control(label):
                return matching_output.locator('label.widget-label').filter(has_text=re.compile(f'^{re.escape(label)}$')).locator('..')

            count = len(chart_messages('ldi-matching-widget'))
            matching_control('Assets ($)').get_by_role('slider').press('ArrowRight')
            more_capital = wait_for_chart('ldi-matching-widget', count)
            for old, new in zip(matching_before['matchingFunding']['series']['Duration matched'], more_capital['matchingFunding']['series']['Duration matched']):
                assert old[0] == new[0] and math.isclose(new[1], old[1] * 131000 / 130000, rel_tol=1e-12)
            assert more_capital['matchingFunding']['series']['Initial matched'][0][1] > 1
            request = page.evaluate('window.widgetRequests.at(-1)')
            assert request['id'] == 'ldi-matching-widget' and 'pok.show_duration_matching_echart(' in request['code']
            assert 'asset_value=131000' in request['code'] and 'Assets ($)' not in request['code']
            count = len(chart_messages('ldi-matching-widget'))
            matching_control('Long coupons').locator('select').select_option(label='Quarterly')
            mixed_frequency = wait_for_chart('ldi-matching-widget', count)
            assert len(mixed_frequency['matchingPayments']['series']['Matched']) == 80
            assert 'long_frequency=4' in page.evaluate('window.widgetRequests.at(-1).code')
            assert 'liability duration: 10.960799 years' in chart_messages('ldi-matching-widget')[-1]
            count = len(chart_messages('ldi-matching-widget'))
            matching_control('Base rate').get_by_role('slider').press('ArrowRight')
            new_base = wait_for_chart('ldi-matching-widget', count)
            assert math.isclose(new_base['matchingFunding']['series']['Initial matched'][0][0], 4.5)
            count = len(chart_messages('ldi-matching-widget'))
            matching_control('Liability delay').get_by_role('slider').press('End')
            infeasible = wait_for_chart('ldi-matching-widget', count)
            assert infeasible == {}
            assert 'No unique long-only duration match' in chart_messages('ldi-matching-widget')[-1]
            matching_output.locator('canvas').first.wait_for(state='detached', timeout=30000)
            count = len(chart_messages('ldi-matching-widget'))
            matching_control('Liability delay').get_by_role('slider').press('Home')
            recovered = wait_for_chart('ldi-matching-widget', count)
            matching_output.locator('canvas').first.wait_for(timeout=30000)
            assert len(recovered) == 2 and matching_output.locator('canvas').count() == 2
            assert len(chart_messages('duration-widget')) == duration_count
            assert not errors, errors
            print('PASS: LDI friendly labels route to Python keywords; capital, common-curve frequency, and base-rate updates work; infeasible matches clear stale charts and recover.', flush=True)

            matching_count = len(chart_messages('ldi-matching-widget'))
            mix_editor = editor_by_id('psp-lhp-widget')
            mix_output = output_for(mix_editor)
            mix_editor.locator('button.run').click()
            mix_before = wait_for_chart('psp-lhp-widget')
            mix_output.locator('canvas').first.wait_for(timeout=30000)
            mix_output.get_by_role('slider').first.wait_for(timeout=30000)
            assert mix_output.get_by_role('slider').count() == 9
            assert mix_output.locator('canvas').count() == 2

            def mix_control(label):
                return mix_output.locator('label.widget-label').filter(has_text=re.compile(f'^{re.escape(label)}$')).locator('..')

            count = len(chart_messages('psp-lhp-widget'))
            mix_control('Stock share').get_by_role('slider').press('Home')
            bonds_only = wait_for_chart('psp-lhp-widget', count)
            assert bonds_only['pspLhpWealth']['series']['Fixed mix median'] == bonds_only['pspLhpWealth']['series']['Bonds median']
            for name in ('Stocks median', 'Bonds median'):
                assert bonds_only['pspLhpWealth']['series'][name] == mix_before['pspLhpWealth']['series'][name]
            count = len(chart_messages('psp-lhp-widget'))
            mix_control('Stock share').get_by_role('slider').press('End')
            stocks_only = wait_for_chart('psp-lhp-widget', count)
            assert stocks_only['pspLhpWealth']['series']['Fixed mix median'] == stocks_only['pspLhpWealth']['series']['Stocks median']
            count = len(chart_messages('psp-lhp-widget'))
            mix_control('Threshold').get_by_role('slider').press('End')
            higher_threshold = wait_for_chart('psp-lhp-widget', count)
            for name, points in stocks_only['pspLhpWealth']['series'].items():
                if name != 'Terminal threshold':
                    assert higher_threshold['pspLhpWealth']['series'][name] == points
            assert higher_threshold['pspLhpTerminal']['series']['Terminal threshold'] == [[1.5, 0], [1.5, 100]]
            count = len(chart_messages('psp-lhp-widget'))
            mix_control('Seed').get_by_role('slider').press('ArrowRight')
            new_seed = wait_for_chart('psp-lhp-widget', count)
            assert new_seed['pspLhpWealth']['series']['Stocks median'] != higher_threshold['pspLhpWealth']['series']['Stocks median']
            count = len(chart_messages('psp-lhp-widget'))
            mix_control('Rebalance').locator('select').select_option(label='Quarterly')
            quarterly_mix = wait_for_chart('psp-lhp-widget', count)
            assert len(quarterly_mix['pspLhpWealth']['series']['Fixed mix median']) == 41
            assert 'periods_per_year=4' in page.evaluate('window.widgetRequests.at(-1).code')
            assert len(chart_messages('ldi-matching-widget')) == matching_count

            # Rerun with fewer controls and non-default fixed arguments. Old models
            # must not override the new callback's fixed parameters on a slider edit.
            content = mix_editor.locator('.cm-content')
            content.click()
            content.press('ControlOrMeta+a')
            page.keyboard.insert_text('''import ipywidgets as widgets
import PortfolioOptimizationKit as pok
widget_instance = widgets.interactive(
    pok.show_psp_lhp_echart,
    n_years=widgets.fixed(2), n_scenarios=widgets.fixed(100),
    periods_per_year=widgets.fixed(4), mu=widgets.fixed(0.03),
    sigma=widgets.fixed(0.0), rate_sigma=widgets.fixed(0.0),
    short_weight=widgets.fixed(0.4), floor=widgets.fixed(1.0), seed=widgets.fixed(9),
    psp_weight=widgets.FloatSlider(value=0.5, min=0, max=1, step=0.1, description="Stock share", continuous_update=False),
)
widget_instance''')
            count = len(chart_messages('psp-lhp-widget'))
            mix_editor.locator('button.run').click()
            wait_for_chart('psp-lhp-widget', count)
            mix_output.get_by_role('slider').first.wait_for(timeout=30000)
            assert mix_output.get_by_role('slider').count() == 1
            count = len(chart_messages('psp-lhp-widget'))
            mix_control('Stock share').get_by_role('slider').press('ArrowRight')
            fixed_parameters = wait_for_chart('psp-lhp-widget', count)
            request = page.evaluate('window.widgetRequests.at(-1)')
            for parameter in ('n_years=2', 'n_scenarios=100', 'periods_per_year=4', 'mu=0.03', 'seed=9', 'psp_weight=0.6'):
                assert parameter in request['code'], request
            expected = (1 + 0.6 * math.expm1(0.03 / 4) + 0.4 * (1.03 ** 0.25 - 1)) ** 8
            points = fixed_parameters['pspLhpWealth']['series']['Fixed mix median']
            assert len(points) == 9 and math.isclose(points[-1][1], expected, rel_tol=1e-12)
            assert not errors, errors
            print('PASS: fixed-mix allocation endpoints, paired samples, terminal thresholds, seeds, and frequency updates work; reruns discard retired controls and preserve fixed callback arguments.', flush=True)

            mix_count = len(chart_messages('psp-lhp-widget'))
            glide_editor = editor_by_id('glide-widget')
            glide_output = output_for(glide_editor)
            glide_editor.locator('button.run').click()
            glide_before = wait_for_chart('glide-widget')
            glide_output.locator('canvas').first.wait_for(timeout=30000)
            glide_output.get_by_role('slider').first.wait_for(timeout=30000)
            assert glide_output.get_by_role('slider').count() == 6
            assert glide_output.locator('canvas').count() == 2
            targets = glide_before['glideTargets']['series']['Glide path']
            assert targets[0] == [0, 80] and targets[-2:] == [[9.5, 20], [10, 20]]

            def glide_control(label):
                return glide_output.locator('label.widget-label').filter(has_text=re.compile(f'^{re.escape(label)}$')).locator('..')

            count = len(chart_messages('glide-widget'))
            glide_control('Start stocks').get_by_role('slider').press('Home')
            new_start = wait_for_chart('glide-widget', count)
            assert new_start['glideWealth']['series']['Fixed 70/30'] == glide_before['glideWealth']['series']['Fixed 70/30']
            assert new_start['glideWealth']['series']['Glide path'] != glide_before['glideWealth']['series']['Glide path']
            count = len(chart_messages('glide-widget'))
            glide_control('End stocks').get_by_role('slider').press('Home')
            constant_glide = wait_for_chart('glide-widget', count)
            assert constant_glide['glideWealth']['series']['Glide path'] == constant_glide['glideWealth']['series']['Constant mean target']
            count = len(chart_messages('glide-widget'))
            glide_control('End stocks').get_by_role('slider').press('End')
            increasing = wait_for_chart('glide-widget', count)
            assert increasing['glideTargets']['series']['Glide path'][-2:] == [[9.5, 100], [10, 100]]
            count = len(chart_messages('glide-widget'))
            glide_control('Rebalance').locator('select').select_option(label='Quarterly')
            quarterly_glide = wait_for_chart('glide-widget', count)
            assert len(quarterly_glide['glideTargets']['series']['Glide path']) == 41
            assert quarterly_glide['glideTargets']['series']['Glide path'][-2:] == [[9.75, 100], [10, 100]]
            request = page.evaluate('window.widgetRequests.at(-1)')
            assert request['id'] == 'glide-widget' and 'pok.show_glidepath_echart(' in request['code']
            assert 'periods_per_year=4' in request['code'] and 'start=0' in request['code']
            count = len(chart_messages('glide-widget'))
            glide_control('Threshold').get_by_role('slider').press('End')
            threshold_glide = wait_for_chart('glide-widget', count)
            assert threshold_glide['glideTargets'] == quarterly_glide['glideTargets']
            for name in ('Glide path', 'Constant mean target', 'Fixed 70/30'):
                assert threshold_glide['glideWealth']['series'][name] == quarterly_glide['glideWealth']['series'][name]
            assert len(chart_messages('psp-lhp-widget')) == mix_count
            assert not errors, errors
            print('PASS: glide endpoints, unchanged fixed comparator, constant and increasing schedules, decision timing, threshold independence, and widget routing are verified.', flush=True)

            glide_count = len(chart_messages('glide-widget'))
            floor_editor = editor_by_id('floor-widget')
            floor_output = output_for(floor_editor)
            floor_editor.locator('button.run').click()
            floor_before = wait_for_chart('floor-widget')
            floor_output.locator('canvas').first.wait_for(timeout=30000)
            floor_output.get_by_role('slider').first.wait_for(timeout=30000)
            assert floor_output.get_by_role('slider').count() == 7
            assert floor_output.locator('canvas').count() == 2
            assert 'initial matching cost: 0.596090' in chart_messages('floor-widget')[-1]

            def floor_control(label):
                return floor_output.locator('label.widget-label').filter(has_text=re.compile(f'^{re.escape(label)}$')).locator('..')

            initial_text = chart_messages('floor-widget')[-1].split('<ECHARTS_DATA>')[0]
            count = len(chart_messages('floor-widget'))
            floor_control('Path').get_by_role('slider').press('ArrowRight')
            second_path = wait_for_chart('floor-widget', count)
            assert 'Scenario 2' in second_path['floorWealth']['title']
            assert second_path['floorWealth']['series']['Floor PV'] != floor_before['floorWealth']['series']['Floor PV']
            assert chart_messages('floor-widget')[-1].split('<ECHARTS_DATA>')[0] == initial_text
            count = len(chart_messages('floor-widget'))
            floor_control('Multiplier').get_by_role('slider').press('Home')
            all_bonds = wait_for_chart('floor-widget', count)
            for actual, expected in zip(all_bonds['floorWealth']['series']['Floor allocator'], all_bonds['floorWealth']['series']['ZCB only']):
                assert actual[0] == expected[0] and math.isclose(actual[1], expected[1], rel_tol=1e-12)
            assert all(value == 0 for _, value in all_bonds['floorWeights']['series']['Floor allocator'])
            count = len(chart_messages('floor-widget'))
            floor_control('Terminal floor').get_by_role('slider').press('End')
            underfunded = wait_for_chart('floor-widget', count)
            assert 'initially underfunded' in chart_messages('floor-widget')[-1]
            assert '1000/1000' in chart_messages('floor-widget')[-1]
            assert underfunded['floorWealth']['series']['Floor PV'][0][1] > 1
            assert all(value == 0 for _, value in underfunded['floorWeights']['series']['Floor allocator'])

            floor_control('Terminal floor').get_by_role('slider').press('Home')
            for _ in range(8):
                floor_control('Terminal floor').get_by_role('slider').press('ArrowRight')
            page.wait_for_function("window.widgetMessages.filter(m => m.id === 'floor-widget' && m.echart).at(-1)?.echart.includes('Terminal promise: 0.8000')", timeout=180000)
            count = len(chart_messages('floor-widget'))
            floor_control('Multiplier').get_by_role('slider').press('End')
            leveraged_cushion = wait_for_chart('floor-widget', count)
            assert leveraged_cushion['floorWealth']['series']['Fixed 70/30'] == second_path['floorWealth']['series']['Fixed 70/30']
            count = len(chart_messages('floor-widget'))
            floor_control('Stock vol').get_by_role('slider').press('End')
            wait_for_chart('floor-widget', count)
            count = len(chart_messages('floor-widget'))
            floor_control('Rebalance').locator('select').select_option(label='Semiannual')
            stressed_floor = wait_for_chart('floor-widget', count)
            assert len(stressed_floor['floorWealth']['series']['Floor allocator']) == 21
            text = chart_messages('floor-widget')[-1].split('<ECHARTS_DATA>')[0]
            breaches = re.search(r'PV breaches \(including time zero\): (\d+)/1000', text)
            assert breaches and int(breaches.group(1)) > 0, text
            request = page.evaluate('window.widgetRequests.at(-1)')
            assert request['id'] == 'floor-widget' and 'pok.show_floor_echart(' in request['code']
            assert 'periods_per_year=2' in request['code'] and 'scenario=2' in request['code']
            assert len(chart_messages('glide-widget')) == glide_count
            assert not errors, errors
            print('PASS: floor controls preserve paired paths, distinguish initial underfunding, recover the all-bond limit, and expose sampled gap losses with larger risk; routing is independent.', flush=True)

            floor_count = len(chart_messages('floor-widget'))
            dd_editor = editor_by_id('drawdown-widget')
            dd_output = output_for(dd_editor)
            dd_editor.locator('button.run').click()
            dd_before = wait_for_chart('drawdown-widget')
            dd_output.locator('canvas').first.wait_for(timeout=30000)
            dd_output.get_by_role('slider').first.wait_for(timeout=30000)
            assert dd_output.get_by_role('slider').count() == 6
            assert dd_output.locator('select').count() == 2
            assert dd_output.locator('canvas').count() == 2

            def dd_control(label):
                return dd_output.locator('label.widget-label').filter(has_text=re.compile(f'^{re.escape(label)}$')).locator('..')

            initial_text = chart_messages('drawdown-widget')[-1].split('<ECHARTS_DATA>')[0]
            count = len(chart_messages('drawdown-widget'))
            dd_control('Display hedge').locator('select').select_option(label='Matching ZCB')
            dd_bond = wait_for_chart('drawdown-widget', count)
            assert dd_bond['drawdownLoss'] == dd_before['drawdownLoss']
            assert dd_bond['drawdownWealth']['series']['Policy wealth'] != dd_before['drawdownWealth']['series']['Policy wealth']
            assert chart_messages('drawdown-widget')[-1].split('<ECHARTS_DATA>')[0] == initial_text
            assert 'hedge="zcb"' in page.evaluate('window.widgetRequests.at(-1).code')
            count = len(chart_messages('drawdown-widget'))
            dd_control('Path').get_by_role('slider').press('ArrowRight')
            dd_path = wait_for_chart('drawdown-widget', count)
            assert 'Scenario 2' in dd_path['drawdownWealth']['title']
            assert chart_messages('drawdown-widget')[-1].split('<ECHARTS_DATA>')[0] == initial_text
            count = len(chart_messages('drawdown-widget'))
            dd_control('DD request').get_by_role('slider').press('Home')
            dd_tight = wait_for_chart('drawdown-widget', count)
            assert dd_tight['drawdownLoss']['series']['Drawdown limit'] == [[0, -5], [10, -5]]
            assert math.isclose(dd_tight['drawdownWealth']['series']['Policy wealth'][1][1],
                                dd_path['drawdownWealth']['series']['Policy wealth'][1][1], rel_tol=1e-12)
            assert 'rule multiplier: 20' in chart_messages('drawdown-widget')[-1]
            count = len(chart_messages('drawdown-widget'))
            dd_control('Rebalance').locator('select').select_option(label='Semiannual')
            dd_semiannual = wait_for_chart('drawdown-widget', count)
            assert len(dd_semiannual['drawdownLoss']['series']['Policy + cash']) == 21
            assert any(value < -5 for _, value in dd_semiannual['drawdownLoss']['series']['Policy + cash'])
            request = page.evaluate('window.widgetRequests.at(-1)')
            assert request['id'] == 'drawdown-widget' and 'pok.show_drawdown_echart(' in request['code']
            assert 'periods_per_year=2' in request['code'] and 'maxdd=0.05' in request['code']
            assert len(chart_messages('floor-widget')) == floor_count
            assert not errors, errors
            print('PASS: drawdown hedge and path selectors preserve paired statistics; tighter requests retain full initial stock exposure, and sampled cash-policy breaches remain possible.', flush=True)

            dd_count = len(chart_messages('drawdown-widget'))
            historical_editor = editor_by_id('historical-widget')
            historical_output = output_for(historical_editor)
            historical_editor.locator('button.run').click()
            historical_before = wait_for_chart('historical-widget')
            historical_output.locator('canvas').first.wait_for(timeout=30000)
            historical_output.get_by_role('slider').first.wait_for(timeout=30000)
            assert historical_output.get_by_role('slider').count() == 3
            assert historical_output.locator('canvas').count() == 2
            assert historical_before['dates'][0] == '1989-12' and historical_before['dates'][-1] == '2018-12'
            assert len(historical_before['dates']) == 349
            assert historical_before['historicalWealth']['yAxis']['type'] == 'log'
            assert '348 monthly returns' in chart_messages('historical-widget')[-1]

            def historical_control(label):
                return historical_output.locator('label.widget-label').filter(has_text=re.compile(f'^{re.escape(label)}$')).locator('..').get_by_role('slider')

            count = len(chart_messages('historical-widget'))
            historical_control('DD request').press('Home')
            historical_tight = wait_for_chart('historical-widget', count)
            assert historical_tight['historicalDrawdowns']['series']['Drawdown policy'][1] < -5
            assert historical_tight['historicalWealth']['series']['Market proxy'] == historical_before['historicalWealth']['series']['Market proxy']
            count = len(chart_messages('historical-widget'))
            historical_control('Start year').press('End')
            historical_short = wait_for_chart('historical-widget', count)
            assert historical_short['dates'][0] == '2017-12' and len(historical_short['dates']) == 13
            for name in ('Market proxy', 'Drawdown policy', 'Fixed 70/30', 'Assumed cash'):
                assert historical_short['historicalWealth']['series'][name][0] == 1
            request = page.evaluate('window.widgetRequests.at(-1)')
            assert request['id'] == 'historical-widget' and 'pok.show_historical_drawdown_echart(' in request['code']
            assert 'start_year=2018' in request['code'] and 'end_year=2018' in request['code']
            count = len(chart_messages('historical-widget'))
            historical_control('Cash rate').press('Home')
            historical_zero_cash = wait_for_chart('historical-widget', count)
            assert all(value == 1 for value in historical_zero_cash['historicalWealth']['series']['Assumed cash'])
            assert historical_zero_cash['historicalWealth']['series']['Market proxy'] == historical_short['historicalWealth']['series']['Market proxy']
            assert 'Assumed cash: 0.00%' in chart_messages('historical-widget')[-1]
            assert len(chart_messages('drawdown-widget')) == dd_count
            assert not errors, errors
            print('PASS: historical data load in-browser; first-month losses, window resets, fixed end dates, cash assumptions, and independent routing are verified.', flush=True)

            nominal_duration_count = len(chart_messages('duration-widget'))
            modified_editor = editor_by_id('modified-duration-widget')
            modified_output = output_for(modified_editor)
            modified_editor.locator('button.run').click()
            modified_before = wait_for_chart('modified-duration-widget')
            modified_output.locator('canvas').first.wait_for(timeout=30000)
            modified_output.get_by_role('slider').first.wait_for(timeout=30000)
            assert modified_output.get_by_role('slider').count() == 5
            assert modified_output.locator('select').count() == 2
            assert modified_output.locator('canvas').count() == 2
            assert 'Full price: 94.213021' in chart_messages('modified-duration-widget')[-1]
            assert 'exact minus linear price: +0.000356' in chart_messages('modified-duration-widget')[-1]

            def modified_control(label):
                return modified_output.locator('label.widget-label').filter(has_text=re.compile(f'^{re.escape(label)}$')).locator('..')

            count = len(chart_messages('modified-duration-widget'))
            modified_control('Face value').get_by_role('slider').press('ArrowRight')
            scaled = wait_for_chart('modified-duration-widget', count)
            assert scaled['durationSensitivity']['series'] == modified_before['durationSensitivity']['series']
            assert 'Full price: 188.426041' in chart_messages('modified-duration-widget')[-1]
            assert 'DV01 for this quote: 0.049990' in chart_messages('modified-duration-widget')[-1]
            count = len(chart_messages('modified-duration-widget'))
            modified_control('Yield shift bp').get_by_role('slider').press('End')
            large_shift = wait_for_chart('modified-duration-widget', count)
            selected = large_shift['durationSensitivity']['series']
            baseline = modified_before['durationSensitivity']['series']
            assert selected['Selected exact'][0][0] == 300
            assert selected['Selected exact'][0][1] - selected['Selected approximation'][0][1] > 100 * (baseline['Selected exact'][0][1] - baseline['Selected approximation'][0][1])
            count = len(chart_messages('modified-duration-widget'))
            modified_control('Convention').locator('select').select_option(label='Nominal annual')
            nominal = wait_for_chart('modified-duration-widget', count)
            assert nominal['durationSensitivity']['xAxis']['name'] == 'Nominal YTM change (bp)'
            assert 'quote="nominal"' in page.evaluate('window.widgetRequests.at(-1).code')
            count = len(chart_messages('modified-duration-widget'))
            modified_control('Coupon rate').get_by_role('slider').press('Home')
            wait_for_chart('modified-duration-widget', count)
            count = len(chart_messages('modified-duration-widget'))
            modified_control('Convention').locator('select').select_option(label='Continuous annual')
            zero_coupon = wait_for_chart('modified-duration-widget', count)
            assert 'Macaulay duration: 3.000000 years; modified duration: 3.000000 years' in chart_messages('modified-duration-widget')[-1]
            count = len(chart_messages('modified-duration-widget'))
            modified_control('Coupons').locator('select').select_option(label='Quarterly')
            quarterly_zero = wait_for_chart('modified-duration-widget', count)
            assert len(quarterly_zero['durationWeights']['series']['PV weight']) == 12
            assert quarterly_zero['durationSensitivity']['series'] == zero_coupon['durationSensitivity']['series']
            assert len(chart_messages('duration-widget')) == nominal_duration_count
            assert not errors, errors
            print('PASS: continuous/nominal duration controls, DV01 scaling, finite-shift errors, zero coupons, and separate instances of the shared helper are verified.', flush=True)

            page.goto(f"{base_url.rstrip('/')}/2.3-black-litterman.html", wait_until='domcontentloaded', timeout=120000)
            page.wait_for_function("document.querySelector('button.run:not(:disabled)')", timeout=120000)
            bl_editor = editor_by_id('black-litterman-widget')
            bl_output = output_for(bl_editor)
            markdown = (Path(__file__).resolve().parents[1] / 'docs/2.3-black-litterman.md').read_text()
            examples = {editor: code for code, editor in re.findall(
                r'```python:line-numbers\n(.*?)\n```\s*<Editor id="([^"]+)"\s*/>', markdown, re.S)}
            # Source scanning would choose the wrong helper here. The actual
            # Python callback, exported by the worker, is the routing authority.
            alias_code = '# pok.show_duration_echart is unrelated\n' + examples['black-litterman-widget'].replace(
                'pok.show_black_litterman_echart,', 'getattr(pok, "show_" + "black_litterman_echart"),')
            bl_editor.locator('.cm-content').click()
            page.keyboard.press('Control+a')
            page.keyboard.insert_text(alias_code)
            bl_editor.locator('button.run').click()
            bl_before = wait_for_chart('black-litterman-widget')
            bl_output.get_by_role('slider').first.wait_for(timeout=30000)
            assert bl_output.get_by_role('slider').count() == 4
            assert bl_output.locator('select').count() == 1
            assert bl_output.locator('canvas').count() == 2

            def bl_control(label):
                return bl_output.locator('label.widget-label').filter(has_text=re.compile(f'^{re.escape(label)}$')).locator('..')

            count = len(chart_messages('black-litterman-widget'))
            bl_control('Confidence').get_by_role('slider').press('Home')
            no_views = wait_for_chart('black-litterman-widget', count)
            assert all(math.isclose(a, b, abs_tol=1e-6) for a, b in zip(no_views['blWeights']['series']['Updated'], [60, 40]))
            assert no_views['blMeans']['series']['Posterior'] == no_views['blMeans']['series']['Prior']
            request = page.evaluate('window.widgetRequests.at(-1)')
            assert 'pok.show_black_litterman_echart(' in request['code'] and 'confidence=0' in request['code']
            assert 'show_duration_echart' not in request['code']

            count = len(chart_messages('black-litterman-widget'))
            bl_control('Confidence').get_by_role('slider').press('End')
            exact = wait_for_chart('black-litterman-widget', count)
            means = exact['blMeans']['series']['Posterior']
            assert math.isclose(means[0] - means[1], 8, abs_tol=1e-9)
            assert 'predictive spread volatility: 19.494%' in chart_messages('black-litterman-widget')[-1]
            count = len(chart_messages('black-litterman-widget'))
            bl_control('View spread').get_by_role('slider').press('End')
            strong = wait_for_chart('black-litterman-widget', count)
            assert math.isclose(strong['blWeights']['series']['Updated'][0], 100, abs_tol=1e-6)
            count = len(chart_messages('black-litterman-widget'))
            bl_control('View spread').get_by_role('slider').press('Home')
            negative = wait_for_chart('black-litterman-widget', count)
            assert math.isclose(negative['blWeights']['series']['Updated'][0], 0, abs_tol=1e-6)

            bl_output.locator('button.reset').click()
            count = len(chart_messages('black-litterman-widget'))
            bl_editor.locator('button.run').click()
            default = wait_for_chart('black-litterman-widget', count)
            bl_output.get_by_role('slider').first.wait_for(timeout=30000)
            count = len(chart_messages('black-litterman-widget'))
            bl_control('Prior tau').get_by_role('slider').press('End')
            high_tau = wait_for_chart('black-litterman-widget', count)
            for key in ('blMeans', 'blWeights'):
                assert all(math.isclose(a, b, abs_tol=1e-6) for a, b in zip(
                    high_tau[key]['series'].get('Posterior', high_tau[key]['series'].get('Updated')),
                    default[key]['series'].get('Posterior', default[key]['series'].get('Updated'))))
            count = len(chart_messages('black-litterman-widget'))
            bl_control('Risk matrix').locator('select').select_option(label='Predictive covariance')
            predictive = wait_for_chart('black-litterman-widget', count)
            assert predictive['blMeans'] == high_tau['blMeans']
            assert predictive['blWeights']['series']['Updated'] != high_tau['blWeights']['series']['Updated']
            count = len(chart_messages('black-litterman-widget'))
            bl_control('Risk aversion').get_by_role('slider').press('ArrowRight')
            changed_delta = wait_for_chart('black-litterman-widget', count)
            assert all(math.isclose(a, 1.2 * b, abs_tol=1e-9) for a, b in zip(
                changed_delta['blMeans']['series']['Prior'], bl_before['blMeans']['series']['Prior']))
            assert 'delta=3' in page.evaluate('window.widgetRequests.at(-1).code')
            count = len(chart_messages('black-litterman-widget'))
            editor_by_id('black-litterman-setup').locator('button.run').click()
            wait_for_done('black-litterman-setup')
            assert len(chart_messages('black-litterman-widget')) == count
            assert bl_output.locator('canvas').count() == 2
            assert not errors, errors
            print('PASS: Black–Litterman callback aliases, confidence endpoints, constrained weights, tau, risk-matrix choice, risk aversion, and editor isolation are verified.', flush=True)

            page.goto(f"{base_url.rstrip('/')}/2.4-robust-portfolios.html", wait_until='domcontentloaded', timeout=120000)
            page.wait_for_function("document.querySelector('button.run:not(:disabled)')", timeout=120000)
            rp_editor = editor_by_id('risk-parity-widget')
            rp_output = output_for(rp_editor)
            rp_editor.locator('button.run').click()
            rp_default = wait_for_chart('risk-parity-widget')
            rp_output.get_by_role('slider').first.wait_for(timeout=30000)
            assert rp_output.get_by_role('slider').count() == 4
            assert rp_output.locator('canvas').count() == 2
            assert all(math.isclose(a, b, abs_tol=1e-6) for a, b in zip(rp_default['riskParityWeights']['series']['GMV'], [12.5, 87.5]))
            assert all(math.isclose(a, b, abs_tol=1e-6) for a, b in zip(rp_default['riskParityShares']['series']['Risk budget'], [50, 50]))

            def rp_control(label):
                return rp_output.locator('label.widget-label').filter(has_text=re.compile(f'^{re.escape(label)}$')).locator('..').get_by_role('slider')

            count = len(chart_messages('risk-parity-widget'))
            rp_control('Correlation').press('Home')
            # Slider initialization can itself emit a rounded default value.
            # Wait for the requested negative-correlation result, not that earlier update.
            page.wait_for_function("""count => {
                const messages = window.widgetMessages.filter(m => m.id === 'risk-parity-widget' && m.echart);
                if (messages.length <= count) return false;
                const payload = JSON.parse(messages.at(-1).echart.split('<ECHARTS_DATA>')[1]);
                return payload.riskParityShares.series.EW[1] < 0;
            }""", arg=count, timeout=30000)
            negative_corr = wait_for_chart('risk-parity-widget', count)
            assert negative_corr['riskParityShares']['series']['EW'][1] < 0
            assert all(math.isclose(a, b, abs_tol=1e-6) for a, b in zip(
                negative_corr['riskParityWeights']['series']['Risk budget'], rp_default['riskParityWeights']['series']['Risk budget']))
            count = len(chart_messages('risk-parity-widget'))
            rp_control('Equity risk share').press('Home')
            unequal = wait_for_chart('risk-parity-widget', count)
            assert all(math.isclose(a, b, abs_tol=1e-6) for a, b in zip(unequal['riskParityShares']['series']['Risk budget'], [10, 90]))
            count = len(chart_messages('risk-parity-widget'))
            rp_control('Correlation').press('End')
            positive_corr = wait_for_chart('risk-parity-widget', count)
            assert positive_corr['riskParityWeights']['series']['Risk budget'] != unequal['riskParityWeights']['series']['Risk budget']
            for control in ('Equity vol', 'Bond vol'):
                count = len(chart_messages('risk-parity-widget'))
                rp_control(control).press('End')
                changed = wait_for_chart('risk-parity-widget', count)
                assert all(math.isclose(a, b, abs_tol=1e-6) for a, b in zip(changed['riskParityShares']['series']['Risk budget'], [10, 90]))
                assert math.isclose(sum(changed['riskParityWeights']['series']['Risk budget']), 100, abs_tol=1e-6)
            request = page.evaluate('window.widgetRequests.at(-1)')
            assert request['id'] == 'risk-parity-widget' and 'pok.show_risk_parity_echart(' in request['code']
            assert 'vol_equity=0.5' in request['code'] and 'vol_bond=0.3' in request['code'] and 'equity_budget=0.1' in request['code']
            count = len(chart_messages('risk-parity-widget'))
            editor_by_id('robust-portfolios-setup').locator('button.run').click()
            wait_for_done('robust-portfolios-setup')
            assert len(chart_messages('risk-parity-widget')) == count
            rp_control('Equity risk share').press('End')
            final = wait_for_chart('risk-parity-widget', count)
            assert math.isclose(final['riskParityShares']['series']['Risk budget'][0], 90, abs_tol=1e-6)
            assert not errors, errors
            print('PASS: risk-budget controls distinguish capital/risk, retain signed hedge contributions, meet unequal budgets, and preserve editor isolation.', flush=True)
            check_unavailable_storage(browser, base_url)
            check_chart_protocol(browser, base_url)
            check_runtime_failure(browser, base_url)
            check_python_input(browser, base_url)
            browser.close()
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--site-dir", type=Path)
    target.add_argument("--base-url", help="Existing VitePress server, e.g. http://localhost:5173")
    args = parser.parse_args()
    if args.site_dir and not (args.site_dir / "1.3-diversification.html").is_file():
        parser.error("--site-dir must contain a fresh VitePress production build")
    run(args.site_dir.resolve() if args.site_dir else None, args.base_url)
