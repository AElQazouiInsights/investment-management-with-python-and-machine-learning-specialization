"""Exercise the built site with Chromium, real Pyodide, and real widget controls.

Run explicitly with --site-dir pointing to a fresh VitePress production build.
Requires Playwright, its Chromium browser, and network access for Pyodide packages.
"""

import argparse
import functools
import http.server
import json
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
