"""Check browser calibration, margin accounting, independent controls, and routing."""
import math

from browser_robust_charts import payload_for
from browser_ml_charts import check_rendered


EDITORS = ('basis-carry', 'basis-dividend-dates', 'basis-executable', 'basis-margin',
           'basis-implied', 'basis-identification-widget', 'basis-curve-fit',
           'basis-dividend-fit', 'basis-option-parity', 'basis-calendar', 'basis-stress')


def near(actual, expected, tolerance=1e-7):
    assert math.isclose(actual, expected, abs_tol=tolerance), (actual, expected)


def check_defaults(page, inspect_axes):
    if inspect_axes:
        for editor in EDITORS:
            check_rendered(page, editor)
    carry = payload_for(page, 'basis-carry')['basisCarry']['series']
    for rate, quote in carry['Model quote']:
        near(quote+30, 5000*math.exp(rate/100*.25))
    band = payload_for(page, 'basis-executable')['basisExecutableBand']['series']
    for long, short in zip(band['Cash-and-carry'], band['Reverse carry']):
        assert min(long[1], short[1]) < 0
    margin = payload_for(page, 'basis-margin')
    near(margin['basisMarginLiquidity']['series']['Path A'][1][1], 2100)
    near(margin['basisMarginLiquidity']['series']['Path B'][1][1], 0)
    for path, profit in [('Path A', 148.26920670232937), ('Path B', 155.30429760532968)]:
        near(margin['basisMarginWealth']['series'][path][-1][1]-2500*math.exp(.01), profit)
    fit = payload_for(page, 'basis-curve-fit')['basisCurveResiduals']['series']
    for name in ('Plain fit', 'Smoothed fit'):
        assert all(abs(value) < 1 for value in fit[name])
    parity = payload_for(page, 'basis-option-parity')['basisParityFit']['series']
    assert max(abs(y) for _, y in parity['Clean quotes']) < 1e-8
    assert max(abs(y) for _, y in parity['One stale put']) > 1
    calendar = payload_for(page, 'basis-calendar')['basisCalendarAttribution']['series']['Contribution']
    assert calendar == [-100, 80, -20]
    stress = payload_for(page, 'basis-stress')['basisStress']['series']['Amount']
    near(sum(stress[:3]), stress[3])
    near(stress[2], -200)
    exercise = page.locator('[data-editor-output="basis-exercise"]').inner_text()
    for value in ('4060.805360107', '4.938522518%', '0.805360107', '-20.00'):
        assert value in exercise, value
    assert page.locator('[data-editor-output="basis-exercise"] .jupyter-widgets').count() == 0
    print('PASS: browser carry, funding, quote residuals, parity, calendar P&L, stress, and exercise.', flush=True)


def check_controls(page, inspect_axes):
    output = page.locator('[data-editor-output="basis-identification-widget"]')
    slider = output.get_by_role('slider')
    assert slider.count() == page.get_by_role('slider').count() == 1
    frozen = {editor: payload_for(page, editor) for editor in EDITORS if editor != 'basis-identification-widget'}
    for rate, keys in [(5, []), (4, ['Home']), (8, ['End']), (6, ['Home']+['ArrowRight']*8)]:
        for key in keys:
            slider.press(key)
        label = f'Financing assumption: {rate:.2f}%'
        page.wait_for_function("""label => window.chapterMessages.filter(m => m.id === 'basis-identification-widget' && m.echart)
            .at(-1)?.echart.includes(label)""", arg=label, timeout=30000)
        chart = payload_for(page, 'basis-identification-widget')['basisIdentification']
        selected = chart['series']['Selected assumption'][0]
        near(selected[0], rate)
        near(5000*math.exp(selected[0]/100*.25)-selected[1], 5040)
        output.locator('.text-output').get_by_text(label, exact=False).wait_for()
        if inspect_axes:
            page.wait_for_function("""rate => document.querySelector('[data-editor-output="basis-identification-widget"] .chart')
                .__vueParentComponent.exposed.chart.getOption().series.find(s => s.name === 'Selected assumption').data[0][0] === rate""", arg=rate)
            check_rendered(page, 'basis-identification-widget')
            marker = output.locator('.chart').evaluate("""el => {
                const s = el.__vueParentComponent.exposed.chart.getOption().series.find(s => s.name === 'Selected assumption');
                return [s.type, s.symbol, s.symbolSize, s.itemStyle.color, s.itemStyle.borderWidth];
            }""")
            assert marker == ['scatter', 'diamond', 18, '#ea580c', 2]
        for editor, original in frozen.items():
            assert payload_for(page, editor) == original, editor
    assert page.locator('.chart-panel').count() == 13
    print('PASS: independent identification widget, rate boundaries, marker contrast, and output isolation.', flush=True)


def check_navigation(page):
    page.evaluate('window.basisNavigationSentinel = true')
    page.locator('.vp-doc').get_by_role('link', name='The Greeks and Hedging', exact=True).last.click()
    page.wait_for_function("document.querySelector('.vp-doc h1')?.textContent.includes('The Greeks and Hedging')")
    assert page.get_by_role('slider').count() == 0
    page.locator('.vp-doc').get_by_role('link', name='Futures Basis, Dividends, and Implied Financing', exact=True).first.click()
    page.wait_for_function("document.querySelector('.vp-doc h1')?.textContent.includes('Futures Basis')")
    assert page.evaluate('window.basisNavigationSentinel === true')
    assert page.locator('.chart-panel').count() == 0
    page.evaluate('window.chapterMessages = []')
    page.locator('[data-editor-id="basis-identification-widget"] button.run').click()
    slider = page.locator('[data-editor-output="basis-identification-widget"]').get_by_role('slider')
    slider.wait_for(timeout=30000)
    slider.press('End')
    page.wait_for_function("""() => window.chapterMessages.filter(m => m.id === 'basis-identification-widget' && m.echart)
        .at(-1)?.echart.includes('Financing assumption: 8.00%')""", timeout=30000)
    assert page.locator('.chart-panel').count() == 1
    assert not page.evaluate('window.chapterMessages.some(m => m.error)')
    print('PASS: named next-chapter navigation and remounted basis widget.', flush=True)
