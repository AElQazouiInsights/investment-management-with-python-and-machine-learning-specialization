"""Live recovery, quote-noise controls, tail ambiguity, and navigation checks."""
import math

from browser_robust_charts import payload_for
from browser_ml_charts import check_rendered


EDITORS = ('distribution-setup','distribution-digital','distribution-recovery','distribution-density',
           'distribution-noise','distribution-resolution-widget','distribution-tails','distribution-exercise')


def near(a,b):
    assert math.isclose(a,b,abs_tol=1e-7),(a,b)


def call(k):
    d1 = math.log(105/k)/.2+.1
    cdf = lambda z:(1+math.erf(z/math.sqrt(2)))/2
    return (105*cdf(d1)-k*cdf(d1-.2))/1.05


def check_defaults(page,inspect_axes):
    if inspect_axes:
        for editor in EDITORS:
            check_rendered(page,editor)
    calls = payload_for(page,'distribution-setup')['distributionCalls']['series']['Synthetic calls']
    near(next(y for x,y in calls if x==105),8)
    digital = payload_for(page,'distribution-digital')['distributionDigital']['series']
    for x,y in digital['110/120 ramp']:
        near(y,min(max((x-110)/10,0),1))
    for x,y in digital['Strictly above 115']:
        near(y,float(x>115))
    masses = payload_for(page,'distribution-recovery')['distributionMass']['series']['Recovered mass (%)']
    for (_,p),expected in zip(masses,[2,8,20,40,20,8,2]):
        near(p,expected)
    near(sum(p for _,p in masses),100)
    near(sum(x*p/100 for x,p in masses),105)
    density = payload_for(page,'distribution-density')['distributionDensity']['series']
    for x,y in density['Exact lognormal']:
        z=(math.log(x/105)+.02)/.2
        near(y,math.exp(-z*z/2)/math.sqrt(2*math.pi)/(x*.2))
    noise = payload_for(page,'distribution-noise')['distributionNoise']['series']
    assert min(y for _,y in noise['One bumped mid'])<0
    near(sum(y for _,y in noise['One bumped mid']),sum(y for _,y in noise['Clean readings']))
    tails = payload_for(page,'distribution-tails')['distributionTails']['series']
    near(tails['Original tail'][0][1],tails['Alternative tail'][0][1])
    assert next(y for x,y in tails['Alternative tail'] if x==150)>next(y for x,y in tails['Original tail'] if x==150)
    exercise = payload_for(page,'distribution-exercise')['distributionExercise']['series']
    near(sum(y for _,y in exercise['Retained mass (%)']),80)
    assert '4.761904762' in page.locator('[data-editor-output="distribution-exercise"]').inner_text()
    assert '30.831736' in page.locator('[data-editor-output="distribution-moments"]').inner_text()
    print('PASS: discounted digital, recovered mass/mean, smooth density, noise, distinct tails, truncation, and moments.',flush=True)


def check_controls(page,inspect_axes):
    output = page.locator('[data-editor-output="distribution-resolution-widget"]')
    sliders = output.get_by_role('slider')
    assert sliders.count()==page.get_by_role('slider').count()==2
    frozen = {name:payload_for(page,name) for name in EDITORS if name!='distribution-resolution-widget'}
    for gap,bump in ((1,.05),(10,-.05),(4,0.),(1,.03),(5,.03)):
        for index,steps in ((0,gap-1),(1,round((bump+.05)/.01))):
            sliders.nth(index).press('Home')
            for _ in range(steps):
                sliders.nth(index).press('ArrowRight')
        label = f'Spacing: {gap:.2f} GBP; middle quote change: {bump:.2f} GBP'
        page.wait_for_function("""label => window.chapterMessages.filter(m=>m.id==='distribution-resolution-widget' && m.echart)
            .at(-1)?.echart.includes(label)""",arg=label,timeout=60000)
        chart = payload_for(page,'distribution-resolution-widget')['densityResolutionExperiment']
        for clean,changed in zip(chart['series']['Clean price differences'],chart['series']['Perturbed mid differences']):
            strike = clean[0]
            expected = (call(strike-gap)-2*call(strike)+call(strike+gap))*1.05/gap**2
            near(clean[1],expected)
            effect = -2*bump if strike==105 else bump if abs(strike-105)==gap else 0
            near(changed[1]-clean[1],effect*1.05/gap**2)
        selected = chart['series']['Selected central reading'][0]
        near(selected[0],105)
        if gap==1 and bump>0:
            assert selected[1]<0
        output.locator('.text-output').get_by_text(label,exact=False).wait_for()
        if inspect_axes:
            page.wait_for_function("""label => {
                const message=window.chapterMessages.filter(m=>m.id==='distribution-resolution-widget' && m.echart).at(-1);
                if (!message?.echart.includes(label)) return false;
                const expected=JSON.parse(message.echart.split('<ECHARTS_DATA>')[1]).densityResolutionExperiment.series;
                const rendered=document.querySelector('[data-editor-output="distribution-resolution-widget"] .chart')
                    .__vueParentComponent.exposed.chart.getOption().series;
                return rendered.every(s=>JSON.stringify(s.data)===JSON.stringify(expected[s.name]));
            }""",arg=label,timeout=60000)
            check_rendered(page,'distribution-resolution-widget')
            marker = output.locator('.chart').evaluate("""el => {
                const s=el.__vueParentComponent.exposed.chart.getOption().series.find(s=>s.name==='Selected central reading');
                return [s.type,s.symbol,s.symbolSize,s.itemStyle.borderWidth];
            }""")
            assert marker==['scatter','diamond',18,2]
        for name,original in frozen.items():
            assert payload_for(page,name)==original,name
    assert page.locator('.chart-panel').count()==8
    print('PASS: standalone spacing/quote controls, negative readings, noise scaling, marker, and isolated outputs.',flush=True)


def check_navigation(page):
    page.evaluate('window.distributionNavigationSentinel=true')
    page.locator('.vp-doc').get_by_role('link',name='Building Structured Products',exact=True).click()
    page.wait_for_function("document.querySelector('.vp-doc h1')?.textContent.includes('Building Structured Products')")
    assert page.get_by_role('slider').count()==0
    page.locator('.vp-doc').get_by_role('link',name='Butterflies, Implied Distributions, and Tail Pricing',exact=True).first.click()
    page.wait_for_function("document.querySelector('.vp-doc h1')?.textContent.includes('Butterflies, Implied Distributions, and Tail Pricing')")
    assert page.evaluate('window.distributionNavigationSentinel===true')
    assert page.locator('.chart-panel').count()==0
    page.evaluate('window.chapterMessages=[]')
    page.locator('[data-editor-id="distribution-resolution-widget"] button.run').click()
    sliders = page.locator('[data-editor-output="distribution-resolution-widget"]').get_by_role('slider')
    sliders.nth(0).wait_for(timeout=30000)
    sliders.nth(0).press('Home')
    page.wait_for_function("""() => window.chapterMessages.filter(m=>m.id==='distribution-resolution-widget' && m.echart)
        .at(-1)?.echart.includes('Spacing: 1.00 GBP')""",timeout=60000)
    assert page.locator('.chart-panel').count()==1
    assert not page.evaluate('window.chapterMessages.some(m=>m.error)')
    print('PASS: named structured-products route and remounted density widget.',flush=True)
