"""Browser reconciliation for signed option baskets, funding, and strike controls."""
import math

from browser_robust_charts import payload_for
from browser_ml_charts import check_rendered


EDITORS = ('combinations-bull-call','combinations-bull-put','combinations-bear','combinations-covered',
           'combinations-protective','combinations-collar','combinations-zero-collar','combinations-parity',
           'combinations-greeks','combinations-exit','combinations-execution','combinations-strike-widget',
           'combinations-exercise')


def near(actual, expected, tol=1e-7):
    assert math.isclose(actual,expected,abs_tol=tol), (actual,expected)


def call(strike):
    d1 = (math.log(100/strike)+math.log1p(.05)+.2**2/2)/.2
    cdf = lambda x:(1+math.erf(x/math.sqrt(2)))/2
    return 100*cdf(d1)-strike/1.05*cdf(d1-.2)


def check_defaults(page, inspect_axes):
    if inspect_axes:
        for editor in EDITORS:
            check_rendered(page,editor)
    debit = call(100)-call(110)
    bull = payload_for(page,'combinations-bull-call')
    legs = bull['spreadLegs']['series']
    for long,short,total in zip(legs['Long 100 call'],legs['Short 110 call'],legs['Combined']):
        near(long[1]+short[1],total[1])
        near(total[1],max(0,min(total[0]-100,10)))
    for x,y in bull['spreadProfit']['series']['Financed profit']:
        near(y,max(0,min(x-100,10))-debit*1.05)
    put = payload_for(page,'combinations-bull-put')['bullPut']['series']
    bear = payload_for(page,'combinations-bear')['bearSpread']['series']
    for a,b,c in zip(bull['spreadProfit']['series']['Financed profit'],put['Financed profit'],bear['Financed profit']):
        near(a[1],b[1]); near(a[1],-c[1])
    for editor,key,label,cost,payoff in (
        ('combinations-covered','coveredCall','Covered call',94.0068880316,lambda x:min(x,110)),
        ('combinations-protective','protectivePut','Protective put',102.3360294912,lambda x:max(x,90)),
        ('combinations-collar','collar','Collar',96.3429175228,lambda x:min(max(x,90),110))):
        for x,y in payload_for(page,editor)[key]['series'][label]:
            near(y,payoff(x)-cost*1.05)
    box = payload_for(page,'combinations-parity')['boxPayments']['series']
    for (_,payment),(_,profit) in zip(box['Terminal payment'],box['Financed profit']):
        near(payment,10); near(profit,0)
    risks = payload_for(page,'combinations-greeks')
    near(risks['combinationDelta']['series']['Bull call'][60][1],.1873035290377821)
    assert risks['combinationGamma']['series']['Bull call'][60][1]<0
    execution = payload_for(page,'combinations-execution')['executionCost']['series']
    for mid,fill in zip(execution['Mid-price profit'],execution['Filled-entry profit']):
        near(mid[1]-fill[1],.21)
    exercise = page.locator('[data-editor-output="combinations-exercise"]').inner_text()
    for number in ('9954.271157144','10451.984715001','104.519847150','36.453826358'):
        assert number in exercise,number
    assert page.locator('[data-editor-output="combinations-exercise"] .jupyter-widgets').count()==0
    print('PASS: signed legs, profit parity, floors/caps, box payment, Greek signs, execution costs, and worked collar.',flush=True)


def check_controls(page, inspect_axes):
    output = page.locator('[data-editor-output="combinations-strike-widget"]')
    sliders = output.get_by_role('slider')
    assert sliders.count()==page.get_by_role('slider').count()==2
    frozen = {name:payload_for(page,name) for name in EDITORS if name!='combinations-strike-widget'}
    for strike,final in ((110,120),(105,0),(130,160),(110,110),(110,100),(120,120)):
        for index,steps in ((0,int((strike-105)/5)),(1,int(final/5))):
            sliders.nth(index).press('Home')
            for _ in range(steps):
                sliders.nth(index).press('ArrowRight')
        label = f'Sold strike: {strike:.2f} GBP; final share: {final:.2f} GBP'
        page.wait_for_function("""label => window.chapterMessages.filter(m=>m.id==='combinations-strike-widget' && m.echart)
            .at(-1)?.echart.includes(label)""",arg=label,timeout=30000)
        data = payload_for(page,'combinations-strike-widget')['optionSpread']
        selected = max(0,min(final-100,strike-100))
        expected = selected-(call(100)-call(strike))*1.05
        near(data['series']['Selected payoff'][0][1],selected)
        near(data['series']['Selected profit'][0][1],expected)
        output.locator('.text-output').get_by_text(label,exact=False).wait_for()
        if inspect_axes:
            page.wait_for_function("""value => {
                const chart=document.querySelector('[data-editor-output="combinations-strike-widget"] .chart')
                    .__vueParentComponent.exposed.chart;
                return Math.abs(chart.getOption().series.find(s=>s.name==='Selected profit').data[0][1]-value)<1e-8;
            }""",arg=expected)
            check_rendered(page,'combinations-strike-widget')
            markers = output.locator('.chart').evaluate("""el => el.__vueParentComponent.exposed.chart.getOption().series
                .filter(s=>s.name.startsWith('Selected')).map(s=>[s.type,s.symbol,s.symbolSize,s.itemStyle.borderWidth])""")
            assert markers==[['scatter','circle',24,3],['scatter','diamond',16,2]]
        for name,original in frozen.items():
            assert payload_for(page,name)==original,name
    assert page.locator('.chart-panel').count()==15
    print('PASS: independent strike/outcome controls, boundaries, strike crossings, markers, and output isolation.',flush=True)


def check_navigation(page):
    page.evaluate('window.combinationsNavigationSentinel = true')
    page.locator('.vp-doc').get_by_role('link',name='Reading the Options Market: Implied Volatility and Surfaces',exact=True).click()
    page.wait_for_function("location.hash==='#volatility-surfaces' && !!document.getElementById('volatility-surfaces')")
    assert page.get_by_role('slider').count()==0
    page.locator('.vp-doc').get_by_role('link',name='Spreads and Basic Option Combinations',exact=True).first.click()
    page.wait_for_function("document.querySelector('.vp-doc h1')?.textContent.includes('Spreads and Basic Option Combinations')")
    assert page.evaluate('window.combinationsNavigationSentinel===true')
    assert page.locator('.chart-panel').count()==0
    page.evaluate('window.chapterMessages=[]')
    page.locator('[data-editor-id="combinations-strike-widget"] button.run').click()
    sliders = page.locator('[data-editor-output="combinations-strike-widget"]').get_by_role('slider')
    sliders.nth(0).wait_for(timeout=30000)
    sliders.nth(0).press('End')
    page.wait_for_function("""() => window.chapterMessages.filter(m=>m.id==='combinations-strike-widget' && m.echart)
        .at(-1)?.echart.includes('Sold strike: 130.00 GBP')""",timeout=30000)
    assert page.locator('.chart-panel').count()==1
    assert not page.evaluate('window.chapterMessages.some(m=>m.error)')
    print('PASS: named volatility-surface transition and remounted combination widget.',flush=True)
