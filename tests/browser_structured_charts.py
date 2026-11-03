"""Live funded-product budgets, payment regions, cost reconciliation, and controls."""
import math

from browser_robust_charts import payload_for
from browser_ml_charts import check_rendered


EDITORS = ('structured-protected','structured-capped','structured-income','structured-fees',
           'structured-early-sale','structured-issuer','structured-budget-widget','structured-exercise')


def near(a,b):
    assert math.isclose(a,b,abs_tol=1e-7),(a,b)


def call(rate,vol):
    d1 = (math.log1p(rate)+.5*vol**2)/vol
    cdf = lambda z:(1+math.erf(z/math.sqrt(2)))/2
    return 100*cdf(d1)-100/(1+rate)*cdf(d1-vol)


def check_defaults(page,inspect_axes):
    if inspect_axes:
        for editor in EDITORS:
            check_rendered(page,editor)
    protected = payload_for(page,'structured-protected')['structuredProtected']['series']
    for s,payment in protected['Bond plus call']:
        near(payment,100+.45848032140949135*max(s-100,0))
    capped = payload_for(page,'structured-capped')['structuredCapped']['series']
    for s,payment in capped['Capped at share price 120']:
        near(payment,100+.6641880647916795*min(max(s-100,0),20))
    income = payload_for(page,'structured-income')['structuredIncome']['series']
    for s,payment in income['Income construction']:
        near(payment,110.9055934715555-max(100-s,0))
    fees = payload_for(page,'structured-fees')['structuredFees']['series']['Participation']
    for fee,participation in fees:
        near(participation,100*(100-100/1.05-fee)/call(.05,.2))
    assert 'cannot fund' in page.locator('[data-editor-output="structured-fees"]').inner_text()
    early = payload_for(page,'structured-early-sale')['structuredEarlySale']['series']['Six-month model mark']
    near(next(y for x,y in early if x==80),97.19021170122082)
    issuer = payload_for(page,'structured-issuer')['structuredIssuer']['series']
    for promised,recovered in zip(issuer['Issuer performs'],issuer['40% recovery stress']):
        near(recovered[1],.4*promised[1])
    near(issuer['40% recovery stress'][0][1],40)
    exercise = payload_for(page,'structured-exercise')['structuredExercise']['series']
    for s,payment in exercise['Executed design with fee']:
        near(payment,100+.5104685910685981*min(max(s-100,0),20))
    assert '98.897906282' in page.locator('[data-editor-output="structured-exercise"]').inner_text()
    print('PASS: funded floors, participation, caps, downside income, fees, early sale, recovery stress, and executed budget.',flush=True)


def check_controls(page,inspect_axes):
    output = page.locator('[data-editor-output="structured-budget-widget"]')
    sliders = output.get_by_role('slider')
    assert sliders.count()==page.get_by_role('slider').count()==2
    frozen = {name:payload_for(page,name) for name in EDITORS if name!='structured-budget-widget'}
    for rate,vol in ((0.,10.),(8.,40.),(3.5,17.5),(8.,20.),(5.,20.)):
        for index,steps in ((0,round(rate/.5)),(1,round((vol-10)/2.5))):
            sliders.nth(index).press('Home')
            for _ in range(steps):
                sliders.nth(index).press('ArrowRight')
        label = f'Cash rate: {rate:.2f}%; volatility: {vol:.2f}%'
        page.wait_for_function("""label => window.chapterMessages.filter(m=>m.id==='structured-budget-widget' && m.echart)
            .at(-1)?.echart.includes(label)""",arg=label,timeout=60000)
        chart = payload_for(page,'structured-budget-widget')['structuredBudgetExperiment']
        for scenario,participation in chart['series']['New-issue participation']:
            near(100/(1+rate/100)+(participation/100)*call(rate/100,scenario/100),100)
        selected = chart['series']['Selected terms'][0]
        near(selected[0],vol)
        near(selected[1],100*(100-100/(1+rate/100))/call(rate/100,vol/100))
        output.locator('.text-output').get_by_text(label,exact=False).wait_for()
        if inspect_axes:
            page.wait_for_function("""label => {
                const message=window.chapterMessages.filter(m=>m.id==='structured-budget-widget' && m.echart).at(-1);
                if (!message?.echart.includes(label)) return false;
                const expected=JSON.parse(message.echart.split('<ECHARTS_DATA>')[1]).structuredBudgetExperiment.series;
                const rendered=document.querySelector('[data-editor-output="structured-budget-widget"] .chart')
                    .__vueParentComponent.exposed.chart.getOption().series;
                return rendered.every(s=>JSON.stringify(s.data)===JSON.stringify(expected[s.name]));
            }""",arg=label,timeout=60000)
            check_rendered(page,'structured-budget-widget')
            marker = output.locator('.chart').evaluate("""el => {
                const s=el.__vueParentComponent.exposed.chart.getOption().series.find(s=>s.name==='Selected terms');
                return [s.type,s.symbol,s.symbolSize,s.itemStyle.borderWidth];
            }""")
            assert marker==['scatter','diamond',18,2]
        for name,original in frozen.items():
            assert payload_for(page,name)==original,name
    assert page.locator('.chart-panel').count()==8
    print('PASS: independent rate/volatility controls, zero-budget limit, repriced participation, marker, and isolation.',flush=True)


def check_navigation(page):
    page.evaluate('window.structuredNavigationSentinel=true')
    page.locator('.vp-doc').get_by_role('link',name='Design, Price, and Explain a Product',exact=True).click()
    page.wait_for_function("document.querySelector('.vp-doc h1')?.textContent.includes('Design, Price, and Explain a Product')")
    assert page.get_by_role('slider').count()==0
    page.locator('.vp-doc').get_by_role('link',name='Building Structured Products',exact=True).first.click()
    page.wait_for_function("document.querySelector('.vp-doc h1')?.textContent.includes('Building Structured Products')")
    assert page.evaluate('window.structuredNavigationSentinel===true')
    assert page.locator('.chart-panel').count()==0
    page.evaluate('window.chapterMessages=[]')
    page.locator('[data-editor-id="structured-budget-widget"] button.run').click()
    sliders = page.locator('[data-editor-output="structured-budget-widget"]').get_by_role('slider')
    sliders.nth(0).wait_for(timeout=30000)
    sliders.nth(0).press('Home')
    page.wait_for_function("""() => window.chapterMessages.filter(m=>m.id==='structured-budget-widget' && m.echart)
        .at(-1)?.echart.includes('Cash rate: 0.00%')""",timeout=60000)
    assert page.locator('.chart-panel').count()==1
    assert not page.evaluate('window.chapterMessages.some(m=>m.error)')
    print('PASS: named capstone route and remounted budget widget.',flush=True)
