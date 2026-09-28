"""Run every chapter cell and check chart layout at desktop and phone widths.

Uses the running VitePress dev server so ECharts' measured axis/legend bounds
can also be inspected. Optional screenshots are saved outside the repository.
"""

import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright


def audit(base_url, chapter, screenshots=None):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
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
        page.goto(f"{base_url.rstrip('/')}/{chapter}", wait_until="domcontentloaded", timeout=120000)
        page.wait_for_function("document.querySelector('button.run:not(:disabled)')", timeout=120000)
        ids = page.locator("[data-editor-id]").evaluate_all("els => els.map(el => el.dataset.editorId)")
        for editor_id in ids:
            page.locator(f'[data-editor-id="{editor_id}"] button.run').click()
            page.wait_for_function("id => window.chapterMessages.some(m => m.id === id && m.done)",
                                   arg=editor_id, timeout=180000)
            failures = page.evaluate("id => window.chapterMessages.filter(m => m.id === id && m.error && /Traceback|Error:/.test(m.output || ''))", editor_id)
            assert not failures, (editor_id, failures)
        expected = {"1.3-diversification": (37, 26), "1.2-optimization": (20, 15)}[chapter]
        assert len(ids) == expected[0], len(ids)
        panels = page.locator(".chart-panel")
        assert panels.count() == expected[1], panels.count()

        for width in (1920, 1440, 390, 320):
            page.set_viewport_size({"width": width, "height": 1000 if width > 600 else 844})
            page.wait_for_timeout(1200)
            measurements = panels.evaluate_all("""panels => panels.map(panel => {
                const el = panel.querySelector('.chart');
                const chart = el.__vueParentComponent?.setupState?.chart;
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
            print(f"PASS: {chapter}, {len(measurements)} charts at {width}px: headers, axes, legends, canvas sizing, and page width.", flush=True)

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
        assert not errors, errors
        print(f"PASS: all {len(ids)} cells executed in order without Python or browser errors.", flush=True)
        browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:5173")
    parser.add_argument("--chapter", choices=["1.3-diversification", "1.2-optimization"], default="1.3-diversification")
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    audit(args.base_url, args.chapter, args.screenshots)
