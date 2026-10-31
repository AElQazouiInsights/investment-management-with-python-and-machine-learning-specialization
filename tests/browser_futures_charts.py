"""Reconcile futures settlement/margin charts and actual liquidity-slider changes."""
import math

from browser_robust_charts import payload_for
from browser_ml_charts import check_rendered


EDITORS = ('futures-daily-settlement', 'futures-cash-timing', 'futures-margin-ledger',
           'futures-two-paths', 'futures-liquidity-widget', 'futures-funding')


def close(actual, expected):
    assert len(actual) == len(expected)
    assert all(math.isclose(a, b, abs_tol=1e-8) for a, b in zip(actual, expected)), (actual, expected)


def check_defaults(page, inspect_axes):
    if inspect_axes:
        for editor in EDITORS:
            check_rendered(page, editor)
        step_series = page.locator('[data-editor-output="futures-cash-timing"] .chart').evaluate(
            'el => el.__vueParentComponent.exposed.chart.getOption().series')
        assert all(series['step'] == 'end' for series in step_series)
    daily = payload_for(page, 'futures-daily-settlement')['futuresDailyCash']
    assert daily['xAxis']['data'] == ['362', '363', '364', '365']
    close(daily['series']['Long'], [-50, -20, 140, 80])
    close(daily['series']['Short'], [50, 20, -140, -80])
    timing = payload_for(page, 'futures-cash-timing')['futuresCashTiming']['series']
    close(timing['Futures'], [0, -50, -70, 70, 150])
    close(timing['Forward'], [0, 0, 0, 0, 150])
    margin = payload_for(page, 'futures-margin-ledger')
    assert margin['futuresMarginBalance']['xAxis']['data'] == ['0', '361', '362', '363', '364', '365']
    balances = margin['futuresMarginBalance']['series']
    close(balances['Before funding/close'], [0, 100, 50, 80, 220, 300])
    close(balances['Closing balance'], [100, 100, 100, 80, 220, 0])
    assert balances['Maintenance level'] == [75] * 5 + [None]
    close(margin['futuresOutsideCash']['series']["Owner's cash flow"], [-100, 0, -50, 0, 0, 300])
    prices = payload_for(page, 'futures-two-paths')['futuresTwoPaths']['series']
    close(prices['A: fall then recover'], [105, 100, 98, 112, 120])
    close(prices['B: steady rise'], [105, 110, 115, 118, 120])
    funding = payload_for(page, 'futures-funding')['futuresFundedComparison']['series']
    close(funding['After funding'], [144.97994522673744, 145, 150])
    close(funding['Before interest'], [150] * 3)
    replication = page.locator('[data-editor-output="futures-quote-replication"]').inner_text()
    assert all(value in replication for value in ('149.993313', '150.037434', '150.000000', '9.995991'))
    exercise = page.locator('[data-editor-output="futures-exercise"]').inner_text()
    assert 'Net cash gain before interest: 30.00 GBP' in exercise
    assert 'Net purchase cost before funding: 1050.00 GBP' in exercise
    assert page.locator('[data-editor-output="futures-exercise"] .jupyter-widgets').count() == 0
    print('PASS: daily settlements, margin deposits/return, dated funding, ideal replication, and exercise match worked answers.', flush=True)


def check_controls(page, inspect_axes):
    output = page.locator('[data-editor-output="futures-liquidity-widget"]')
    slider = output.get_by_role('slider')
    slider.wait_for(timeout=30000)
    assert page.get_by_role('slider').count() == 1
    frozen = {editor: payload_for(page, editor) for editor in EDITORS if editor != 'futures-liquidity-widget'}
    for dip, key, expected_deposits in (
        (5, None, [100, 150, 150, 150, 150]),
        (0, 'Home', [100] * 5),
        (1, 'ArrowRight', [100] * 5),
        (15, 'End', [100, 250, 310, 310, 310]),
        (14, 'ArrowLeft', [100, 240, 296, 296, 296]),
        (0, 'Home', [100] * 5),
    ):
        if key:
            slider.press(key)
        page.wait_for_function("""dip => {
            const message = window.chapterMessages.filter(m => m.id === 'futures-liquidity-widget' && m.echart).at(-1);
            return message?.echart.includes(`Day 362 drop: ${dip} GBP/unit`);
        }""", arg=dip, timeout=30000)
        payload = payload_for(page, 'futures-liquidity-widget')
        close(payload['futuresPathExperiment']['series']['Selected path'], [105, 105-dip, 105-1.4*dip, 112, 120])
        close(payload['futuresPathExperiment']['series']['Steady rise'], [105, 110, 115, 118, 120])
        close(payload['futuresDepositExperiment']['series']['Selected path'], expected_deposits)
        close(payload['futuresDepositExperiment']['series']['Steady rise'], [100] * 5)
        output.locator('.text-output').get_by_text(f'Day 362 drop: {dip} GBP/unit', exact=False).wait_for()
        text = output.locator('.text-output').inner_text()
        assert f'Total deposits: {expected_deposits[-1]:.2f} GBP' in text
        assert f'Close-out receipt: {expected_deposits[-1] + 150:.2f} GBP' in text
        assert 'Net cash before interest: 150.00 GBP' in text
        if inspect_axes:
            page.wait_for_function("""expected => {
                const el = document.querySelectorAll('[data-editor-output="futures-liquidity-widget"] .chart')[1];
                const actual = el.__vueParentComponent.exposed.chart.getOption().series[0].data;
                return actual.length === expected.length && actual.every((value, i) => Math.abs(value - expected[i]) < 1e-8);
            }""", arg=expected_deposits)
            check_rendered(page, 'futures-liquidity-widget')
            properties = output.locator('.chart').nth(1).evaluate("""el => {
                const option = el.__vueParentComponent.exposed.chart.getOption();
                return {step:option.series[0].step, tooltip:option.tooltip[0].valueFormatter(option.series[0].data.at(-1))};
            }""")
            assert properties['step'] == 'end'
            assert properties['tooltip'] == str(expected_deposits[-1])
        for editor, original in frozen.items():
            assert payload_for(page, editor) == original, editor
    if inspect_axes:
        for editor in frozen:
            check_rendered(page, editor)
    assert page.locator('.chart-panel').count() == 8
    print('PASS: standalone liquidity widget and repeated zero/intermediate/deep-drop changes preserve final gain and other outputs.', flush=True)
