"""Actual forward-contract chart data, live spot changes, and output isolation."""
import math
import re

from browser_robust_charts import payload_for
from browser_ml_charts import check_rendered


EDITORS = ('forward-payoffs', 'forward-financing', 'forward-arbitrage',
           'forward-review', 'forward-value-widget', 'forward-hedge')


def check_defaults(page, inspect_axes):
    if inspect_axes:
        for editor in EDITORS:
            check_rendered(page, editor)
        bounds = page.locator('[data-editor-output="forward-arbitrage"] .chart').evaluate(
            "el => el.__vueParentComponent.exposed.chart.getModel().getComponent('xAxis').axis.scale.getExtent()")
        assert bounds == [90, 120], bounds
    payoffs = payload_for(page, 'forward-payoffs')['forwardPayoffs']
    assert payoffs['xAxis']['name'] == 'Maturity spot (GBP/unit)'
    long = dict(payoffs['series']['Long'])
    short = dict(payoffs['series']['Short'])
    assert [long[s] for s in (80, 100, 105, 120, 140)] == [-250, -50, 0, 150, 350]
    assert all(short[s] == -long[s] for s in long)
    financing = payload_for(page, 'forward-financing')['forwardMaturities']
    assert dict(financing['series']['Financed purchase'])[1] == 105
    assert abs(dict(financing['series']['Financed purchase'])[2] - 110.25) < 1e-10
    arbitrage = payload_for(page, 'forward-arbitrage')['forwardArbitrage']['series']
    assert dict(arbitrage['Buy asset; sell forward'])[110] == 5
    assert dict(arbitrage['Sell asset; buy forward'])[100] == 5
    review = payload_for(page, 'forward-review')['forwardReview']
    assert review['xAxis']['name'] == 'Current spot (GBP/unit)'
    expected = 10 * (110 - 105 / math.sqrt(1.05))
    assert abs(dict(review['series']['Existing long'])[110] - expected) < 1e-9
    hedge = payload_for(page, 'forward-hedge')['forwardHedge']['series']
    assert all(y == 1050 for x, y in hedge['Purchase plus long forward'])
    assert all(y == 10*x for x, y in hedge['Market purchase alone'])
    answer = page.locator('[data-editor-output="forward-exercise"]').inner_text()
    assert all(number in answer for number in ('135.20', '40.00', '-60.80'))
    assert page.locator('[data-editor-output="forward-exercise"] .jupyter-widgets').count() == 0
    print('PASS: signed payoffs, financing, both arbitrage directions, discounted old-contract value, and purchase hedge reconcile.', flush=True)


def check_controls(page, inspect_axes):
    output = page.locator('[data-editor-output="forward-value-widget"]')
    slider = output.get_by_role('slider')
    slider.wait_for(timeout=30000)
    assert page.get_by_role('slider').count() == 1
    frozen = {editor: payload_for(page, editor) for editor in EDITORS if editor != 'forward-value-widget'}
    for spot, key in ((110, None), (115, 'ArrowRight'), (60, 'Home'), (150, 'End'), (145, 'ArrowLeft'), (60, 'Home')):
        if key:
            slider.press(key)
        page.wait_for_function("""spot => {
            const message = window.chapterMessages.filter(m => m.id === 'forward-value-widget' && m.echart).at(-1);
            return message?.echart.includes(`Current spot: ${spot.toFixed(2)} GBP/unit`);
        }""", arg=spot, timeout=30000)
        payload = payload_for(page, 'forward-value-widget')['forwardValueExperiment']
        point = payload['series']['Selected spot'][0]
        assert point[0] == spot
        assert abs(point[1] - 10 * (spot - 105 / math.sqrt(1.05))) < 1e-9
        for x, y in payload['series']['Existing long']:
            assert abs(y - 10 * (x - 105 / math.sqrt(1.05))) < 1e-9
        output.locator('.text-output').get_by_text(f'Current spot: {spot:.2f} GBP/unit', exact=False).wait_for()
        text = output.locator('.text-output').inner_text()
        assert 'Existing delivery price: 105.00' in text
        assert 'Remaining term: 0.50 years' in text
        assert f'New forward delivery price: {spot * math.sqrt(1.05):.4f}' in text
        assert f'Existing ten-unit long value: {point[1]:.4f}' in text
        if inspect_axes:
            page.wait_for_function("""point => {
                const chart = document.querySelector('[data-editor-output="forward-value-widget"] .chart');
                return JSON.stringify(chart.__vueParentComponent.exposed.chart.getOption().series.find(s => s.name === 'Selected spot').data[0])
                    === JSON.stringify(point);
            }""", arg=point)
            check_rendered(page, 'forward-value-widget')
            chart = output.locator('.chart')
            chart.evaluate("el => el.__vueParentComponent.exposed.chart.dispatchAction({type:'showTip', seriesIndex:1, dataIndex:0})")
            chart.get_by_text('Selected spot', exact=False).first.wait_for()
            tooltip = chart.inner_text()
            assert '%' not in tooltip and ' pp' not in tooltip
            numbers = [float(value.replace(',', '')) for value in re.findall(r'-?\d[\d,]*(?:\.\d+)?', tooltip.replace('−', '-'))]
            assert len(numbers) == 1 and abs(numbers[0] - point[1]) < .000051, tooltip
        for editor, original in frozen.items():
            assert payload_for(page, editor) == original
    if inspect_axes:
        for editor in frozen:
            check_rendered(page, editor)
    assert page.locator('.chart-panel').count() == 6
    print('PASS: standalone spot widget, endpoints and intermediate changes preserve fixed terms, money units, and other outputs.', flush=True)
