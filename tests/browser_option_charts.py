"""Verify live option charts, financed break-even points, and slider isolation."""
import math

from browser_robust_charts import payload_for
from browser_ml_charts import check_rendered


EDITORS = ('options-payoffs', 'options-profit', 'options-call-replication', 'options-put-replication',
           'options-pricing-weights', 'options-parity', 'options-payoff-widget')


def close(actual, expected):
    assert len(actual) == len(expected)
    assert all(math.isclose(a, b, abs_tol=1e-9) for a, b in zip(actual, expected)), (actual, expected)


def check_defaults(page, inspect_axes):
    if inspect_axes:
        for editor in EDITORS:
            check_rendered(page, editor)
    payoff = payload_for(page, 'options-payoffs')
    profit = payload_for(page, 'options-profit')
    for who, sign in [('Holder', 1), ('Writer', -1)]:
        for name, values, cost in [('Call', [0, 0, 20], 12.5), ('Put', [20, 0, 0], 7.5)]:
            points = dict(payoff['optionsPayoff' + who]['series'][name])
            earnings = dict(profit['optionsProfit' + who]['series'][name])
            close([points[s] for s in (80, 100, 120)], [sign * v for v in values])
            close([earnings[s] for s in (80, 100, 120)], [sign * (v - cost) for v in values])
    for kind, values, cash, asset_name in [('call', [0, 20], -40, 'Asset holding'), ('put', [20, 0], 60, 'Short asset')]:
        data = payload_for(page, 'options-' + kind + '-replication')['options' + kind.title() + 'Replication']['series']
        close(data['Net portfolio'], values)
        close(data[kind.title() + ' payoff'], values)
        close(data['Cash account'], [cash, cash])
        close(data[asset_name], [v - cash for v in values])
    pricing = payload_for(page, 'options-pricing-weights')['optionsForecastProfit']['series']['Expected profit']
    close([pricing[i][1] for i in (0, 50, 80, 100)], [-12.5, -2.5, 3.5, 7.5])
    for chart in payload_for(page, 'options-parity').values():
        a, b = chart['series'].values()
        assert a == b
    assert 'Both model prices satisfy the bounds: True' in page.locator('[data-editor-output="options-bounds"]').inner_text()
    exercise = page.locator('[data-editor-output="options-exercise"]').inner_text()
    assert all(value in exercise for value in ('5.952381', '10.714286', '116.250000', '98.750000', '3.75 GBP'))
    assert page.locator('[data-editor-output="options-exercise"] .jupyter-widgets').count() == 0
    print('PASS: payoff signs, financed profit, both replications, pricing weights, parity, bounds, and exercise.', flush=True)


def check_controls(page, inspect_axes):
    output = page.locator('[data-editor-output="options-payoff-widget"]')
    slider = output.get_by_role('slider')
    slider.wait_for(timeout=30000)
    assert page.get_by_role('slider').count() == 1
    frozen = {editor: payload_for(page, editor) for editor in EDITORS if editor != 'options-payoff-widget'}
    scenarios = [(120., []), (0., ['Home']), (200., ['End']), (92.5, ['Home'] + ['ArrowRight'] * 37),
                 (100., ['ArrowRight'] * 3), (110., ['ArrowRight'] * 4), (112.5, ['ArrowRight']),
                 (120., ['ArrowRight'] * 3), (0., ['Home'])]
    for spot, keys in scenarios:
        for key in keys:
            slider.press(key)
        page.wait_for_function("""spot => {
            const message = window.chapterMessages.filter(m => m.id === 'options-payoff-widget' && m.echart).at(-1);
            return message?.echart.includes(`Final asset price: ${spot.toFixed(2)} GBP/unit`);
        }""", arg=spot, timeout=30000)
        payload = payload_for(page, 'options-payoff-widget')
        for name, sign, cost in [('Call', 1, 12.5), ('Put', -1, 7.5)]:
            data = payload['option' + name + 'Experiment']['series']
            amount = max(sign * (spot - 100), 0)
            close(data['Selected payoff'][0], [spot, amount])
            close(data['Selected profit'][0], [spot, amount - cost])
            for payoff, profit in zip(data['Payoff'], data['Financed profit']):
                assert abs(payoff[1] - profit[1] - cost) < 1e-9
        output.locator('.text-output').get_by_text(f'Final asset price: {spot:.2f} GBP/unit', exact=False).wait_for()
        text = output.locator('.text-output').inner_text()
        assert 'Call premium today: 11.904762 GBP' in text and 'Put premium today: 7.142857 GBP' in text
        if inspect_axes:
            page.wait_for_function("""spot => [...document.querySelectorAll('[data-editor-output="options-payoff-widget"] .chart')]
                .every(el => el.__vueParentComponent.exposed.chart.getOption().series
                    .filter(s => s.type === 'scatter').every(s => s.data[0][0] === spot))""", arg=spot)
            check_rendered(page, 'options-payoff-widget')
            styles = output.locator('.chart').evaluate_all("""els => els.flatMap(el =>
                el.__vueParentComponent.exposed.chart.getOption().series.filter(s => s.type === 'scatter')
                .map(s => ({color:s.itemStyle.color, opacity:s.itemStyle.opacity, border:s.itemStyle.borderWidth, size:s.symbolSize})))""")
            assert all(s['opacity'] == 1 and s['border'] == 2 and s['size'] >= 14 for s in styles)
            assert {s['color'] for s in styles} == {'#ea580c', '#db2777'}
        for editor, original in frozen.items():
            assert payload_for(page, editor) == original, editor
    assert page.locator('.chart-panel').count() == 11
    print('PASS: standalone final-price widget, both break-even points, strike, endpoints, and output isolation.', flush=True)


def check_navigation(page):
    page.evaluate('window.optionNavigationSentinel = true')
    page.locator('.vp-doc').get_by_role('link', name="Random Motion and Itô's Lemma", exact=True).click()
    page.wait_for_function("document.querySelector('.vp-doc h1')?.textContent.includes('Random Motion')")
    assert page.get_by_role('slider').count() == 0
    page.locator('.vp-doc').get_by_role('link', name='Options and Replication', exact=True).click()
    page.wait_for_function("document.querySelector('.vp-doc h1')?.textContent.includes('Options and Replication')")
    assert page.evaluate('window.optionNavigationSentinel === true'), 'Must use client-side navigation'
    assert page.locator('.chart-panel').count() == 0
    page.evaluate('window.chapterMessages = []')
    page.locator('[data-editor-id="options-payoff-widget"] button.run').click()
    output = page.locator('[data-editor-output="options-payoff-widget"]')
    slider = output.get_by_role('slider')
    slider.wait_for(timeout=30000)
    slider.press('End')
    page.wait_for_function("""() => window.chapterMessages.filter(m => m.id === 'options-payoff-widget' && m.echart)
        .at(-1)?.echart.includes('Final asset price: 200.00 GBP/unit')""")
    assert page.get_by_role('slider').count() == 1
    assert page.locator('.chart-panel').count() == 2
    assert not page.evaluate('window.chapterMessages.some(m => m.error)')
    print('PASS: mounted widget detaches on navigation; returning creates one working slider with the shared worker.', flush=True)
