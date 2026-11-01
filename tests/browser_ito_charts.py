"""Check rendered stochastic identities, nested widget grids, and name-only navigation."""
import math
import re

from browser_robust_charts import payload_for
from browser_ml_charts import check_rendered


EDITORS = ('ito-curvature', 'ito-brownian', 'ito-quadratic-variation', 'ito-square-identity',
           'ito-general-formula', 'ito-refinement-widget', 'ito-log-returns', 'ito-log-price')


def close(actual, expected, tolerance=1e-9):
    assert len(actual) == len(expected)
    assert all(math.isclose(a, b, abs_tol=tolerance) for a, b in zip(actual, expected)), (actual[:5], expected[:5])


def check_defaults(page, inspect_axes):
    if inspect_axes:
        for editor in EDITORS:
            check_rendered(page, editor)
    curvature = payload_for(page, 'ito-curvature')['itoCurvature']['series']
    close(curvature['Two outcomes'][0], [1.9, 3.61])
    close(curvature['Two outcomes'][1], [2.1, 4.41])
    for x, y in curvature['Square']:
        assert math.isclose(y, x*x, abs_tol=1e-12)
    paths = payload_for(page, 'ito-brownian')['itoBrownianPaths']['series']
    assert len(paths) == 4
    assert all(len(path) == 257 and path[0] == [0, 0] and path[-1][0] == 1 for path in paths.values())
    qv = payload_for(page, 'ito-quadratic-variation')['itoQuadraticVariation']['series']
    close(qv['Brownian squared sum'], [1.1538804049625153, .8647254053353399, 1.125232068230941,
                                      .9960011734532783, .9825098621243328])
    close(qv['Smooth path t'], [1/16, 1/64, 1/256, 1/1024, 1/4096])
    square = payload_for(page, 'ito-square-identity')['itoSquareIdentity']['series']
    for exact, first, corrected in zip(square['Exact square'], square['First order only'], square['First order + time']):
        assert exact[1] >= 0
        assert math.isclose(corrected[1] - first[1], exact[0], abs_tol=1e-12)
    assert math.isclose(square['Exact square'][-1][1] - square['First order only'][-1][1], qv['Brownian squared sum'][2], abs_tol=1e-10)
    local = payload_for(page, 'ito-general-formula')['itoLocalTransformation']['series']
    close(local['Direct substitution'], [-.114959, .125161])
    close(local['Itô approximation'], [-.1149, .1251])
    returns = payload_for(page, 'ito-log-returns')['itoLogReturns']['series']
    for simple, log in zip(returns['Simple return'], returns['Log return']):
        assert math.isclose(simple[1]/100, math.expm1(log[1]/100), abs_tol=1e-12)
    prices = payload_for(page, 'ito-log-price')['itoLogPrice']['series']
    for exact, wrong, mean, median in zip(prices['Exact GBM path'], prices['Correction omitted'], prices['Model mean'], prices['Model median']):
        assert exact[1] > 0
        assert math.isclose(wrong[1]/exact[1], math.exp(.02*exact[0]), abs_tol=1e-12)
        assert math.isclose(mean[1], 100*math.exp(.08*exact[0]), abs_tol=1e-9)
        assert math.isclose(median[1], 100*math.exp(.06*exact[0]), abs_tol=1e-9)
    exercise = page.locator('[data-editor-output="ito-exercise"]').inner_text()
    assert all(value in exercise for value in ('85.586421 GBP', '82.436363 GBP', '80.602256 GBP', '0.088388 years', '-0.040000 years'))
    assert page.locator('[data-editor-output="ito-exercise"] .jupyter-widgets').count() == 0
    assert not re.search(r'\bD\.\d|\bChapter \d', page.locator('.vp-doc').inner_text())
    print('PASS: curvature, Brownian scaling, quadratic variation, Itô terms, log-price corrections, and exercise answers.', flush=True)


