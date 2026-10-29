"""Reconcile chapter 2.4 worker payloads, Vue chart options, and live controls."""

import json
import math
import re


EDITORS = (
    'risk-parity-widget', 'robust-gross-evaluation', 'robust-decision-attribution',
    'robust-allocation-sensitivity', 'robust-historical-turnover', 'robust-transaction-costs',
)


def payload_for(page, editor):
    text = page.evaluate("""id => {
        const messages = window.chapterMessages.filter(m => m.id === id);
        return messages.filter(m => m.echart).at(-1)?.echart
            || messages.map(m => m.output || '').join('');
    }""", editor)
    return json.JSONDecoder().raw_decode(text.split('<ECHARTS_DATA>', 1)[1])[0]


def check_rendered_payload(page, editor):
    payload = payload_for(page, editor)
    panels = page.locator(f'[data-editor-output="{editor}"] .chart-panel')
    charts = [value for value in payload.values() if isinstance(value, dict) and 'series' in value]
    assert panels.count() == len(charts), editor
    for index, expected in enumerate(charts):
        panel = panels.nth(index)
        chart = panel.locator('.chart')
        option = chart.evaluate('el => el.__vueParentComponent.exposed.chart.getOption()')
        assert panel.locator('.chart-title').inner_text() == expected['title']
        assert [series['name'] for series in option['series']] == list(expected['series']), editor
        assert option['legend'][0]['data'] == list(expected['series']), editor
        for series in option['series']:
            assert series['type'] == expected.get('type', 'line'), (editor, series['name'])
            assert series['data'] == expected['series'][series['name']], (editor, series['name'])
        assert option['xAxis'][0]['data'] == expected.get('xAxis', {}).get('data', payload.get('dates')), editor
        axis = expected.get('yAxis', {'type': 'value', 'name': expected.get('yAxisName')})
        assert option['yAxis'][0]['type'] == axis['type'], editor
        caption = axis['name'] + (' · logarithmic scale' if axis['type'] == 'log' else '')
        assert panel.locator('.chart-axis-caption').inner_text() == caption, editor
        tooltip = chart.evaluate("""el => {
            const option = el.__vueParentComponent.exposed.chart.getOption();
            return option.tooltip[0].valueFormatter(option.series[0].data[0]);
        }""")
        suffix = ' pp' if 'percentage points' in caption else '%' if '%' in caption else ''
        assert tooltip.endswith(suffix), (editor, tooltip)
        assert ('%' in tooltip) == ('%' in caption), (editor, tooltip)
        assert math.isclose(float(tooltip.removesuffix(suffix).replace(',', '')),
                            option['series'][0]['data'][0], abs_tol=0.000051), (editor, tooltip)
    return payload


def check_defaults(page, inspect_axes):
    if inspect_axes:
        for editor in EDITORS:
            check_rendered_payload(page, editor)
    gross = payload_for(page, 'robust-gross-evaluation')
    net = payload_for(page, 'robust-transaction-costs')
    assert gross['dates'] == net['dates']
    assert len(gross['dates']) == 289 and gross['dates'][0] == '1994-12' and gross['dates'][-1] == '2018-12'
    for name, values in gross['robustGrossWealth']['series'].items():
        net_values = net['robustNetWealth']['series'][name]
        assert values[0] == net_values[0] == 100
        assert all(n <= g + 1e-10 for n, g in zip(net_values, values))
    snapshot = payload_for(page, 'robust-decision-attribution')
    assert snapshot['snapshotWeights']['xAxis']['data'] == snapshot['snapshotRisk']['xAxis']['data']
    assert math.isclose(sum(snapshot['snapshotRisk']['series']['ERC']), 100 * 8 / 30, abs_tol=1e-6)
    print('PASS: chapter chart dates, whole-portfolio risk shares, and gross/net wealth reconcile'
          + ('; all eight Vue series, legends, captions, axes, and tooltip units match Python payloads.'
             if inspect_axes else '.'), flush=True)


