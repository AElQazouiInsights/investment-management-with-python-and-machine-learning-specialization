"""Reconcile live Greek, hedge, and widget outputs and navigation lifecycle."""
import math

from browser_robust_charts import payload_for
from browser_ml_charts import check_rendered


EDITORS = ('greeks-spot', 'greeks-time', 'greeks-volatility', 'greeks-vol-quotes', 'greeks-carry', 'greeks-cross',
           'greeks-higher', 'greeks-approximation-widget', 'greeks-attribution', 'greeks-book',
           'greeks-gamma-hedge', 'greeks-ledger', 'greeks-delta-one', 'greeks-frequency')


def near(a, b, tolerance=1e-7):
    assert math.isclose(a,b,abs_tol=tolerance), (a,b)


def call(s, vol):
    d1=(math.log(s/100)+math.log1p(.05)+vol*vol/2)/vol
    cdf=lambda x:(1+math.erf(x/math.sqrt(2)))/2
    return s*cdf(d1)-100/1.05*cdf(d1-vol)


def check_defaults(page, inspect_axes):
    if inspect_axes:
        for editor in EDITORS:
            check_rendered(page,editor)
    spot=payload_for(page,'greeks-spot')['greeksSpot']['series']
    for x,y in spot['Exact repricing']:
        near(y,call(100+x,.2)-call(100,.2))
    near(spot['Delta + gamma'][50][1],3.407809804)
    neutral=payload_for(page,'greeks-spot')['greeksDeltaNeutral']['series']
    near(neutral['Exact hedged P&L'][40][1],0)
    assert neutral['Exact hedged P&L'][42][1]<-.9
    quotes=payload_for(page,'greeks-vol-quotes')['greeksVolQuotes']['series']
    near(quotes['Quoted strike 90'][0][0],20)
    near(quotes['Quoted strike 110'][0][0],20)
    near(quotes['Quoted strike 90'][0][1],16.621743776917896)
    near(quotes['Quoted strike 110'][0][1],5.993111968355159)
    gamma=payload_for(page,'greeks-gamma-hedge')['greeksGammaHedge']['series']
    near(gamma['Delta and gamma hedge'][40][1],0)
    assert abs(gamma['Delta and gamma hedge'][44][1])<abs(gamma['Delta hedge only'][44][1])
    future=payload_for(page,'greeks-delta-one')['greeksDeltaOne']['series']
    near(future['Move in futures quote'][12][1],10)
    near(future['Move in spot at fixed carry'][12][1],10.5)
    time=payload_for(page,'greeks-time')['greeksTime']['series']
    assert time['Put'][0][1]>0
    near(time['Call'][40][1],-.017403935)
    carry=payload_for(page,'greeks-carry')['greeksCarry']['series']['Linear']
    near(carry[0]+carry[1],carry[2])
    attribution=payload_for(page,'greeks-attribution')['greeksAttribution']['series']['Amount']
    near(sum(attribution[:-1]),attribution[-1])
    near(attribution[-1],1.657700768)
    book=payload_for(page,'greeks-book')['greeksBook']['series']['Hedged book']
    assert max(abs(x) for x in book)<1e-10
    ledger=payload_for(page,'greeks-ledger')
    wealth=ledger['greeksLedger']['series']
    net=ledger['greeksLedgerCosts']['series']
    for asset,liability,pnl in zip(wealth['Hedge wealth'],wealth['Call liability'],net['With costs']):
        near(asset[1]-liability[1],pnl[1])
    near(net['With costs'][-1][1],5.165924444)
    frequency=payload_for(page,'greeks-frequency')
    rms=frequency['greeksFrequency']['series']['No costs']
    assert rms[-1]<rms[0]
    fees=frequency['greeksTurnover']['series']['Funded fees']
    assert fees[-1]>fees[0]
    exercise=page.locator('[data-editor-output="greeks-exercise"]').inner_text()
    for value in ('94.839560805','9.255393431','-9.319139860','-90.129060269'):
        assert value in exercise,value
    assert page.locator('[data-editor-output="greeks-exercise"] .jupyter-widgets').count()==0
    print('PASS: Greek units, exact repricing, cross-effects, hedge budget, costs, and worked answers.',flush=True)


