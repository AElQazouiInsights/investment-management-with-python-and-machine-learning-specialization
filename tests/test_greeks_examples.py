"""Independent derivatives, parity, risk-rank, and funded hedge identities."""
import ast
import contextlib
import importlib.util
import io
import json
import re
import unittest

import numpy as np
from scipy.integrate import quad
from scipy.stats import norm
import PortfolioOptimizationKit as pok

from test_return_annualization import ROOT, MODULE_PATHS


def derivative(f, x, h):
    """Fourth-order centered stencil, independent of the chapter's formulas."""
    return (f(x-2*h)-8*f(x-h)+8*f(x+h)-f(x+2*h))/(12*h)


class GreeksTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.markdown = (ROOT/'docs/greeks-hedging.md').read_text()
        cls.examples = {editor: code for code, editor in re.findall(
            r'```python:line-numbers\n(.*?)\n```\s*<Editor id="([^"]+)"\s*/>', cls.markdown, re.S)}
        cls.v = {}
        with contextlib.redirect_stdout(out := io.StringIO()):
            for editor, code in cls.examples.items():
                exec(compile(code, editor, 'exec'), cls.v)
        cls.charts = {}
        for line in out.getvalue().splitlines():
            if line.startswith('<ECHARTS_DATA>'):
                cls.charts.update(json.loads(line[len('<ECHARTS_DATA>'):]))

    @classmethod
    def tearDownClass(cls):
        cls.v['widget_instance'].close()

    def assertNear(self, a, b, atol=1e-7, rtol=1e-6):
        self.assertTrue(np.isclose(a,b,atol=atol,rtol=rtol), (a,b))

    def test_cells_units_and_finite_charts(self):
        self.assertEqual(list(self.examples), re.findall(r'<Editor id="([^"]+)"', self.markdown))
        self.assertEqual(len(self.examples), 16)
        self.assertEqual(len(self.charts), 19)
        for chart in self.charts.values():
            self.assertTrue(chart['xAxis']['name'])
            self.assertTrue(chart['yAxisName'])
            json.dumps(chart, allow_nan=False)
            for values in chart['series'].values():
                self.assertTrue(np.isfinite(values).all())

    def test_prices_against_discounted_payoff_integrals(self):
        price = self.v['option_price']
        for s,k,t,r,vol,q in [(100,100,1,np.log1p(.05),.2,0), (80,85,.5,-.02,.3,.01), (120,100,2,.04,.25,.05)]:
            cutoff = (np.log(k/s)-(r-q-vol*vol/2)*t)/(vol*np.sqrt(t))
            terminal = lambda z: s*np.exp((r-q-vol*vol/2)*t+vol*np.sqrt(t)*z)
            call = np.exp(-r*t)*quad(lambda z:(terminal(z)-k)*norm.pdf(z),cutoff,12,epsabs=1e-10)[0]
            put = np.exp(-r*t)*quad(lambda z:(k-terminal(z))*norm.pdf(z),-12,cutoff,epsabs=1e-10)[0]
            self.assertNear(price(s,k,t,r,vol,q),call)
            self.assertNear(price(s,k,t,r,vol,q,'put'),put)

    def test_core_greeks_from_price_derivatives(self):
        price, greeks = self.v['option_price'], self.v['core_greeks']
        cases = [(100,100,1,np.log1p(.05),.2,0), (80,85,.5,-.02,.3,.01),
                 (120,100,2,.04,.25,.05), (100,100,.02,.01,.15,.02)]
        for args in cases:
            for kind in ('call','put'):
                g = greeks(*args,kind)
                for name, index, step, sign in [('delta',0,.001,1),('theta',2,1e-5,-1),
                                                ('vega',4,1e-5,1),('rho',3,1e-5,1),('yield_sensitivity',5,1e-5,1)]:
                    def f(x):
                        bumped = list(args); bumped[index] = x
                        return price(*bumped,kind)
                    self.assertNear(g[name], sign*derivative(f,args[index],step))
                h = .02
                prices = [price(args[0]+j*h,*args[1:],kind) for j in (-2,-1,0,1,2)]
                gamma = (-prices[0]+16*prices[1]-30*prices[2]+16*prices[3]-prices[4])/(12*h*h)
                self.assertNear(g['gamma'],gamma,atol=1e-8)

    def test_cross_and_higher_greeks_from_independent_lower_derivatives(self):
        core, cross, higher = [self.v[n] for n in ('core_greeks','cross_greeks','higher_greeks')]
        for args in [(100,100,1,.048790164,.2,0), (80,85,.5,-.02,.3,.01), (120,100,2,.04,.25,.05),
                     (100,100,.02,.01,.15,.02)]:
            for kind in ('call','put'):
                c, h = cross(*args,kind), higher(*args,kind)
                checks = [('vanna',core,'delta',4,1e-5,1),('vanna',core,'vega',0,.001,1),
                          ('charm',core,'delta',2,1e-5,-1),('volga',core,'vega',4,1e-5,1),
                          ('speed',core,'gamma',0,.001,1),('zomma',core,'gamma',4,1e-5,1),
                          ('color',core,'gamma',2,1e-5,-1),('veta',core,'vega',2,1e-5,-1),
                          ('ultima',cross,'volga',4,1e-5,1)]
                for name, function, field, index, step, sign in checks:
                    def f(x):
                        bumped = list(args); bumped[index] = x
                        return function(*bumped,kind)[field]
                    self.assertNear((c if name in c else h)[name],sign*derivative(f,args[index],step))

    def test_parity_derivatives_pde_and_units(self):
        v = self.v
        for s,k,t,r,vol,q in [(100,100,1,.05,.2,0), (80,85,.5,-.02,.3,.01), (120,100,2,.04,.25,.05)]:
            c,p = [v['core_greeks'](s,k,t,r,vol,q,kind) for kind in ('call','put')]
            a,b = np.exp(-q*t),np.exp(-r*t)
            self.assertNear(c['value']-p['value'],s*a-k*b)
            self.assertNear(c['delta']-p['delta'],a)
            self.assertNear(c['rho']-p['rho'],t*k*b)
            self.assertNear(c['yield_sensitivity']-p['yield_sensitivity'],-t*s*a)
            self.assertNear(c['theta']-p['theta'],q*s*a-r*k*b)
            for g in (c,p):
                self.assertNear(g['theta']+.5*vol*vol*s*s*g['gamma']+(r-q)*s*g['delta']-r*g['value'],0)
                self.assertNear(g['vega'],s*s*vol*t*g['gamma'])
        self.assertNear(v['g']['vega']*.01,.3760287721721686)
        self.assertNear(v['g']['theta']/365,-.0173960551152376)
        self.assertNear(v['g']['rho']*.0001,.005306955693695)
        self.assertNear(pok.compounding_rate_inv(.05),v['r'])

    def test_limits_and_sign_changes(self):
        v = self.v
        for rate in (-.02,0,.05):
            for s in (80,100,120):
                for kind,sign in [('call',1),('put',-1)]:
                    self.assertNear(v['option_price'](s,100,0,rate,.2,.01,kind),max(sign*(s-100),0))
                    self.assertNear(v['option_price'](s,100,1,rate,0,.01,kind),max(sign*(s*np.exp(-.01)-100*np.exp(-rate)),0))
        for t,vol in [(0,.2),(1,0)]:
            with self.assertRaises(ValueError):
                v['core_greeks'](100,100,t,.05,vol)
        self.assertGreater(v['core_greeks'](60,100,1,.05,.2,0,'put')['theta'],0)
        self.assertLess(v['cross_greeks'](100,100,1,0,.2)['volga'],0)
        self.assertGreater(v['core_greeks'](100,100,.001,0,.2)['gamma'],v['core_greeks'](100,100,1,0,.2)['gamma'])
        self.assertLess(v['core_greeks'](100,100,.001,0,.2)['vega'],v['core_greeks'](100,100,1,0,.2)['vega'])
        for args in [(0,100,1,.05,.2), (100,100,-1,.05,.2), (100,100,1,.05,-.2), (100,100,1,np.nan,.2)]:
            with self.assertRaises(ValueError): v['option_price'](*args)

    def test_independent_carry_discount_and_surface_chain_rule(self):
        v = self.v
        f,rate,t,vol = v['forward'],v['r'],v['tau'],v['sigma']
        self.assertNear(derivative(lambda rd:v['forward_call'](f,100,t,rd,vol),rate,1e-5),v['discount_sensitivity'])
        self.assertNear(derivative(lambda b:v['forward_call'](100*np.exp(b*t),100,t,rate,vol),rate,1e-5),v['carry_sensitivity'])
        self.assertNear(v['carry_sensitivity']+v['discount_sensitivity'],v['g']['rho'])
        self.assertNear(v['surface_fd'],v['surface_delta'])
        self.assertGreater(v['surface_delta'],v['g']['delta'])

    def test_multivariate_attribution_and_local_convergence(self):
        v = self.v
        self.assertNear(sum(v['joint_terms'])+v['joint_remainder'],v['exact_joint'])
        self.assertTrue(np.all(np.diff(np.abs(v['joint_errors']))<0))
        self.assertNear(v['joint_terms'][4],v['cross']['vanna']*2*.01)
        self.assertGreater(abs(v['joint_remainder']),1e-5)  # omitted terms are retained
        self.assertNear(v['exact_joint'],1.657700767641)

    def test_risk_rank_hedge_budget_and_residual_surface_exposure(self):
        v = self.v
        self.assertEqual(np.linalg.matrix_rank(v['same_expiry_matrix']),1)
        self.assertEqual(np.linalg.matrix_rank(v['risk_matrix']),2)
        # Hand solution exploits the independently established vega/gamma identity.
        expected = [2*v['g']['gamma']/3/v['hedge_risks'][0]['gamma'],v['g']['gamma']/3/v['hedge_risks'][1]['gamma']]
        np.testing.assert_allclose(v['option_units'],expected,atol=1e-12)
        for value in v['book_exposures'].values(): self.assertNear(value,0)
        self.assertNear(v['book_value'](),0)
        self.assertNear(v['book_cash']+v['stock_units']*100+sum(n*x['value'] for n,x in zip(v['option_units'],v['hedge_risks']))-v['g']['value'],0)
        self.assertGreater(abs(v['book_scenarios']['Target-only vol +1 point']),.37)
        self.assertLess(abs(v['book_scenarios']['Parallel vol +1 point']),.001)

    def test_ledger_discounted_gain_identity_and_exact_interval_explain(self):
        v = self.v
        for name in ('free_ledger','costly_ledger'):
            ledger=v[name]
            dates=ledger.Time.to_numpy(); stock=ledger.Spot.to_numpy(); units=ledger.Units.to_numpy()
            fees=ledger.Fee.to_numpy(); wealth=ledger['Hedge wealth'].to_numpy()
            np.testing.assert_allclose(ledger['Budget error'],0,atol=1e-12)
            np.testing.assert_allclose(ledger.Cash+ledger.Units*ledger.Spot,wealth,atol=1e-12)
            discounted_stock=stock*np.exp(-v['r']*dates)
            reconstructed=v['g']['value']+np.r_[0,np.cumsum(units[:-1]*np.diff(discounted_stock))]-np.cumsum(fees*np.exp(-v['r']*dates))
            np.testing.assert_allclose(wealth*np.exp(-v['r']*dates),reconstructed,atol=2e-12)
            self.assertEqual(units[-1],0)
            self.assertNear(ledger['Net P&L'].iloc[-1],ledger.Cash.iloc[-1]-3)
            interval=ledger['Stock gain']+ledger.Interest-ledger['Option change']-ledger.Fee
            np.testing.assert_allclose(interval,ledger['Net P&L'].diff().fillna(ledger['Net P&L'].iloc[0]),atol=2e-12)
        self.assertNear(v['free_ledger']['Net P&L'].iloc[-1]-v['costly_ledger']['Net P&L'].iloc[-1],v['funded_fees'])
        self.assertNear(v['costly_ledger']['Net P&L'].iloc[-1],5.1659244439)

    def test_funding_stress_and_gap_are_accounted_for(self):
        v=self.v
        stressed=v['delta_hedge'](v['hand_spots'],v['hand_dates'],funding_rate=v['r']+.02)
        self.assertLess(stressed['Net P&L'].iloc[-1],v['costly_ledger']['Net P&L'].iloc[-1])
        gap=v['delta_hedge']([100,120,97,105,103],v['hand_dates'])
        self.assertLess(gap['Net P&L'].iloc[1],v['costly_ledger']['Net P&L'].iloc[1])
        np.testing.assert_allclose(gap['Budget error'],0,atol=1e-12)
        with self.assertRaises(ValueError): v['delta_hedge']([100,105],[0,.5])

    def test_vectorized_ensemble_matches_single_path_accounts(self):
        v=self.v
        for count in (4,16,64,256):
            result=v['frequency_results'][count]
            np.testing.assert_allclose(result['no_cost']-result['with_cost'],result['fees'],atol=3e-12)
            for column in (0,17):
                ledger=v['delta_hedge'](v['paths'][::256//count,column],v['times'][::256//count])
                self.assertNear(ledger['Net P&L'].iloc[-1],result['with_cost'][column],atol=1e-10)
        self.assertLess(v['frequency_table']['RMS no cost'].iloc[-1],v['frequency_table']['RMS no cost'].iloc[0])
        self.assertGreater(v['frequency_table']['Mean funded fees'].iloc[-1],v['frequency_table']['Mean funded fees'].iloc[0])
        self.assertLess(v['misspecified_pnl'].mean(),-3.)

    def test_exercise_and_multiplier_units(self):
        v=self.v
        expected={'exercise_shares':94.8395608045,'exercise_futures':9.255393431,
                  'exercise_spot_approx':-9.383485913,'exercise_spot_exact':-9.319139860,
                  'exercise_vol_approx':-90.135268725,'exercise_vol_exact':-90.129060269}
        for key,value in expected.items(): self.assertNear(v[key],value,atol=1e-8)
        self.assertNear(v['exercise_futures']*10*np.exp(v['r']*.5),v['exercise_shares'])

    def test_desk_readings_match_position_risk_derivatives(self):
        v = self.v
        core = v['desk_core'].set_index('Greek')['One long 100-share contract']
        position = lambda s, t, rate, vol, yield_rate=0.: 100*v['option_price'](s,100,t,rate,vol,yield_rate)
        self.assertNear(core['Delta'],derivative(lambda s:position(s,1,v['r'],.2),100,.001))
        self.assertNear(core['Theta'],-derivative(lambda t:position(100,t,v['r'],.2),1,1e-5)/365)
        self.assertNear(core['Vega'],derivative(lambda vol:position(100,1,v['r'],vol),.2,1e-5)*.01)
        self.assertNear(core['Rho'],derivative(lambda rate:position(100,1,rate,.2),v['r'],1e-5)*.0001)
        self.assertNear(core['Yield sensitivity'],derivative(lambda q:position(100,1,v['r'],.2,q),0,1e-5)*.0001)
        self.assertNear(v['cash_delta']*.01,core['Delta'])  # one percent of spot 100 is GBP 1
        self.assertGreater(v['cash_delta'],100*v['g']['value'])
        desk = v['desk_higher'].set_index('Greek')['Predicted change']
        # Differentiate the desk's already-scaled risk readings in the displayed coordinates.
        f = v['core_greeks']; c = v['cross_greeks']
        checks = {
            'Vanna': derivative(lambda pp:100*f(100,100,1,v['r'],.2+pp*.01)['delta'],0,.001),
            'Volga': derivative(lambda pp:f(100,100,1,v['r'],.2+pp*.01)['vega'],0,.001),
            'Charm': derivative(lambda days:100*f(100,100,1-days/365,v['r'],.2)['delta'],0,.001),
            'Speed': derivative(lambda s:100*f(s,100,1,v['r'],.2)['gamma'],100,.001),
            'Zomma': derivative(lambda pp:100*f(100,100,1,v['r'],.2+pp*.01)['gamma'],0,.001),
            'Color': derivative(lambda days:100*f(100,100,1-days/365,v['r'],.2)['gamma'],0,.001),
            'Veta': derivative(lambda days:f(100,100,1-days/365,v['r'],.2)['vega'],0,.001),
            'Ultima': derivative(lambda pp:.01*c(100,100,1,v['r'],.2+pp*.01)['volga'],0,.001),
        }
        self.assertEqual(set(desk.index),set(checks))
        for name, expected in checks.items(): self.assertNear(desk[name],expected)

    def test_delta_neutrality_and_single_option_gamma_hedge(self):
        v = self.v
        self.assertNear(-100*v['g']['delta']+v['neutral_stock_shares'],0)
        self.assertNear(v['residual_delta_after_rise'],-1.85412787747705)
        self.assertLess(v['neutral_exact'][42],0)  # GBP 1 move despite initially zero delta
        self.assertNear(v['gamma_hedge_contracts'],.8007854445366344)
        self.assertNear(v['gamma_hedge_shares'],5.181704030670009)
        self.assertNear(v['gamma_hedge_cash'],-267.08607278792034)
        f = v['gamma_hedged_value']
        self.assertNear(f(),0)
        self.assertNear(derivative(f,0,.001),0,atol=1e-7)
        h = .01
        self.assertNear((f(h)-2*f()+f(-h))/(h*h),0,atol=2e-6)
        self.assertGreater(abs(f(1)),.001)  # hedge is local, not identical payoffs
        self.assertLess(abs(f(1)),abs(v['neutral_exact'][42]))
        self.assertNear(v['gamma_hedge_vega_point'],-18.80143860860843)
        self.assertLess(v['gamma_hedge_vega_point'],0)

    def test_volatility_quotes_and_funded_delta_neutral_scenarios(self):
        v = self.v
        np.testing.assert_allclose(v['recovered_vols'],[.2,.2],atol=1e-11)
        self.assertGreater(v['quoted_premiums'][0],v['quoted_premiums'][1]+10)
        for strike, premium, vol in zip(v['quoted_strikes'],v['quoted_premiums'],v['recovered_vols']):
            self.assertNear(v['option_price'](100,strike,1,v['r'],vol),premium)
        table = v['quote_scenarios'].set_index('Scenario')
        np.testing.assert_allclose(table[['Option GBP','Stock GBP','Interest GBP']].sum(axis=1),table['Net GBP'],atol=1e-12)
        self.assertGreater(table.loc['Spot +1','Net GBP'],.9)
        self.assertGreater(table.loc['Vol +1 point','Net GBP'],37)
        self.assertEqual(table.loc['Vol +1 point','Stock GBP'],0)
        self.assertLess(table.loc['One calendar day','Net GBP'],0)
        self.assertGreater(table.loc['One calendar day','Interest GBP'],0)
        self.assertNear(100*v['g']['value']-100*v['g']['delta']*100+v['long_hedge_cash'],0)

    def test_futures_delta_coordinates_and_multiplier(self):
        v = self.v
        self.assertNear(v['futures_delta_quote'],10)
        self.assertNear(v['futures_delta_spot'],10.5)
        self.assertNear(v['futures_for_short_contract'],6.04341299365789)
        self.assertNear(v['futures_for_short_contract']*v['futures_delta_spot'],v['neutral_stock_shares'])
        self.assertNear(v['option_delta_in_futures_quote']*v['futures_spot_slope'],v['g']['delta'])
        np.testing.assert_allclose(np.diff(v['futures_pnl_quote'],n=2),0,atol=1e-12)
        np.testing.assert_allclose(np.diff(v['futures_pnl_spot'],n=2),0,atol=1e-12)
        self.assertNear(v['futures_pnl_quote'][12],10)
        self.assertNear(v['futures_pnl_spot'][12],10.5)

    def test_all_widget_settings_and_markers(self):
        for vol in range(10,61,5):
            for move in range(-20,21):
                with contextlib.redirect_stdout(out:=io.StringIO()): pok.show_greeks_hedge_echart(move,vol)
                chart=json.loads(out.getvalue().split('<ECHARTS_DATA>')[1])['greeksApproximation']
                data=chart['series']; g=self.v['core_greeks'](100,100,1,np.log1p(.05),vol/100)
                exact=self.v['option_price'](100+move,100,1,np.log1p(.05),vol/100)-g['value']
                self.assertNear(data['Selected exact'][0][1],exact)
                self.assertNear(data['Selected estimate'][0][1],g['delta']*move+.5*g['gamma']*move*move)
                self.assertEqual(data['Selected exact'][0],data['Exact repricing'][(move+20)*2])
        for bad in [(True,20),(21,20),(0,9),(0,61),(np.nan,20),(0,'20')]:
            with self.assertRaises(ValueError): pok.show_greeks_hedge_echart(*bad)

    def test_helper_copies_and_standalone_widget_serialization(self):
        definitions,outputs=[],[]
        for index,path in enumerate(MODULE_PATHS):
            tree=ast.parse((ROOT/path).read_text())
            definitions.append(ast.dump(next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='show_greeks_hedge_echart')))
            spec=importlib.util.spec_from_file_location(f'greeks_copy_{index}',ROOT/path)
            module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            with contextlib.redirect_stdout(out:=io.StringIO()): module.show_greeks_hedge_echart()
            outputs.append(out.getvalue())
        self.assertEqual(len(definitions),6)
        self.assertEqual(len(set(definitions)),1)
        self.assertEqual(len(set(outputs)),1)
        ns={}
        with contextlib.redirect_stdout(io.StringIO()): exec(self.examples['greeks-approximation-widget'],ns)
        widget=ns['widget_instance']
        try:
            export=next(block for block in re.findall(r'pyodide\.runPython\(`(.*?)`\)',(ROOT/'src/pyodide-worker.js').read_text(),re.S)
                        if 'from ipywidgets.embed import dependency_state' in block)
            exec(export,ns)
            state=json.loads(ns['_widget_json_result'])['state']
            self.assertEqual(state[widget.model_id]['state']['_echarts_callback'],'show_greeks_hedge_echart')
            self.assertEqual(state[widget.model_id]['state']['_echarts_kwargs'],{'spot_move':5.,'volatility_percent':20.})
            parameters={x['state']['_echarts_parameter'] for x in state.values() if x['model_name']=='FloatSliderModel'}
            self.assertEqual(parameters,{'spot_move','volatility_percent'})
        finally:
            widget.close()


if __name__=='__main__':
    unittest.main()