def check_controls(page, inspect_axes):
    output = page.locator('[data-editor-output="risk-parity-widget"]')
    output.get_by_role('slider').first.wait_for(timeout=30000)
    assert output.get_by_role('slider').count() == 4
    params = {'Equity vol': 0.20, 'Bond vol': 0.10, 'Correlation': 0.25, 'Equity risk share': 0.50}

    def verify():
        equity, bonds, rho, budget = params.values()
        cross = rho * equity * bonds

        def shares(w):
            components = [w * (w * equity**2 + (1-w) * cross),
                          (1-w) * (w * cross + (1-w) * bonds**2)]
            return [100 * value / sum(components) for value in components]

        low, high = 0.0, 1.0
        for _ in range(80):
            middle = (low + high) / 2
            if shares(middle)[0] < 100 * budget:
                low = middle
            else:
                high = middle
        weights = {'EW': 0.5, 'GMV': min(1, max(0, (bonds**2-cross)/(equity**2+bonds**2-2*cross))),
                   'Risk budget': (low+high)/2}
        expected = {
            'riskParityWeights': {name: [100*w, 100*(1-w)] for name, w in weights.items()},
            'riskParityShares': {name: shares(w) for name, w in weights.items()},
        }
        page.wait_for_function("""expected => {
            const message = window.chapterMessages.filter(m => m.id === 'risk-parity-widget' && m.echart).at(-1);
            if (!message) return false;
            const actual = JSON.parse(message.echart.split('<ECHARTS_DATA>')[1]);
            return Object.entries(expected).every(([key, series]) => Object.entries(series).every(([name, values]) =>
                values.every((value, i) => Math.abs(value - actual[key].series[name][i]) < 1e-6)));
        }""", arg=expected, timeout=30000)
        # Wait for the corresponding Vue update, not only the worker message.
        if inspect_axes:
            page.wait_for_function("""expected => {
                const charts = [...document.querySelectorAll('[data-editor-output="risk-parity-widget"] .chart')];
                return charts.length === 2 && charts.every((el, i) => {
                    const series = el.__vueParentComponent.exposed.chart.getOption().series;
                    return series.every(s => Object.values(expected)[i][s.name].every((v, j) => Math.abs(v-s.data[j]) < 1e-6));
                });
            }""", arg=expected)
            check_rendered_payload(page, 'risk-parity-widget')
        text = output.locator('.text-output').inner_text()
        for name, w in weights.items():
            volatility = 100 * math.sqrt(w*w*equity**2 + 2*w*(1-w)*cross + (1-w)**2*bonds**2)
            holdings = 1 / (w*w + (1-w)**2)
            assert re.search(rf'{name}\s+{volatility:.4f}\s+{holdings:.4f}', text), (params, text)

    verify()
    for label, key, value in (
        ('Correlation', 'Home', -0.90), ('Equity risk share', 'Home', 0.10),
        ('Correlation', 'End', 0.90), ('Equity vol', 'End', 0.50),
        ('Bond vol', 'End', 0.30), ('Equity risk share', 'End', 0.90),
    ):
        control = output.locator('label.widget-label').filter(has_text=re.compile(f'^{re.escape(label)}$')).locator('..').get_by_role('slider')
        control.press(key)
        params[label] = value
        verify()
        if label == 'Correlation' and value < 0 and inspect_axes:
            chart = output.locator('.chart').nth(1)
            extent = chart.evaluate("el => el.__vueParentComponent.exposed.chart.getModel().getComponent('yAxis').axis.scale.getExtent()")
            assert extent[0] < 0 and extent[1] > 100, extent
            chart.evaluate("el => el.__vueParentComponent.exposed.chart.dispatchAction({type:'showTip', seriesIndex:0, dataIndex:1})")
            chart.get_by_text('-', exact=False).first.wait_for()
            assert '%' in chart.inner_text(), chart.inner_text()
    print('PASS: all four live sliders reconcile to independent two-asset calculations and summary statistics'
          + ('; Vue retains negative/>100% hedge contributions and unequal risk budgets.' if inspect_axes else '.'), flush=True)


def check_execution_cleanup(page):
    editor = page.locator('[data-editor-id="robust-portfolios-setup"]')

    def execute(code):
        page.evaluate('window.chapterMessages = []')
        editor.locator('.cm-content').click()
        page.keyboard.press('Control+a')
        page.keyboard.insert_text(code)
        editor.locator('button.run').click()
        page.wait_for_function("window.chapterMessages.some(m => m.id === 'robust-portfolios-setup' && m.done)", timeout=45000)
        messages = page.evaluate("window.chapterMessages.filter(m => m.id === 'robust-portfolios-setup')")
        assert not any(message.get('error') for message in messages), messages
        return ''.join(message.get('output', '') for message in messages)

    # A CPU-bound cell outlasts the yielding-code deadline, then must cancel the
    # overdue JS timer before Pyodide yields and serializes widget metadata.
    text = execute('''import time
deadline = time.monotonic() + 16
while time.monotonic() < deadline:
    pass
print("LONG_SYNC_COMPLETED")''')
    assert 'LONG_SYNC_COMPLETED' in text and 'timed out' not in text, text
    text = execute('''import asyncio
await asyncio.sleep(16)
print("SHOULD_NOT_COMPLETE")''')
    assert '[Execution timed out]' in text and 'SHOULD_NOT_COMPLETE' not in text, text
    text = execute('print("NEXT_CELL_RECOVERED")')
    assert 'NEXT_CELL_RECOVERED' in text, text
    print('PASS: long synchronous execution cancels the overdue timer; yielding-code timeout and subsequent execution still work.', flush=True)
