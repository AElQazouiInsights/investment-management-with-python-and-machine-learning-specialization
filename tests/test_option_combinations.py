"""Independent payoff, financing, parity, Greek, and execution checks for combinations."""
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
from test_greeks_examples import derivative


class OptionCombinationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.markdown = (ROOT/'docs/option-combinations.md').read_text()
        cls.examples = dict((name,code) for code,name in re.findall(
            r'```python:line-numbers\n(.*?)\n```\s*<Editor id="([^"]+)"\s*/>',cls.markdown,re.S))
        cls.v = {}
        with contextlib.redirect_stdout(out := io.StringIO()):
            for name,code in cls.examples.items():
                exec(compile(code,name,'exec'),cls.v)
        cls.charts = {}
        for line in out.getvalue().splitlines():
            if line.startswith('<ECHARTS_DATA>'):
                cls.charts.update(json.loads(line[len('<ECHARTS_DATA>'):]))

    @classmethod
    def tearDownClass(cls):
        cls.v['widget_instance'].close()

    def near(self, actual, expected, atol=1e-7):
        np.testing.assert_allclose(actual,expected,atol=atol,rtol=1e-6)

    def test_cells_and_finite_chart_units(self):
        self.assertEqual(list(self.examples),re.findall(r'<Editor id="([^"]+)"',self.markdown))
        self.assertEqual(len(self.examples),14)
        self.assertEqual(len(self.charts),15)
        self.assertNotIn('—',self.markdown)
        for chart in self.charts.values():
            self.assertTrue(chart['xAxis']['name'])
            self.assertTrue(chart['yAxisName'])
            json.dumps(chart,allow_nan=False)
            for data in chart['series'].values():
                self.assertTrue(np.isfinite(data).all())

    def test_prices_from_discounted_piecewise_payoff_integrals(self):
        # Integrate terminal payoffs across independent lognormal states, splitting at all strikes.
        v = self.v
        for spot,remaining,rate,vol in [(100,1,np.log1p(.05),.2),(85,.4,-.02,.35)]:
            scale = vol*np.sqrt(remaining)
            terminal = lambda z:spot*np.exp((rate-vol*vol/2)*remaining+scale*z)
            for name,(legs,stock) in v['strategies'].items():
                cuts = sorted({-12.,12.} | {(np.log(k/spot)-(rate-vol*vol/2)*remaining)/scale for _,_,k in legs})
                def state_value(z):
                    s = terminal(z)
                    return stock*s+sum(n*(max(s-k,0) if kind=='call' else max(k-s,0)) for n,kind,k in legs)
                expected = np.exp(-rate*remaining)*sum(quad(lambda z:state_value(z)*norm.pdf(z),a,b,epsabs=1e-9)[0]
                                                      for a,b in zip(cuts[:-1],cuts[1:]))
                with self.subTest(strategy=name,spot=spot):
                    self.near(v['value'](legs,stock,spot,remaining,rate,vol),expected)

    def test_all_terminal_regions_and_strike_boundaries(self):
        v = self.v
        prices = np.array([0,89.99,90,95,99.99,100,100.01,105,109.99,110,110.01,160,10000.])
        bull = np.clip(prices-100,0,10)
        expected = {'Bull call':bull,'Bull put':bull-10,'Bear put':10-bull,'Bear call':-bull,
                    'Covered call':np.minimum(prices,110),'Protective put':np.maximum(prices,90),
                    'Collar':np.clip(prices,90,110),'Box':np.full(len(prices),10.)}
        for name,(legs,stock) in v['strategies'].items():
            self.near(v['payoff'](legs,stock,prices),expected[name])

    def test_funded_debit_credit_equivalence_at_varied_rates(self):
        v = self.v
        for rate in (-.03,0,.08):
            for remaining in (.25,2.):
                def pnl(name):
                    legs,stock = v['strategies'][name]
                    cost = v['value'](legs,stock,remaining=remaining,rate=rate)
                    return v['payoff'](legs,stock)-cost*np.exp(rate*remaining)
                self.near(pnl('Bull call'),pnl('Bull put'))
                self.near(pnl('Bear put'),pnl('Bear call'))
                self.near(pnl('Bull call'),-pnl('Bear put'))
                self.near(pnl('Box'),0)

    def test_synthetic_stock_overlay_prices_and_expiry_limits(self):
        v = self.v
        for spot in (0.,60.,100.,200.):
            for remaining,rate,vol in [(0.,.05,.2),(1.,-.02,.3),(2.,.06,0.)]:
                f = lambda k,kind:v['option_price'](spot,k,remaining,rate,vol,kind)
                d = np.exp(-rate*remaining)
                self.near(v['value'](v['covered'],1,spot,remaining,rate,vol),110*d-f(110,'put'))
                self.near(v['value'](v['protective'],1,spot,remaining,rate,vol),90*d+f(90,'call'))
                self.near(v['value'](v['collar'],1,spot,remaining,rate,vol),90*d+f(90,'call')-f(110,'call'))

    def test_financed_break_evens_and_global_bounds(self):
        v = self.v
        cases = [('Bull call',104.6128259048,-4.6128259048,5.3871740952),
                 ('Bull put',104.6128259048,-4.6128259048,5.3871740952),
                 ('Bear put',104.6128259048,-5.3871740952,4.6128259048),
                 ('Bear call',104.6128259048,-5.3871740952,4.6128259048),
                 ('Covered call',98.7072324332,-98.7072324332,11.2927675668),
                 ('Protective put',107.4528309658,-17.4528309658,None),
                 ('Collar',101.160063399,-11.160063399,8.839936601)]
        for name,root,minimum,maximum in cases:
            legs,stock = v['strategies'][name]
            f = lambda final:v['payoff'](legs,stock,final)-v['value'](legs,stock)*v['growth']
            self.near(f(root),0)
            values = f(np.r_[v['terminal'],100000.])
            self.near(values.min(),minimum)
            if maximum is not None:
                self.near(values.max(),maximum)
            else:
                self.assertGreater(f(100000),f(10000))

    def test_zero_premium_collar_is_not_principal_protection(self):
        v = self.v
        self.near(v['zero_collar_cost'],100)
        self.near(v['zero_collar_strike'],124.7751572458)
        self.near(v['zero_collar_wealth'].min(),90)
        self.near((v['zero_collar_wealth']-100*1.05).min(),-15)
        self.assertGreater(v['option_price'](100,v['zero_collar_strike']-.1),v['option_price'](100,90,kind='put'))
        self.assertLess(v['option_price'](100,v['zero_collar_strike']+.1),v['option_price'](100,90,kind='put'))

    def test_aggregate_greeks_from_basket_price_derivatives(self):
        v = self.v
        for spot,remaining,rate,vol in [(100,1,v['r'],.2),(85,.4,-.02,.35),(120,.1,.04,.15)]:
            for name,(legs,stock) in v['strategies'].items():
                f = lambda s=spot,t=remaining,r=rate,vol=vol:v['value'](legs,stock,s,t,r,vol)
                expected = [derivative(lambda s:f(s=s),spot,.001),
                            (f(s=spot+.01)-2*f()+f(s=spot-.01))/.01**2,
                            derivative(lambda sigma:f(vol=sigma),vol,1e-5)*.01,
                            -derivative(lambda t:f(t=t),remaining,1e-5)/365,
                            derivative(lambda r:f(r=r),rate,1e-5)*.0001]
                with self.subTest(strategy=name,spot=spot):
                    self.near(v['basket_risk'](legs,stock,spot,remaining,rate,vol),expected,atol=2e-6)
        risk = v['basket_risk'](v['bull_call'])
        self.assertGreater(risk[0],0)
        self.assertLess(risk[1],0)
        self.assertLess(risk[2],0)

    def test_box_discount_risk_and_calendar_accrual(self):
        v = self.v
        expected = [0,0,0,v['r']*10/1.05/365,-10/1.05*.0001]
        self.near(v['basket_risk'](v['box']),expected)
        bull_call = v['basket_risk'](v['bull_call'])
        bull_put = v['basket_risk'](v['bull_put'])
        self.near(bull_call-bull_put,expected)
        for elapsed in (0.,.25,.9,1.):
            price = v['value'](v['box'],remaining=1-elapsed)
            self.near(price,v['box_cost']*np.exp(v['r']*elapsed))

    def test_early_exit_uses_elapsed_funding_and_remaining_option_life(self):
        v = self.v
        # Close legs separately and repay the original loan; keep the opening rate fixed.
        for elapsed in (.2,.5,.8):
            proceeds = v['option_price'](105,100,1-elapsed)-v['option_price'](105,110,1-elapsed)
            cash = -v['bull_debit']*1.05**elapsed+proceeds
            self.near(cash,v['value'](v['bull_call'],spot=105,remaining=1-elapsed)-v['bull_debit']*np.exp(v['r']*elapsed))
        self.near(v['exit_table']['Profit GBP'],[.776132652,.419169620])
        self.assertGreater(v['exit_table'].iloc[0]['Exit value GBP'],v['exit_table'].iloc[1]['Exit value GBP'])

    def test_bid_ask_cash_ledger_both_directions_and_fees(self):
        v = self.v
        for _,(legs,stock) in v['strategies'].items():
            for sign in (-1.,1.):
                signed = [(sign*n,kind,k) for n,kind,k in legs]
                h = sign*stock
                cash = -h*(100+.02 if h>0 else 100-.02)
                for n,kind,k in signed:
                    mid = v['option_price'](100,k,kind=kind)
                    cash -= n*(mid+.1 if n>0 else mid-.1)+abs(n)*.03
                self.near(-cash,v['executed_cost'](signed,h,fee_per_option=.03))
        self.near(10-v['filled_box_cost']*1.05,-.42)
        self.near(v['filled_bull_cost']-v['bull_debit'],.2)

    def test_worked_contract_multiplier_and_residual_delta(self):
        v = self.v
        self.near(v['exercise_entry'],9954.27115714368)
        self.near(v['exercise_funded'],10451.9847150009)
        self.near(v['exercise_wealth'],[9500,10500,11500])
        self.near(v['exercise_delta'],36.4538263577)
        self.near(v['exercise_break_even'],104.519847150009)
        self.assertGreater(v['exercise_delta'],0)

    def test_all_widget_controls_and_invalid_inputs(self):
        v = self.v
        for strike in range(105,131,5):
            debit = v['option_price'](100,100)-v['option_price'](100,strike)
            for final in range(0,161,5):
                with contextlib.redirect_stdout(out := io.StringIO()):
                    pok.show_option_spread_echart(strike,final)
                data = json.loads(out.getvalue().split('<ECHARTS_DATA>')[1])['optionSpread']
                selected = np.clip(final-100,0,strike-100)
                self.near(data['series']['Selected payoff'][0],[final,selected])
                self.near(data['series']['Selected profit'][0],[final,selected-debit*1.05])
                self.assertEqual(data['seriesOptions']['Selected payoff']['symbol'],'circle')
                self.assertEqual(data['seriesOptions']['Selected profit']['symbol'],'diamond')
                self.assertTrue(any(point==[strike,strike-100] for point in data['series']['Payoff']))
        for args in [(104,120),(131,120),(110,-1),(110,161),(True,100),(110,np.nan),(110,'100')]:
            with self.assertRaises(ValueError):
                pok.show_option_spread_echart(*args)

    def test_six_copy_helper_parity_and_standalone_serialization(self):
        definitions, outputs = [], []
        for index,path in enumerate(MODULE_PATHS):
            tree = ast.parse((ROOT/path).read_text())
            definitions.append(ast.dump(next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='show_option_spread_echart')))
            spec = importlib.util.spec_from_file_location(f'combinations_copy_{index}',ROOT/path)
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            with contextlib.redirect_stdout(out := io.StringIO()):
                module.show_option_spread_echart()
            outputs.append(out.getvalue())
        self.assertEqual(len(set(definitions)),1)
        self.assertEqual(len(set(outputs)),1)
        ns = {}
        with contextlib.redirect_stdout(io.StringIO()):
            exec(self.examples['combinations-strike-widget'],ns)
        widget = ns['widget_instance']
        try:
            export = next(block for block in re.findall(r'pyodide\.runPython\(`(.*?)`\)',(ROOT/'src/pyodide-worker.js').read_text(),re.S)
                          if 'from ipywidgets.embed import dependency_state' in block)
            exec(export,ns)
            state = json.loads(ns['_widget_json_result'])['state']
            self.assertEqual(state[widget.model_id]['state']['_echarts_callback'],'show_option_spread_echart')
            self.assertEqual(state[widget.model_id]['state']['_echarts_kwargs'],{'upper_strike':110.,'final_spot':120.})
            self.assertEqual({x['state']['_echarts_parameter'] for x in state.values() if x['model_name']=='FloatSliderModel'},
                             {'upper_strike','final_spot'})
        finally:
            widget.close()


if __name__ == '__main__':
    unittest.main()
