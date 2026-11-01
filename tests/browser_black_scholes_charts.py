"""Check browser-produced prices, hedge ledgers, limit controls, and navigation."""
import math

from browser_robust_charts import payload_for
from browser_ml_charts import check_rendered


EDITORS = ('bs-conventions', 'bs-normal', 'bs-integral', 'bs-prices', 'bs-pde',
           'bs-parity', 'bs-limits-widget', 'bs-stock-hedge', 'bs-futures-hedge')


def near(actual, expected, tolerance=1e-8):
    assert math.isclose(actual, expected, abs_tol=tolerance), (actual, expected)


def check_defaults(page, inspect_axes):
    if inspect_axes:
        for editor in EDITORS:
            check_rendered(page, editor)
    means = payload_for(page, 'bs-conventions')['bsMeanConventions']['series']
    near(means['Real-world assumption'][-1][1], 100*math.exp(.08))
    near(means['Pricing distribution'][-1][1], 105)
    cutoff = payload_for(page, 'bs-normal')['bsNormalCutoff']['series']['Exercise cutoff'][0][0]
    near(cutoff, -(math.log(1.05)-.02)/.2)
    prices = payload_for(page, 'bs-prices')['bsSpotPrices']['series']
    for call, put in zip(prices['Call'], prices['Put']):
        near(call[1]-put[1], call[0]-100/1.05)
    near(prices['Call'][50][1], 10.38627949671952)
    near(prices['Put'][50][1], 5.62437473481475)
    pde = payload_for(page, 'bs-pde')['bsPDEBalance']['series']['PDE term']
    near(sum(pde), 0, 1e-10)
    parity = payload_for(page, 'bs-parity')['bsForwardParity']['series']
    for synthetic, forward in zip(parity['Financed call minus put'], parity['Fair forward']):
        near(synthetic[1], forward[1])
        near(forward[1], forward[0]-105)
    stock = payload_for(page, 'bs-stock-hedge')
    hedge = stock['bsStockHedge']['series']
    near(hedge['Hedge account'][0][1], prices['Call'][50][1])
    near(hedge['Call liability'][0][1], prices['Call'][50][1])
    near(hedge['Hedge account'][-1][1]-hedge['Call liability'][-1][1],
         stock['bsStockErrors']['series']['Stock hedge error'][1])
    errors = payload_for(page, 'bs-futures-hedge')['bsFuturesErrors']['series']
    assert errors['Stock hedge'] == stock['bsStockErrors']['series']['Stock hedge error']
    assert abs(errors['Futures hedge'][-1]-errors['Stock hedge'][-1]) < .001
    assert abs(errors['Stock hedge'][1]) > .9  # accounting does not erase trading error
    exercise = page.locator('[data-editor-output="bs-exercise"]').inner_text()
    for value in ('5.506246474', '8.457752674', '-32.429577848', '-0.642223652'):
        assert value in exercise, value
    assert page.locator('[data-editor-output="bs-exercise"] .jupyter-widgets').count() == 0
    print('PASS: pricing probabilities, formula values, PDE, parity, hedge residuals, and exercise answers.', flush=True)


def check_controls(page, inspect_axes):
    output = page.locator('[data-editor-output="bs-limits-widget"]')
    sliders = output.get_by_role('slider')
    assert sliders.count() == page.get_by_role('slider').count() == 2
    frozen = {editor: payload_for(page, editor) for editor in EDITORS if editor != 'bs-limits-widget'}
    for time, vol, time_keys, vol_keys in [
            (1., .2, [], []), (1., 0., [], ['Home']), (0., 0., ['Home'], []),
            (0., .6, [], ['End']), (2., .6, ['End'], []),
            (1., .2, ['Home']+['ArrowRight']*4, ['Home']+['ArrowRight']*4)]:
        for key in time_keys:
            sliders.nth(0).press(key)
        for key in vol_keys:
            sliders.nth(1).press(key)
        label = f'Remaining years: {time:.2f}; volatility: {vol:.2f}'
        page.wait_for_function("""label => window.chapterMessages.filter(m => m.id === 'bs-limits-widget' && m.echart)
            .at(-1)?.echart.includes(label)""", arg=label, timeout=30000)
        chart = payload_for(page, 'bs-limits-widget')['bsLimits']
        series = chart['series']
        pv = 100/1.05**time
        for call, put in zip(series['Call'], series['Put']):
            near(call[1]-put[1], call[0]-pv)
            assert call[1] >= max(call[0]-pv, 0)-1e-10
            assert put[1] >= max(pv-put[0], 0)-1e-10
            if time == 0 or vol == 0:
                near(call[1], max(call[0]-pv, 0))
                near(put[1], max(pv-put[0], 0))
        assert series['Call at 100'][0] == series['Call'][50]
        assert series['Put at 100'][0] == series['Put'][50]
        output.locator('.text-output').get_by_text(label, exact=False).wait_for()
        if inspect_axes:
            page.wait_for_function("""expected => {
                const chart = document.querySelector('[data-editor-output="bs-limits-widget"] .chart')
                    .__vueParentComponent.exposed.chart.getOption();
                return Math.abs(chart.series.find(s => s.name === 'Call').data[50][1] - expected) < 1e-9;
            }""", arg=series['Call'][50][1])
            check_rendered(page, 'bs-limits-widget')
            markers = output.locator('.chart').evaluate("""el => el.__vueParentComponent.exposed.chart.getOption()
                .series.filter(s => s.name.endsWith('at 100')).map(s => [s.type, s.symbol, s.symbolSize, s.itemStyle.borderWidth])""")
            assert markers == [['scatter', 'diamond', 18, 2]]*2
        for editor, original in frozen.items():
            assert payload_for(page, editor) == original, editor
    assert page.locator('.chart-panel').count() == 10
    print('PASS: standalone two-control widget, expiry and volatility boundaries, markers, parity, and output isolation.', flush=True)


def check_navigation(page):
    page.evaluate('window.bsNavigationSentinel = true')
    page.locator('.vp-doc').get_by_role('link', name='The Greeks and Hedging', exact=True).click()
    page.wait_for_function("location.hash === '#greeks' && !!document.getElementById('greeks')")
    assert page.get_by_role('slider').count() == 0
    page.locator('.vp-doc').get_by_role('link', name='Deriving and Using Black–Scholes', exact=True).first.click()
    page.wait_for_function("document.querySelector('.vp-doc h1')?.textContent.includes('Deriving and Using Black')")
    assert page.evaluate('window.bsNavigationSentinel === true')
    assert page.locator('.chart-panel').count() == 0
    page.evaluate('window.chapterMessages = []')
    page.locator('[data-editor-id="bs-limits-widget"] button.run').click()
    sliders = page.locator('[data-editor-output="bs-limits-widget"]').get_by_role('slider')
    sliders.nth(1).wait_for(timeout=30000)
    sliders.nth(1).press('Home')
    page.wait_for_function("""() => window.chapterMessages.filter(m => m.id === 'bs-limits-widget' && m.echart)
        .at(-1)?.echart.includes('Remaining years: 1.00; volatility: 0.00')""", timeout=30000)
    assert page.locator('.chart-panel').count() == 1
    assert not page.evaluate('window.chapterMessages.some(m => m.error)')
    print('PASS: named next-topic navigation and remounted widget retain a working runtime.', flush=True)
