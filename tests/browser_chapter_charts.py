"""Run every chapter cell and check chart layout at desktop and phone widths.

Use the dev server for measured ECharts axis/legend bounds. A production build
also supports execution, MathJax, canvas, and page-layout checks with --site-dir.
Optional screenshots are saved outside the repository.
"""

import argparse
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright


CHAPTERS = {
    "1.0-overview": (0, 0),
    "1.1-risks": (33, 9),
    "1.2-optimization": (20, 15),
    "1.3-diversification": (37, 26),
    "1.4-alm": (77, 33),
    "2.1-style-factors": (18, 7),
    "2.2-covariance": (23, 9),
    "2.3-black-litterman": (20, 10),
    "2.4-robust-portfolios": (18, 8),
    "3.0-overview": (0, 0),
    "4.0-overview": (0, 0),
}


def audit(base_url, chapter, screenshots=None, inspect_axes=True, browser_name='chromium'):
    with sync_playwright() as playwright:
        browser = getattr(playwright, browser_name).launch()
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, service_workers='block')
        external = []

        def same_origin_only(route):
            if urlsplit(route.request.url)[:2] != urlsplit(base_url)[:2]:
                external.append(route.request.url)
                route.abort()
            else:
                route.continue_()

        context.route('**/*', same_origin_only)
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
        page.add_init_script("""
            window.chapterMessages = [];
            const NativeWorker = window.Worker;
            window.Worker = class extends NativeWorker {
                constructor(...args) {
                    super(...args);
                    this.addEventListener('message', event => window.chapterMessages.push(event.data));
                }
            };
        """)
        page.goto(f"{base_url.rstrip('/')}/{chapter}.html", wait_until="domcontentloaded", timeout=120000)
        expected = CHAPTERS[chapter]
        page.locator('.vp-doc h1').wait_for()
        if expected[0]:
            page.wait_for_function("document.querySelector('button.run:not(:disabled)')", timeout=120000)
        ids = page.locator("[data-editor-id]").evaluate_all("els => els.map(el => el.dataset.editorId)")
        for editor_id in ids:
            page.locator(f'[data-editor-id="{editor_id}"] button.run').click()
            page.wait_for_function("id => window.chapterMessages.some(m => m.id === id && m.done)",
                                   arg=editor_id, timeout=180000)
            failures = page.evaluate("id => window.chapterMessages.filter(m => m.id === id && m.error && /Traceback|Error:/.test(m.output || ''))", editor_id)
            assert not failures, (editor_id, failures)
        assert len(ids) == expected[0], len(ids)
        assert len(ids) == len(set(ids)), "Editor IDs must be unique"
        assert page.locator('mjx-merror, [data-mml-node="merror"], .katex-error').count() == 0
        assert not page.get_by_text('[Invalid chart JSON:', exact=False).count()
        assert not page.get_by_text('[Incomplete chart JSON received]', exact=False).count()
        panels = page.locator(".chart-panel")
        assert panels.count() == expected[1], panels.count()
        assert not external, f'Unexpected off-site requests: {external}'
        if chapter == "2.3-black-litterman":
            assert page.locator('a[href="/2.3-black-litterman"]').count() > 0
            assert page.locator('a[href="https://github.com/AElQazouiInsights/investment-management-with-python-and-machine-learning-specialization"]').count() > 0
            if inspect_axes:
                mean_chart, weight_chart = page.locator('[data-editor-output="expected-return-shrinkage"] .chart').evaluate_all(
                    'els => els.map(el => el.__vueParentComponent.exposed.chart.getOption())')
                for chart in (mean_chart, weight_chart):
                    assert chart['xAxis'][0]['name'] == 'Weight on target'
                    assert chart['xAxis'][0]['data'] == [f'{5 * i}%' for i in range(21)]
                means = {s['name']: s['data'] for s in mean_chart['series']}
                weights = {s['name']: s['data'] for s in weight_chart['series']}
                for name, target in (('Equal return', (0.04, 0.04)), ('Equal Sharpe', (0.06, 0.03))):
                    for i in range(21):
                        equity = (1 - i / 20) * 0.12 + i / 20 * target[0]
                        bonds = (1 - i / 20) * 0.02 + i / 20 * target[1]
                        weight = min(1, max(0, (equity - bonds + 0.01) / 0.095))
                        assert abs(means[f'{name}: Equity'][i] - 100 * equity) < 1e-8
                        assert abs(means[f'{name}: Bonds'][i] - 100 * bonds) < 1e-8
                        assert abs(weights[name][i] - 100 * weight) < 1e-6
        if chapter == "1.4-alm" and inspect_axes:
            selected = page.locator('[data-editor-output="coupon-widget"] .chart').evaluate_all("""els =>
                els.map(el => el.__vueParentComponent.exposed.chart.getOption().series
                    .find(series => series.name.startsWith('Selected')))
            """)
            assert len(selected) == 2
            assert all(series['type'] == 'scatter' and series['showSymbol'] and series['symbol'] == 'diamond'
                       for series in selected), selected
            step_series = page.locator('[data-editor-output="glide-widget"] .chart').first.evaluate("""el =>
                el.__vueParentComponent.exposed.chart.getOption().series.find(series => series.name === 'Glide path')
            """)
            assert step_series['step'] == 'end'
            assert step_series['data'][-2:] == [[9.5, 20], [10, 20]]
            floor_series = page.locator('[data-editor-output="floor-widget"] .chart').first.evaluate("""el =>
                el.__vueParentComponent.exposed.chart.getOption().series
            """)
            styles = {series['name']: series['lineStyle'].get('type') for series in floor_series}
            assert styles['Floor PV'] == 'dashed' and styles['Floor allocator'] != 'dashed', styles

        if chapter == "2.1-style-factors" and inspect_axes:
            drift = page.locator('[data-editor-output="rolling-style-drift"] .chart').evaluate("el => el.__vueParentComponent.exposed.chart.getOption()")
            actual = next(series for series in drift['series'] if series['name'] == 'Actual')
            estimated = next(series for series in drift['series'] if series['name'] == 'Prior-window estimate')
            january = drift['xAxis'][0]['data'].index('2009-01')
            assert actual['step'] == 'start' and actual['data'][january] == 20
            assert abs(estimated['data'][january] - 80) < 1e-5
            benchmark = page.locator('[data-editor-output="berkshire-factor-benchmark"] .chart').evaluate("el => el.__vueParentComponent.exposed.chart.getOption()")
            assert benchmark['yAxis'][0]['type'] == 'log'
            assert benchmark['xAxis'][0]['data'][0] == '1989-12'
            assert all(series['data'][0] == 100 for series in benchmark['series'])

        if chapter == "2.2-covariance" and inspect_axes:
            rolling = page.locator('[data-editor-output="rolling-covariance-volatility"] .chart').evaluate("el => el.__vueParentComponent.exposed.chart.getOption()")
            for series, warmup in zip(rolling['series'], (11, 59)):
                assert series['data'][:warmup] == [None] * warmup
                assert series['data'][warmup] is not None
            wealth = page.locator('[data-editor-output="covariance-portfolio-evaluation"] .chart').evaluate("el => el.__vueParentComponent.exposed.chart.getOption()")
            assert wealth['yAxis'][0]['type'] == 'log'
            assert wealth['xAxis'][0]['data'][0] == '1977-12'
            assert all(len(series['data']) == 493 and series['data'][0] == 100 for series in wealth['series'])

        if chapter == "2.4-robust-portfolios":
            from browser_robust_charts import check_defaults, check_controls, check_execution_cleanup
            check_defaults(page, inspect_axes)

        for width in (1920, 1440, 390, 320):
            page.set_viewport_size({"width": width, "height": 1000 if width > 600 else 844})
            page.wait_for_timeout(1200)
            measurements = panels.evaluate_all("""panels => panels.map(panel => {
                const el = panel.querySelector('.chart');
                const chart = el.__vueParentComponent?.exposed?.chart;
                const box = el.getBoundingClientRect();
                const title = panel.querySelector('.chart-title');
                const caption = panel.querySelector('.chart-axis-caption');
                const model = chart?.getModel();
                function bounds(type) {
                    const component = model?.getComponent(type);
                    const group = component && chart.getViewOfComponentModel(component)?.group;
                    if (!group) return null;
                    const rect = group.getBoundingRect().clone();
                    rect.applyTransform(group.getComputedTransform());
                    return {x:rect.x, y:rect.y, width:rect.width, height:rect.height};
                }
                return {
                    title:title.textContent, width:box.width, height:box.height, left:box.left, right:box.right,
                    headingFits:title.scrollWidth <= title.clientWidth + 1,
                    captionFits:!caption || caption.scrollWidth <= caption.clientWidth + 1,
                    headerSeparated:Math.max(title.getBoundingClientRect().bottom, caption?.getBoundingClientRect().bottom || 0) <= box.top + 1,
                    x:bounds('xAxis'), y:bounds('yAxis'), legend:bounds('legend'),
                    legendType:chart?.getOption().legend?.[0]?.type,
                    canvasWidth:panel.querySelector('canvas')?.getBoundingClientRect().width,
                };
            })""")
            for index, item in enumerate(measurements):
                label = (width, item["title"])
                assert item["headingFits"] and item["captionFits"] and item["headerSeparated"], label
                assert item["left"] >= -1 and item["right"] <= width + 1, label
                assert item["width"] >= 260 and 320 <= item["height"] <= 400, label
                assert abs(item["canvasWidth"] - item["width"]) <= 1, label
                if inspect_axes:
                    assert item["x"] is not None and item["y"] is not None, "Run against the dev server to inspect ECharts bounds"
                    for axis in (item["x"], item["y"]):
                        assert axis["x"] >= -1 and axis["x"] + axis["width"] <= item["width"] + 1, (label, axis)
                        assert axis["y"] >= -1 and axis["y"] + axis["height"] <= item["height"] + 1, (label, axis)
                    assert item["legendType"] == "scroll", label
                    assert item["legend"]["y"] >= item["x"]["y"] + item["x"]["height"], label
                    assert item["legend"]["y"] + item["legend"]["height"] <= item["height"] + 1, label
                if screenshots:
                    screenshots.mkdir(parents=True, exist_ok=True)
                    panels.nth(index).screenshot(path=str(screenshots / f"{chapter}-{width}-{index:02d}.png"))
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
            checks = "headers, axes, legends, canvas sizing, and page width" if inspect_axes else "headers, canvas sizing, and page width"
            print(f"PASS: {chapter}, {len(measurements)} charts at {width}px: {checks}.", flush=True)

        if chapter == "1.3-diversification":
            page.set_viewport_size({"width": 1440, "height": 1000})
            page.wait_for_timeout(1200)
            for editor, index, label, percent in (("calculating-indexes-9", 1, "Industry pairs", False),
                                                   ("cppi-6", 2, "Risky weight", True)):
                chart = page.locator(f'[data-editor-output="{editor}"] .chart').nth(index)
                chart.scroll_into_view_if_needed()
                chart.hover(position={"x": 350, "y": 170})
                chart.get_by_text(label, exact=False).first.wait_for(timeout=10000)
                text = chart.inner_text()
                assert ("%" in text) == percent, (editor, text)
            print("PASS: axis tooltips show readable correlation and percentage values.", flush=True)
        if chapter == "2.4-robust-portfolios":
            check_controls(page, inspect_axes)
            check_execution_cleanup(page)
        assert not errors, errors
        assert not external, f'Unexpected off-site requests: {external}'
        print(f"PASS: all {len(ids)} cells executed in order without Python or browser errors.", flush=True)
        browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--base-url", default=None)
    target.add_argument("--site-dir", type=Path)
    parser.add_argument("--chapter", choices=CHAPTERS, default="1.3-diversification")
    parser.add_argument("--screenshots", type=Path)
    parser.add_argument("--browser", choices=['chromium', 'firefox'], default='chromium')
    args = parser.parse_args()
    if args.site_dir:
        import functools
        import http.server
        import threading
        from browser_widget_regression import IsolatedSiteHandler
        if not (args.site_dir / f"{args.chapter}.html").is_file():
            parser.error("--site-dir must contain a fresh VitePress production build")
        with http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(
                IsolatedSiteHandler, directory=str(args.site_dir.resolve()))) as server:
            threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                audit(f"http://127.0.0.1:{server.server_port}", args.chapter, args.screenshots, inspect_axes=False, browser_name=args.browser)
            finally:
                server.shutdown()
    else:
        audit(args.base_url or "http://localhost:5173", args.chapter, args.screenshots, browser_name=args.browser)
