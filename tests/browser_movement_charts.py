"""Browser checks for movement/range strategies and the independently repriced widget."""
import math

from browser_robust_charts import payload_for
from browser_ml_charts import check_rendered


EDITORS = ('movement-straddle','movement-strangle','movement-butterfly','movement-condor',
           'movement-risk','movement-range-widget','movement-exercise')


def near(a,b):
    assert math.isclose(a,b,abs_tol=1e-7), (a,b)


def call(strike):
    d1 = (math.log(100/strike)+math.log1p(.05)+.02)/.2
    cdf = lambda x:(1+math.erf(x/math.sqrt(2)))/2
    return 100*cdf(d1)-strike/1.05*cdf(d1-.2)


def check_defaults(page,inspect_axes):
    if inspect_axes:
        for editor in EDITORS:
            check_rendered(page,editor)
    for editor,key,cost,shape in (
        ('movement-straddle','movementStraddle',16.010654231534275,lambda s:abs(s-100)),
        ('movement-butterfly','movementButterfly',1.842296751834006,lambda s:max(10-abs(s-100),0))):
        series = payload_for(page,editor)[key]['series']
        for x,y in series['Expiry payoff']:
            near(y,shape(x))
        for x,y in series['Financed profit']:
            near(y,shape(x)-cost*1.05)
    series = payload_for(page,'movement-strangle')['movementStrangle']['series']
    for x,y in series['Strangle profit']:
        near(y,max(abs(x-100)-10,0)-8.329141459558773*1.05)
    series = payload_for(page,'movement-condor')['movementCondor']['series']
    for x,y in series['Condor profit']:
        near(y,max(10-max(abs(x-100)-5,0),0)-3.575825604321615*1.05)
    risk_text = page.locator('[data-editor-output="movement-risk"]').inner_text()
    assert '-3.723531' in risk_text and '0.269117' in risk_text
    risk = payload_for(page,'movement-risk')['movementVega']['series']
    for data in risk.values():
        near(next(y for x,y in data if abs(x-20)<1e-8),0)
    assert risk['Straddle'][-1][1]>0 and risk['Butterfly'][-1][1]<0
    exercise = payload_for(page,'movement-exercise')['movementExercise']['series']
    for name in ('Butterfly','Condor'):
        for model,executed in zip(exercise[name+' model'],exercise[name+' executed']):
            near(model[1]-executed[1],.21)
    text = page.locator('[data-editor-output="movement-exercise"]').inner_text()
    assert '-14.441159' in text and '303.538312' in text
    print('PASS: strategy regions, financed profits, local-risk units, early exit, and executed comparison.',flush=True)


def check_controls(page,inspect_axes):
    output = page.locator('[data-editor-output="movement-range-widget"]')
    sliders = output.get_by_role('slider')
    assert sliders.count()==page.get_by_role('slider').count()==2
    frozen = {name:payload_for(page,name) for name in EDITORS if name!='movement-range-widget'}
    for half,final in ((0,100),(10,60),(10,140),(3,95),(5,100)):
        for index,steps in ((0,half),(1,(final-60)//5)):
            sliders.nth(index).press('Home')
            for _ in range(steps):
                sliders.nth(index).press('ArrowRight')
        label = f'Half-plateau: {half:.2f} GBP; final share: {final:.2f} GBP'
        page.wait_for_function("""label => window.chapterMessages.filter(m=>m.id==='movement-range-widget' && m.echart)
            .at(-1)?.echart.includes(label)""",arg=label,timeout=60000)
        chart = payload_for(page,'movement-range-widget')['optionRangeExperiment']
        debit = call(90-half)-call(100-half)-call(100+half)+call(110+half)
        for x,y in chart['series']['Expiry payoff']:
            near(y,max(10-max(abs(x-100)-half,0),0))
        near(chart['series']['Selected profit'][0][0],final)
        near(chart['series']['Selected profit'][0][1],max(10-max(abs(final-100)-half,0),0)-debit*1.05)
        output.locator('.text-output').get_by_text(label,exact=False).wait_for()
        if inspect_axes:
            page.wait_for_function("""label => {
                const message=window.chapterMessages.filter(m=>m.id==='movement-range-widget' && m.echart).at(-1);
                if (!message?.echart.includes(label)) return false;
                const expected=JSON.parse(message.echart.split('<ECHARTS_DATA>')[1]).optionRangeExperiment.series;
                const rendered=document.querySelector('[data-editor-output="movement-range-widget"] .chart')
                    .__vueParentComponent.exposed.chart.getOption().series;
                return rendered.every(s=>JSON.stringify(s.data)===JSON.stringify(expected[s.name]));
            }""",arg=label,timeout=60000)
            check_rendered(page,'movement-range-widget')
            marker = output.locator('.chart').evaluate("""el => {
                const s=el.__vueParentComponent.exposed.chart.getOption().series.find(s=>s.name==='Selected profit');
                return [s.type,s.symbol,s.symbolSize,s.itemStyle.borderWidth];
            }""")
            assert marker==['scatter','diamond',18,2]
        for name,original in frozen.items():
            assert payload_for(page,name)==original,name
    assert page.locator('.chart-panel').count()==7
    print('PASS: independent range/outcome controls, butterfly limit, quote repricing, marker, and output isolation.',flush=True)


def check_navigation(page):
    page.evaluate('window.movementNavigationSentinel=true')
    page.locator('.vp-doc').get_by_role('link',name='Butterflies, Implied Distributions, and Tail Pricing',exact=True).click()
    page.wait_for_function("document.querySelector('.vp-doc h1')?.textContent.includes('Butterflies, Implied Distributions, and Tail Pricing')")
    assert page.get_by_role('slider').count()==0
    page.locator('.vp-doc').get_by_role('link',name='Straddles, Strangles, Butterflies, and Condors',exact=True).first.click()
    page.wait_for_function("document.querySelector('.vp-doc h1')?.textContent.includes('Straddles, Strangles, Butterflies, and Condors')")
    assert page.evaluate('window.movementNavigationSentinel===true')
    assert page.locator('.chart-panel').count()==0
    page.evaluate('window.chapterMessages=[]')
    page.locator('[data-editor-id="movement-range-widget"] button.run').click()
    sliders = page.locator('[data-editor-output="movement-range-widget"]').get_by_role('slider')
    sliders.nth(0).wait_for(timeout=30000)
    sliders.nth(0).press('Home')
    page.wait_for_function("""() => window.chapterMessages.filter(m=>m.id==='movement-range-widget' && m.echart)
        .at(-1)?.echart.includes('Half-plateau: 0.00 GBP')""",timeout=60000)
    assert page.locator('.chart-panel').count()==1
    assert not page.evaluate('window.chapterMessages.some(m=>m.error)')
    print('PASS: named distribution route and remounted range widget.',flush=True)
