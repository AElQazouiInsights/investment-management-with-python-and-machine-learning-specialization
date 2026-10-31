"""Reconcile ML worker results, mixed ECharts series, and actual degree controls."""
import math

from browser_robust_charts import payload_for


EDITORS = ('ml-baseline', 'ml-fitted-line', 'ml-validation', 'ml-model-selection',
           'ml-complexity-widget', 'ml-final-test')


def check_rendered(page, editor):
    payload = payload_for(page, editor)
    panels = page.locator(f'[data-editor-output="{editor}"] .chart-panel')
    assert panels.count() == len(payload)
    for index, expected in enumerate(payload.values()):
        panel = panels.nth(index)
        option = panel.locator('.chart').evaluate('el => el.__vueParentComponent.exposed.chart.getOption()')
        assert panel.locator('.chart-title').inner_text() == expected['title']
        assert panel.locator('.chart-axis-caption').inner_text() == expected['yAxisName']
        assert option['legend'][0]['data'] == list(expected['series'])
        assert option['xAxis'][0]['type'] == expected['xAxis']['type']
        if expected['xAxis']['type'] == 'category':
            assert option['xAxis'][0]['data'] == expected['xAxis']['data']
        for series in option['series']:
            settings = expected.get('seriesOptions', {}).get(series['name'], {})
            assert series['type'] == settings.get('type', expected['type'])
            assert series['data'] == expected['series'][series['name']]
            if 'symbol' in settings:
                assert series['symbol'] == settings['symbol']
            if 'lineStyle' in settings:
                assert series['lineStyle']['type'] == settings['lineStyle']['type']


def close(actual, expected):
    assert len(actual) == len(expected)
    assert all(math.isclose(a, e, abs_tol=1e-10) for a, e in zip(actual, expected)), (actual, expected)


def check_defaults(page, inspect_axes):
    if inspect_axes:
        for editor in EDITORS:
            check_rendered(page, editor)
    baseline = payload_for(page, 'ml-baseline')['mlBaseline']
    assert baseline['xAxis']['data'] == ['2020-01', '2020-02', '2020-03', '2020-04']
    close(baseline['series']['Actual'], [-1, 1, 1, 3])
    close(baseline['series']['Training mean'], [1] * 4)
    validation = payload_for(page, 'ml-validation')['mlValidation']
    assert validation['xAxis']['data'] == ['2020-05', '2020-06', '2020-07', '2020-08']
    close(validation['series']['Fitted line'], [-.2, 1, 2.2, 1.6])
    selection = payload_for(page, 'ml-model-selection')['mlModelSelection']
    close(selection['series']['Training'], [2, .2, .2, 0])
    close(selection['series']['Validation'], [.5475, .0375, .0375, .1725])
    final = payload_for(page, 'ml-final-test')['mlFinalTest']
    assert final['xAxis']['data'] == ['2020-10', '2020-11', '2020-12', '2021-01']
    close(final['series']['Selected model'], [-.4227272727272727, .7088744588744589, 1.8404761904761904, 2.406277056277056])
    close(final['series']['Development mean'], [1.0625] * 4)
    assert '0.023728' in page.locator('[data-editor-output="ml-final-test"]').inner_text()
    assert page.locator('[data-editor-output="ml-check-understanding"] .jupyter-widgets').count() == 0
    print('PASS: ML baseline, model selection, final predictions, and decision/target months match worked answers.', flush=True)


def check_controls(page, inspect_axes):
    output = page.locator('[data-editor-output="ml-complexity-widget"]')
    slider = output.get_by_role('slider')
    slider.wait_for(timeout=30000)
    assert slider.count() == 1
    assert page.get_by_role('slider').count() == 1
    frozen = {editor: payload_for(page, editor) for editor in EDITORS if editor != 'ml-complexity-widget'}
    for degree, key in ((1, None), (2, 'ArrowRight'), (3, 'End'), (1, 'Home')):
        if key:
            slider.press(key)
        page.wait_for_function("""degree => {
            const messages = window.chapterMessages.filter(m => m.id === 'ml-complexity-widget');
            return messages.filter(m => m.echart).at(-1)?.echart.includes(`Polynomial degree: ${degree}`);
        }""", arg=degree, timeout=30000)
        payload = payload_for(page, 'ml-complexity-widget')
        fit = payload['mlComplexityFit']['series']
        assert set(fit) == {'Training', 'Validation', 'Fitted curve', 'Training mean'}
        assert len(fit['Training']) == len(fit['Validation']) == 4
        for x, y in fit['Fitted curve']:
            expected = .4 + 1.2*x if degree < 3 else 1 + x/3 - x*x + 2*x**3/3
            assert math.isclose(y, expected, abs_tol=1e-10)
        close(payload['mlComplexityError']['series']['Selected curve'], [.2, .0375] if degree < 3 else [0, .1725])
        output.locator('.text-output').get_by_text(f'Polynomial degree: {degree}', exact=False).wait_for()
        if inspect_axes:
            page.wait_for_function("""expected => {
                const el = document.querySelector('[data-editor-output="ml-complexity-widget"] .chart');
                return JSON.stringify(el.__vueParentComponent.exposed.chart.getOption().series.find(s => s.name === 'Fitted curve').data)
                    === JSON.stringify(expected);
            }""", arg=fit['Fitted curve'])
            check_rendered(page, 'ml-complexity-widget')
        for editor, original in frozen.items():
            assert payload_for(page, editor) == original, editor
    assert page.locator('.chart-panel').count() == 7
    print('PASS: standalone widget and degree 1/2/3/1 updates match analytical curves; other cell results remain isolated.', flush=True)
