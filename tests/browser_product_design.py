"""Capstone values, editable experiment, isolated output, and closing navigation."""
import math

from browser_robust_charts import payload_for
from browser_ml_charts import check_rendered


EDITORS = ('product-design-payments','product-design-stress','product-design-hedge','product-design-experiment')


def check_defaults(page,inspect_axes):
    if inspect_axes:
        for editor in EDITORS:
            check_rendered(page,editor)
    series = payload_for(page,'product-design-payments')['designPayments']['series']
    for label,units,cap in (('A: cap 110',.8190218925553494,110),('B: cap 130',.41962334086424885,130)):
        for spot,paid in series[label]:
            assert math.isclose(paid,100+units*min(max(spot-100,0),cap-100),abs_tol=1e-8)
    risks = page.locator('[data-editor-output="product-design-risks"]').inner_text()
    assert '-0.015906734' in risks and '0.052992707' in risks
    assert '97.559625' in page.locator('[data-editor-output="product-design-stress"]').inner_text()
    assert '1.087370739' in page.locator('[data-editor-output="product-design-experiment"]').inner_text()
    assert 'meets target: True' in page.locator('[data-editor-output="product-design-experiment"]').inner_text()
    print('PASS: capstone budget, target payments, signed risks, six-month stress, and fee boundary.',flush=True)


def check_experiment_navigation(page,inspect_axes):
    frozen = {name:payload_for(page,name) for name in EDITORS[:-1]}
    content = page.locator('[data-editor-id="product-design-experiment"] .cm-content')
    content.click()
    content.press('Control+Home')
    content.press('Shift+End')
    page.keyboard.insert_text('candidate_cap = 130.')
    done_before = page.evaluate("window.chapterMessages.filter(m=>m.id==='product-design-experiment' && m.done).length")
    page.locator('[data-editor-id="product-design-experiment"] button.run').click()
    page.wait_for_function("count=>window.chapterMessages.filter(m=>m.id==='product-design-experiment' && m.done).length>count",arg=done_before,timeout=60000)
    text = page.locator('[data-editor-output="product-design-experiment"]').inner_text()
    assert '104.196233409' in text and 'meets target: False' in text,text
    if inspect_axes:
        check_rendered(page,'product-design-experiment')
    # Previous payloads remain in the DOM; rerunning one cell must not clear other charts.
    for name in frozen:
        assert payload_for(page,name)==frozen[name]
        assert page.locator(f'[data-editor-output="{name}"] .chart-panel').count()==1
    assert page.locator('.chart-panel').count()==4
    assert not page.evaluate('window.chapterMessages.some(m=>m.error)')
    page.locator('.vp-doc').get_by_role('link',name='Robust Estimation of Factor Models',exact=True).click()
    page.wait_for_function("!!document.getElementById(decodeURIComponent(location.hash.slice(1))) && location.pathname.includes('3.0-overview')")
    page.go_back()
    page.locator('[data-editor-id="product-design-setup"]').wait_for()
    assert page.locator('[data-editor-id]').count()==6
    print('PASS: editable cap changes target outcome, isolated chart outputs, and next-topic navigation.',flush=True)
