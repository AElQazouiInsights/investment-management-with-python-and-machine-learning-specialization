"""Live quote inversion, price-space fitting, and independent IV input controls."""
import math

from browser_robust_charts import payload_for
from browser_ml_charts import check_rendered


EDITORS = ('iv-inversion','iv-conditioning','iv-forward','iv-snapshot','iv-variance','iv-least-squares',
           'iv-fit','iv-joint','iv-held-out','iv-strike-checks','iv-calendar','iv-input-widget','iv-later-snapshot','iv-exercise')


def near(actual,expected,tolerance=2e-7):
    assert math.isclose(actual,expected,abs_tol=tolerance), (actual,expected)


def price(forward,strike,vol):
    d1 = math.log(forward/strike)/vol+vol/2
    cdf = lambda x:(1+math.erf(x/math.sqrt(2)))/2
    return (forward*cdf(d1)-strike*cdf(d1-vol))/1.05


def check_defaults(page,inspect_axes):
    if inspect_axes:
        for editor in EDITORS:
            check_rendered(page,editor)
    inversion = payload_for(page,'iv-inversion')['ivInversion']['series']
    for vol,premium in inversion['Bid, mid, ask']:
        near(price(105,100,vol/100),premium)
    text = page.locator('[data-editor-output="iv-inversion"]').inner_text()
    for label in ('Below intrinsic','At upper bound','Expired'):
        assert label in text,label
    conditioning = payload_for(page,'iv-conditioning')['ivConditioning']['series']
    assert conditioning['After adding GBP 0.01'][-1][1]>37
    forwards = payload_for(page,'iv-forward')['ivForwardError']['series']
    for x,y in forwards['Assumed forward 105']:
        near(y,20)
    assert all(p[1]>20 for p in forwards['Assumed forward 103'])
    assert all(p[1]<20 for p in forwards['Assumed forward 107'])
    snapshot = payload_for(page,'iv-snapshot')['ivSmile']['series']
    for bid,mid,ask in zip(snapshot['Bid IV'],snapshot['Mid IV'],snapshot['Ask IV']):
        assert bid[1]<mid[1]<ask[1]
    variance = payload_for(page,'iv-variance')['ivTotalVariance']['series']['ATM total variance']
    near(variance[0][1],.008875); near(variance[-1][1],.04)
    fit = payload_for(page,'iv-fit')['ivPriceResiduals']['series']
    assert max(abs(p[1]) for p in fit['Weighted mid'])<.31
    assert max(abs(p[1]) for p in fit['Interval'])<=1.00001
    assert 'False' not in page.locator('[data-editor-output="iv-fit"]').inner_text()
    assert 'Joint convergence: True' in page.locator('[data-editor-output="iv-joint"]').inner_text()
    hold = payload_for(page,'iv-held-out')['ivHeldOut']['series']['Held-out errors']
    assert len(hold)==4 and max(abs(p[1]) for p in hold)<1
    butterfly = page.locator('[data-editor-output="iv-strike-checks"]').inner_text()
    for number in ('-0.04','0.16','-0.40'):
        assert number in butterfly,number
    calendar = payload_for(page,'iv-calendar')['ivCalendar']['series']
    assert calendar['Fitted ATM slice'][1][1]>calendar['Fitted ATM slice'][0][1]
    assert calendar['Inconsistent pair'][1][1]<calendar['Inconsistent pair'][0][1]
    later = payload_for(page,'iv-later-snapshot')['ivLaterSnapshot']['series']['Rolled old-fit errors']
    assert min(p[1] for p in later)<-1
    exercise = payload_for(page,'iv-exercise')['ivExercise']['series']['Observed premium']
    for vol,premium in exercise:
        near(price(105,110,vol/100),premium)
    near(exercise[0][0],19.747052075)
    near(exercise[-1][0],20.252806884)
    assert page.locator('[data-editor-output="iv-exercise"] .jupyter-widgets').count()==0
    print('PASS: bid/mid/ask repricing, input conditioning, quote-aware fits, held-out errors, price constraints, and worked IV.',flush=True)