def check_controls(page, inspect_axes):
    output=page.locator('[data-editor-output="greeks-approximation-widget"]')
    sliders=output.get_by_role('slider')
    assert sliders.count()==page.get_by_role('slider').count()==2
    frozen={editor:payload_for(page,editor) for editor in EDITORS if editor!='greeks-approximation-widget'}
    for move,vol,move_keys,vol_keys in [(5,20,[],[]),(-20,10,['Home'],['Home']),
                                     (20,60,['End'],['End']),(0,20,['Home']+['ArrowRight']*20,['Home']+['ArrowRight']*2)]:
        for key in move_keys: sliders.nth(0).press(key)
        for key in vol_keys: sliders.nth(1).press(key)
        label=f'Spot move: {move:.2f} GBP; baseline volatility: {vol:.2f}%'
        page.wait_for_function("""label => window.chapterMessages.filter(m => m.id === 'greeks-approximation-widget' && m.echart)
            .at(-1)?.echart.includes(label)""",arg=label,timeout=30000)
        chart=payload_for(page,'greeks-approximation-widget')['greeksApproximation']
        data=chart['series']
        near(data['Selected exact'][0][0],move)
        near(data['Selected exact'][0][1],call(100+move,vol/100)-call(100,vol/100))
        assert data['Selected estimate'][0]==data['Delta + gamma'][(move+20)*2]
        output.locator('.text-output').get_by_text(label,exact=False).wait_for()
        if inspect_axes:
            page.wait_for_function("""expected => {
                const series=document.querySelector('[data-editor-output="greeks-approximation-widget"] .chart')
                    .__vueParentComponent.exposed.chart.getOption().series;
                return Math.abs(series.find(s=>s.name==='Selected exact').data[0][1]-expected)<1e-9;
            }""",arg=data['Selected exact'][0][1])
            check_rendered(page,'greeks-approximation-widget')
            markers=output.locator('.chart').evaluate("""el => el.__vueParentComponent.exposed.chart.getOption().series
                .filter(s=>s.name.startsWith('Selected')).map(s=>[s.type,s.symbol,s.symbolSize,s.itemStyle.borderWidth])""")
            assert markers==[['scatter','circle',24,3],['scatter','diamond',16,2]]
        for editor,original in frozen.items():
            assert payload_for(page,editor)==original,editor
    assert page.locator('.chart-panel').count()==19
    print('PASS: independent two-control widget, both parameter boundaries, selected markers, and output isolation.',flush=True)


def check_navigation(page):
    page.evaluate('window.greeksNavigationSentinel = true')
    page.locator('.vp-doc').get_by_role('link',name='Spreads and Basic Option Combinations',exact=True).last.click()
    page.wait_for_function("document.querySelector('.vp-doc h1')?.textContent.includes('Spreads and Basic Option Combinations')")
    assert page.get_by_role('slider').count()==0
    page.locator('.vp-doc').get_by_role('link',name='The Greeks and Hedging',exact=True).first.click()
    page.wait_for_function("document.querySelector('.vp-doc h1')?.textContent.includes('The Greeks and Hedging')")
    assert page.evaluate('window.greeksNavigationSentinel === true')
    assert page.locator('.chart-panel').count()==0
    page.evaluate('window.chapterMessages = []')
    page.locator('[data-editor-id="greeks-approximation-widget"] button.run').click()
    sliders=page.locator('[data-editor-output="greeks-approximation-widget"]').get_by_role('slider')
    sliders.nth(1).wait_for(timeout=30000)
    sliders.nth(1).press('End')
    page.wait_for_function("""() => window.chapterMessages.filter(m=>m.id==='greeks-approximation-widget' && m.echart)
        .at(-1)?.echart.includes('baseline volatility: 60.00%')""",timeout=30000)
    assert page.locator('.chart-panel').count()==1
    assert not page.evaluate('window.chapterMessages.some(m=>m.error)')
    print('PASS: named next-topic route and remounted Greek widget.',flush=True)