def check_controls(page, inspect_axes):
    output = page.locator('[data-editor-output="ito-refinement-widget"]')
    slider = output.get_by_role('slider')
    slider.wait_for(timeout=30000)
    assert page.get_by_role('slider').count() == 1
    frozen = {editor: payload_for(page, editor) for editor in EDITORS if editor != 'ito-refinement-widget'}
    original_square = None
    previous = None
    for power, keys in [(8, []), (4, ['Home']), (5, ['ArrowRight']), (12, ['End']),
                        (11, ['ArrowLeft']), (8, ['Home'] + ['ArrowRight'] * 4)]:
        for key in keys:
            slider.press(key)
        page.wait_for_function("""power => window.chapterMessages.filter(m => m.id === 'ito-refinement-widget' && m.echart)
            .at(-1)?.echart.includes(`Grid power: ${power};`)""", arg=power, timeout=30000)
        payload = payload_for(page, 'ito-refinement-widget')
        series = payload['itoRefinementSquare']['series']
        exact, first, corrected = (series[k] for k in ('Exact square', 'First order only', 'First order + time'))
        variation = payload['itoRefinementVariation']['series']['Squared increments']
        assert len(exact) == len(variation) == 2**power + 1
        if original_square is None:
            original_square = exact[-1][1]
        assert math.isclose(exact[-1][1], original_square, abs_tol=1e-12)
        for (t, value), (_, linear), (_, approx), (_, qv) in zip(exact, first, corrected, variation):
            assert math.isclose(value, linear + qv, abs_tol=1e-10)
            assert math.isclose(approx - value, t - qv, abs_tol=1e-10)
        assert all(a[1] <= b[1] for a, b in zip(variation, variation[1:]))
        if previous:
            previous_power, previous_exact = previous
            coarse, fine = (previous_exact, exact) if previous_power < power else (exact, previous_exact)
            stride = 2**abs(power-previous_power)
            close([p[1] for p in coarse], [p[1] for p in fine[::stride]])
        previous = (power, exact)
        output.locator('.text-output').get_by_text(f'Grid power: {power}; intervals: {2**power}', exact=False).wait_for()
        if inspect_axes:
            page.wait_for_function("""count => document.querySelector('[data-editor-output="ito-refinement-widget"] .chart')
                .__vueParentComponent.exposed.chart.getOption().series[0].data.length === count + 1""", arg=2**power)
            check_rendered(page, 'ito-refinement-widget')
        for editor, original in frozen.items():
            assert payload_for(page, editor) == original, editor
    assert page.locator('.chart-panel').count() == 9
    print('PASS: standalone refinement widget, nested coarse/fine grids, fixed endpoint, error identities, and output isolation.', flush=True)


def check_navigation(page):
    page.evaluate('window.itoNavigationSentinel = true')
    page.locator('.vp-doc').get_by_role('link', name='Deriving and Using Black–Scholes', exact=True).last.click()
    page.wait_for_function("document.querySelector('.vp-doc h1')?.textContent.includes('Deriving and Using Black')")
    assert page.get_by_role('slider').count() == 0
    assert not re.search(r'\bD\.\d', page.locator('.vp-doc').inner_text())
    page.locator('.vp-doc').get_by_role('link', name="Random Motion and Itô's Lemma", exact=True).first.click()
    page.wait_for_function("document.querySelector('.vp-doc h1')?.textContent.includes('Random Motion')")
    assert page.evaluate('window.itoNavigationSentinel === true')
    assert page.locator('.chart-panel').count() == 0
    page.evaluate('window.chapterMessages = []')
    page.locator('[data-editor-id="ito-refinement-widget"] button.run').click()
    output = page.locator('[data-editor-output="ito-refinement-widget"]')
    output.get_by_role('slider').wait_for(timeout=30000)
    output.get_by_role('slider').press('Home')
    page.wait_for_function("""() => window.chapterMessages.filter(m => m.id === 'ito-refinement-widget' && m.echart)
        .at(-1)?.echart.includes('Grid power: 4;')""")
    assert page.locator('.chart-panel').count() == 2
    assert not page.evaluate('window.chapterMessages.some(m => m.error)')
    print('PASS: name-only chapter links and mounted-widget navigation preserve a working shared runtime.', flush=True)