def check_controls(page,inspect_axes):
    output = page.locator('[data-editor-output="iv-input-widget"]')
    sliders = output.get_by_role('slider')
    assert sliders.count()==page.get_by_role('slider').count()==2
    frozen = {name:payload_for(page,name) for name in EDITORS if name!='iv-input-widget'}
    for forward,change in ((105.,0.),(103.,-.5),(107.,.5),(104.5,.2),(105.,0.)):
        for index,steps in ((0,round((forward-103)/.25)),(1,round((change+.5)/.1))):
            sliders.nth(index).press('Home')
            for _ in range(steps):
                sliders.nth(index).press('ArrowRight')
        label = f'Forward assumption: {forward:.2f} GBP; premium change: {change:.2f} GBP'
        page.wait_for_function("""label => window.chapterMessages.filter(m=>m.id==='iv-input-widget' && m.echart)
            .at(-1)?.echart.includes(label)""",arg=label,timeout=60000)
        chart = payload_for(page,'iv-input-widget')['ivInputExperiment']
        selected = chart['series']['Selected assumption'][0]
        near(selected[0],forward)
        premium = price(105,105,.2)+change
        near(price(forward,105,selected[1]/100),premium)
        for f,vol in chart['series']['Quote-consistent pairs']:
            near(price(f,105,vol/100),premium)
        output.locator('.text-output').get_by_text(label,exact=False).wait_for()
        if inspect_axes:
            page.wait_for_function("""label => {
                const message = window.chapterMessages.filter(m=>m.id==='iv-input-widget' && m.echart).at(-1);
                if (!message?.echart.includes(label)) return false;
                const expected = JSON.parse(message.echart.split('<ECHARTS_DATA>')[1]).ivInputExperiment.series;
                const rendered = document.querySelector('[data-editor-output="iv-input-widget"] .chart')
                    .__vueParentComponent.exposed.chart.getOption().series;
                return rendered.every(s=>JSON.stringify(s.data)===JSON.stringify(expected[s.name]));
            }""",arg=label,timeout=60000)
            check_rendered(page,'iv-input-widget')
            marker = output.locator('.chart').evaluate("""el => {
                const s=el.__vueParentComponent.exposed.chart.getOption().series.find(s=>s.name==='Selected assumption');
                return [s.type,s.symbol,s.symbolSize,s.itemStyle.borderWidth];
            }""")
            assert marker==['scatter','diamond',18,2]
        for name,original in frozen.items():
            assert payload_for(page,name)==original,name
    assert page.locator('.chart-panel').count()==16
    print('PASS: standalone forward/quote controls, boundaries, repricing, marker styling, and output isolation.',flush=True)


def check_navigation(page):
    page.evaluate('window.ivNavigationSentinel=true')
    page.locator('.vp-doc').get_by_role('link',name='Straddles, Strangles, Butterflies, and Condors',exact=True).click()
    page.wait_for_function("document.querySelector('.vp-doc h1')?.textContent.includes('Straddles, Strangles, Butterflies, and Condors')")
    assert page.get_by_role('slider').count()==0
    page.locator('.vp-doc').get_by_role('link',name='Reading the Options Market: Implied Volatility and Surfaces',exact=True).first.click()
    page.wait_for_function("document.querySelector('.vp-doc h1')?.textContent.includes('Reading the Options Market: Implied Volatility and Surfaces')")
    assert page.evaluate('window.ivNavigationSentinel===true')
    assert page.locator('.chart-panel').count()==0
    page.evaluate('window.chapterMessages=[]')
    page.locator('[data-editor-id="iv-input-widget"] button.run').click()
    sliders = page.locator('[data-editor-output="iv-input-widget"]').get_by_role('slider')
    sliders.nth(0).wait_for(timeout=30000)
    sliders.nth(0).press('End')
    page.wait_for_function("""() => window.chapterMessages.filter(m=>m.id==='iv-input-widget' && m.echart)
        .at(-1)?.echart.includes('Forward assumption: 107.00 GBP')""",timeout=60000)
    assert page.locator('.chart-panel').count()==1
    assert not page.evaluate('window.chapterMessages.some(m=>m.error)')
    print('PASS: named next-strategy route and remounted IV widget.',flush=True)
