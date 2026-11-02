"""Independent movement/range payoffs, prices, risk units, and execution ledgers."""
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


def shape(name,spot):
    spot = np.asarray(spot)
    if name=='Straddle':
        return np.abs(spot-100)
    if name=='Strangle':
        return np.maximum(np.abs(spot-100)-10,0)
    return np.clip(10-np.maximum(np.abs(spot-100)-(5 if name=='Condor' else 0),0),0,10)


class MovementStrategyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.markdown = (ROOT/'docs/option-movement-range.md').read_text()
        cls.examples = {name:code for code,name in re.findall(
            r'```python:line-numbers\n(.*?)\n```\s*<Editor id="([^"]+)"\s*/>',cls.markdown,re.S)}
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

    def near(self,a,b,atol=1e-8,rtol=1e-6):
        np.testing.assert_allclose(a,b,atol=atol,rtol=rtol)

    def test_runnable_examples_chart_units_and_finite_payloads(self):
        self.assertEqual((len(self.examples),len(self.charts)),(8,7))
        self.assertEqual(list(self.examples),re.findall(r'<Editor id="([^"]+)"',self.markdown))
        self.assertNotIn('—',self.markdown)
        for chart in self.charts.values():
            self.assertTrue(chart['xAxis']['name'])
            self.assertTrue(chart['yAxisName'])
            json.dumps(chart,allow_nan=False)
            for points in chart['series'].values():
                self.assertTrue(np.isfinite(points).all())

    def test_every_payoff_region_against_independent_shapes(self):
        v = self.v
        points = np.r_[np.linspace(0,200,2001),[84.999,85,85.001,89.999,90,90.001,95,100,105,110,115,10000]]
        for name,legs in v['strategies'].items():
            self.near(v['payoff'](legs,points),shape(name,points))
        self.near(v['payoff'](v['straddle'],0),100)
        self.near(v['payoff'](v['straddle'],10000),9900)

    def test_prices_by_direct_discounted_payoff_integration(self):
        v = self.v
        for spot,t,vol in ((100,1,.2),(108,.5,.1),(85,.25,.35)):
            scale = vol*np.sqrt(t)
            for name,legs in v['strategies'].items():
                knots = sorted(set((np.log(k/spot)-(v['r']-.5*vol**2)*t)/scale for _,_,k in legs))
                cuts = sorted(set([-12.,12.]+[k for k in knots if -12<k<12]))
                integral = sum(quad(lambda z:float(shape(name,spot*np.exp((v['r']-.5*vol**2)*t+scale*z)))*norm.pdf(z),
                                    lo,hi,epsabs=1e-10)[0] for lo,hi in zip(cuts,cuts[1:]))
                self.near(v['value'](legs,spot=spot,remaining=t,vol=vol),np.exp(-v['r']*t)*integral)

    def test_break_evens_profit_bounds_and_short_reversal(self):
        v = self.v
        points = np.linspace(0,300,3001)
        for name,legs in v['strategies'].items():
            cost = v['costs'][name]*v['growth']
            breaks = v[name.lower()+'_breaks']
            self.near(v['payoff'](legs,breaks)-cost,0)
            profits = shape(name,points)-cost
            self.near(profits.min(),-cost)
            if name in ('Butterfly','Condor'):
                self.near(profits.max(),10-cost)
            reversed_legs = [(-n,kind,k) for n,kind,k in legs]
            self.near(v['payoff'](reversed_legs,points)-v['value'](reversed_legs)*v['growth'],-profits)

    def test_strangle_experiment_reprices_and_moves_break_evens(self):
        v = self.v
        wider = [(1,'put',85),(1,'call',115)]
        cost = v['value'](wider)
        self.assertLess(cost,v['costs']['Strangle'])
        self.assertLess(85-cost*v['growth'],v['strangle_breaks'][0])
        self.assertGreater(115+cost*v['growth'],v['strangle_breaks'][1])

    def test_broader_plateau_dominates_payoff_but_not_profit(self):
        v = self.v
        s = np.linspace(0,200,401)
        self.assertTrue(np.all(shape('Condor',s)>=shape('Butterfly',s)))
        self.assertGreater(v['costs']['Condor'],v['costs']['Butterfly'])
        self.assertLess(10-v['condor_funded'],10-v['butterfly_funded'])
        self.assertGreater(shape('Condor',95)-v['condor_funded'],shape('Butterfly',95)-v['butterfly_funded'])

    def test_analytic_risk_sums_against_price_derivatives(self):
        v = self.v
        for name,legs in v['strategies'].items():
            value = lambda s:v['value'](legs,spot=s)
            h = .01
            delta = (value(100+h)-value(100-h))/(2*h)
            gamma = (value(100+h)-2*value(100)+value(100-h))/h**2
            dv = .0001
            vega_point = .01*(v['value'](legs,vol=.2+dv)-v['value'](legs,vol=.2-dv))/(2*dv)
            self.near(v['risks'](legs),[delta,gamma,vega_point],atol=1e-7,rtol=1e-5)
        self.assertGreater(v['risk_table'].loc['Straddle','Delta shares'],.26)
        self.assertLess(v['risk_table'].loc['Butterfly','Vega GBP/point'],0)

    def test_early_exit_elapsed_funding_and_volatility_scenario(self):
        v = self.v
        self.near(v['exit_funding'],v['costs']['Straddle']*np.sqrt(1.05))
        self.near(v['exit_value']-v['exit_funding'],-3.723531274)
        restored = v['value'](v['straddle'],spot=110,remaining=.5,vol=.2)-v['exit_funding']
        self.near(restored,-.757526304)
        index = np.argmin(abs(v['vol_grid']-.2))
        for changes in v['vol_changes'].values():
            self.near(changes[index],0)

    def test_execution_sides_and_contract_cash_ledger(self):
        v = self.v
        rows = v['exercise'].set_index('Strategy')
        for name,legs in v['strategies'].items():
            cash = 0.
            final = 0.
            for n,kind,k in legs:
                mid = v['option_price'](k,kind)
                paid = mid+.05 if n>0 else mid-.05
                cash -= 100*n*paid
                final += 100*n*max(108-k if kind=='call' else k-108,0)
            wealth = cash*1.05+final
            self.near(rows.loc[name,'Executed profit/100'],wealth)
            self.near(rows.loc[name,'Model profit/100']-wealth,100*.05*sum(abs(n) for n,_,_ in legs)*1.05)
        self.near(rows.loc['Butterfly','Executed profit/100'],-14.441158943)
        self.near(rows.loc['Condor','Executed profit/100'],303.538311546)

    def test_price_limits_and_invalid_inputs(self):
        price = self.v['option_price']
        self.near(price(100,remaining=0,spot=108),8)
        self.near(price(100,'put',spot=0),100/1.05)
        self.near(price(100,vol=0),100-100/1.05)
        for inputs in ({'strike':0},{'strike':100,'spot':-1},{'strike':100,'remaining':-1},
                       {'strike':100,'vol':-1},{'strike':100,'kind':'bad'},{'strike':np.nan}):
            with self.assertRaises(ValueError):
                price(**inputs)

    def test_all_187_widget_settings_and_degenerate_butterfly(self):
        v = self.v
        last_debit = -1
        for half in range(11):
            strikes = [90-half,100-half,100+half,110+half]
            legs = list(zip([1,-1,-1,1],['call']*4,strikes))
            debit = v['value'](legs)
            self.assertGreater(debit,last_debit)
            last_debit = debit
            for final in range(60,141,5):
                with contextlib.redirect_stdout(out := io.StringIO()):
                    pok.show_option_range_echart(half,final)
                chart = json.loads(out.getvalue().split('<ECHARTS_DATA>')[1])['optionRangeExperiment']
                curve = np.array(chart['series']['Expiry payoff'])
                expected = np.clip(10-np.maximum(np.abs(curve[:,0]-100)-half,0),0,10)
                self.near(curve[:,1],expected)
                self.near(np.array(chart['series']['Financed profit'])[:,1],expected-debit*1.05)
                selected = np.clip(10-max(abs(final-100)-half,0),0,10)-debit*1.05
                self.near(chart['series']['Selected profit'],[[final,selected]])
                self.assertEqual(chart['seriesOptions']['Selected profit']['symbol'],'diamond')
            if half==0:
                self.near(debit,v['costs']['Butterfly'])
            if half==5:
                self.near(debit,v['costs']['Condor'])
        for args in [(-1,100),(11,100),(5,59),(5,141),(True,100),(5,np.nan),('5',100)]:
            with self.assertRaises(ValueError):
                pok.show_option_range_echart(*args)

    def test_six_copy_parity_and_standalone_widget_serialization(self):
        definitions,outputs = [],[]
        for index,path in enumerate(MODULE_PATHS):
            tree = ast.parse((ROOT/path).read_text())
            definitions.append(ast.dump(next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='show_option_range_echart')))
            spec = importlib.util.spec_from_file_location(f'range_copy_{index}',ROOT/path)
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            with contextlib.redirect_stdout(out := io.StringIO()):
                module.show_option_range_echart()
            outputs.append(out.getvalue())
        self.assertEqual(len(set(definitions)),1)
        self.assertEqual(len(set(outputs)),1)
        ns = {}
        with contextlib.redirect_stdout(io.StringIO()):
            exec(self.examples['movement-range-widget'],ns)
        widget = ns['widget_instance']
        try:
            export = next(block for block in re.findall(r'pyodide\.runPython\(`(.*?)`\)',(ROOT/'src/pyodide-worker.js').read_text(),re.S)
                          if 'from ipywidgets.embed import dependency_state' in block)
            exec(export,ns)
            state = json.loads(ns['_widget_json_result'])['state']
            self.assertEqual(state[widget.model_id]['state']['_echarts_callback'],'show_option_range_echart')
            self.assertEqual(state[widget.model_id]['state']['_echarts_kwargs'],{'half_plateau':5.,'final_spot':100.})
            self.assertEqual({x['state']['_echarts_parameter'] for x in state.values() if x['model_name']=='FloatSliderModel'},
                             {'half_plateau','final_spot'})
        finally:
            widget.close()


if __name__=='__main__':
    unittest.main()
