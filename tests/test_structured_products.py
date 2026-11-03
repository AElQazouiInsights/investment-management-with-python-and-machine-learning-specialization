"""Independent funded budgets, conditional payoffs, early marks, and execution checks."""
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


def price_by_integration(payoff,forward,discount,vol,time,knots):
    scale = vol*np.sqrt(time)
    cuts = sorted(set([-12.,12.]+[(np.log(k/forward)+.5*scale**2)/scale for k in knots
                                 if -12<(np.log(k/forward)+.5*scale**2)/scale<12]))
    return discount*sum(quad(lambda z:payoff(forward*np.exp(-.5*scale**2+scale*z))*norm.pdf(z),
                             lo,hi,epsabs=1e-9)[0] for lo,hi in zip(cuts,cuts[1:]))


class StructuredProductsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.markdown = (ROOT/'docs/structured-products.md').read_text()
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

    def test_cells_finite_charts_and_explicit_units(self):
        self.assertEqual((len(self.examples),len(self.charts)),(9,8))
        self.assertEqual(list(self.examples),re.findall(r'<Editor id="([^"]+)"',self.markdown))
        self.assertNotIn('—',self.markdown)
        for chart in self.charts.values():
            self.assertTrue(chart['xAxis']['name'])
            self.assertTrue(chart['yAxisName'])
            json.dumps(chart,allow_nan=False)
            for series in chart['series'].values():
                self.assertTrue(np.isfinite(series).all())

    def test_forward_black_against_integrals_with_independent_discount(self):
        v = self.v
        for f,k,t,d,vol in ((105,100,1,1/1.05,.2),(80,100,.5,.97,.25),(120,110,2,1.01,.3)):
            for kind in ('call','put'):
                payoff = lambda s:max(s-k if kind=='call' else k-s,0)
                expected = price_by_integration(payoff,f,d,vol,t,[k])
                self.near(v['black'](f,k,t,d,vol,kind),expected)
            self.near(v['black'](f,k,t,d,vol)-v['black'](f,k,t,d,vol,'put'),d*(f-k))
        self.near(v['black'](0,100,1,.95,.2,'put'),95)
        self.near(v['black'](110,100,0,1,.2),10)
        self.near(v['black'](105,100,1,.95,0),4.75)
        for args in ((105,0,1,1,.2),(105,100,-1,1,.2),(105,100,1,0,.2),(105,100,1,1,-.2),(np.nan,100,1,1,.2)):
            with self.assertRaises(ValueError):
                v['black'](*args)

    def test_all_three_terminal_payoffs_price_to_the_funded_budget(self):
        v = self.v
        protected = lambda s:100+v['protected_units']*max(s-100,0)
        capped = lambda s:100+v['capped_units']*(max(s-100,0)-max(s-120,0))
        income = lambda s:v['income_face']-max(100-s,0)
        for payment in (protected,capped,income):
            price = price_by_integration(payment,105,v['D'],.2,1,[100,120])
            self.near(price,100)
            self.near(price/v['D'],105)
        for design in (v['protected'],v['capped']):
            self.near(design['Bond cost']+design['Option units']*design['Unit option cost'],100)
        self.near(v['income_bond_cost']-v['put_100'],100)

    def test_participation_has_correct_notional_and_share_units(self):
        v = self.v
        original_n,original_s = v['N'],v['S0']
        try:
            v['N'],v['S0'] = 1000.,200.
            scaled = v['protected_terms']()
            self.near(scaled['Participation'],v['protected']['Participation'])
            self.near(scaled['Option units'],5*v['protected_units'])
            self.near(v['protected_payoff'](280,scaled['Option units']),10*(100+40*v['protected_units']))
            self.near(scaled['Option units']*200/1000,scaled['Participation'])
        finally:
            v['N'],v['S0'] = original_n,original_s

    def test_floor_cap_regions_and_cash_break_even_points(self):
        v = self.v
        s = np.r_[np.linspace(0,200,801),[99.999,100,100.001,119.999,120,120.001,10000]]
        for units,cap in ((v['protected_units'],None),(v['capped_units'],120)):
            independent = 100+units*np.maximum(s-100,0)
            if cap:
                independent -= units*np.maximum(s-cap,0)
            self.near(v['protected_payoff'](s,units,cap),independent)
            self.assertGreaterEqual(independent.min(),100-1e-9)
        self.near(v['protected_payoff'](v['protected_cash_break'],v['protected_units']),105)
        self.near(v['protected_payoff'](v['capped_cash_break'],v['capped_units'],120),105)
        self.near(v['capped_maximum'],113.28376129583359)
        tighter = v['protected_terms'](cap=110)
        self.assertGreater(tighter['Participation'],v['capped']['Participation'])
        self.assertLess(100+10*tighter['Option units'],v['capped_maximum'])

    def test_downside_funds_income_and_break_even_comparisons(self):
        v = self.v
        self.near(v['income_face'],110.9055934715555)
        self.near(v['income_payoff']([0,80,100,140]),[10.9055934715555,90.9055934715555,110.9055934715555,110.9055934715555])
        self.near(v['income_payoff'](v['income_nominal_break']),100)
        self.near(v['income_payoff'](v['income_cash_break']),105)
        self.assertLess(v['income_payoff'](80),100)

    def test_fees_and_unfundable_floor_rejection(self):
        v = self.v
        self.near(v['fee_one']['Participation'],.3621994539134984)
        self.near(1/v['protected']['Option budget'],.21)
        self.near(np.diff(v['fee_participation'])/np.diff(v['fees']),-1/v['call_100'])
        zero = v['protected_terms'](rate=0)
        self.near(zero['Bond cost'],100)
        self.near(zero['Option units'],0)
        for inputs in ({'fee':5},{'rate':-.01},{'rate':0,'fee':.01},{'rate':-1},
                       {'vol':0},{'fee':-1},{'cap':100},{'cap':np.nan},{'rate':np.nan}):
            with self.assertRaises(ValueError):
                v['protected_terms'](**inputs)

    def test_early_sale_prices_fixed_original_payoff_under_new_inputs(self):
        v = self.v
        payoff = lambda s:100+v['protected_units']*max(s-100,0)
        for spot in (40,80,100,140):
            expected = price_by_integration(payoff,spot/v['new_discount'],v['new_discount'],.25,.5,[100])
            self.near(v['protected_mark'](spot),expected)
        self.near(v['early_value'],97.19021170122082)
        self.near(v['early_cash'],100*np.sqrt(1.05))
        self.assertLess(v['early_value'],100)
        self.near(v['protected_units'],v['protected']['Option units'])

    def test_explicit_default_recovery_removes_the_nominal_floor(self):
        v = self.v
        self.near(v['default_payments'][0],40)
        index = np.flatnonzero(v['terminal']==140)[0]
        self.near(v['default_payments'][index],47.33568514255186)
        self.assertTrue(np.all(v['default_payments']<v['promised_payments']))

    def test_executed_capped_budget_and_fair_value_reconciliation(self):
        v = self.v
        units = v['exercise_units']
        # Independent cash ledger: purchases negative, sold upper call positive.
        cash = 100-1-100/1.05-units*(v['call_100']+.1)+units*(v['call_120']-.1)
        self.near(cash,0)
        self.near(units,.5104685910685981)
        self.near(v['exercise_payments'],[100,105.104685910686,110.209371821372])
        self.near(v['model_mid_value']+v['exercise_fee']+v['execution_cost'],100)
        independent = price_by_integration(lambda s:100+units*(max(s-100,0)-max(s-120,0)),105,v['D'],.2,1,[100,120])
        self.near(independent,98.89790628178628)
        self.assertLess(independent,99)

    def test_all_221_widget_settings_reconcile_new_issue_terms(self):
        v = self.v
        for rate in np.arange(0,8.01,.5):
            for vol in np.arange(10,40.01,2.5):
                with contextlib.redirect_stdout(out := io.StringIO()):
                    pok.show_structured_budget_echart(rate,vol)
                chart = json.loads(out.getvalue().split('<ECHARTS_DATA>')[1])['structuredBudgetExperiment']
                curve = np.array(chart['series']['New-issue participation'])
                selected = chart['series']['Selected terms'][0]
                terms = v['protected_terms'](rate=rate/100,vol=vol/100)
                self.near(selected,[vol,100*terms['Participation']])
                for scenario,participation in curve:
                    discount = 1/(1+rate/100)
                    option_cost = v['black'](100/discount,100,1,discount,scenario/100)
                    self.near(100*discount+(participation/100)*option_cost,100)
                self.assertTrue(np.all(np.diff(curve[:,1])<=0))
                if rate==0:
                    self.near(curve[:,1],0)
                self.assertEqual(chart['seriesOptions']['Selected terms']['symbol'],'diamond')
        for args in [(-.5,20),(9,20),(5,9),(5,41),(True,20),(5,np.nan),(5,'20')]:
            with self.assertRaises(ValueError):
                pok.show_structured_budget_echart(*args)

    def test_six_copy_parity_and_standalone_serialization(self):
        definitions,outputs = [],[]
        for index,path in enumerate(MODULE_PATHS):
            tree = ast.parse((ROOT/path).read_text())
            definitions.append(ast.dump(next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='show_structured_budget_echart')))
            spec = importlib.util.spec_from_file_location(f'structured_copy_{index}',ROOT/path)
            module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            with contextlib.redirect_stdout(out := io.StringIO()):
                module.show_structured_budget_echart()
            outputs.append(out.getvalue())
        self.assertEqual(len(set(definitions)),1)
        self.assertEqual(len(set(outputs)),1)
        ns = {}
        with contextlib.redirect_stdout(io.StringIO()):
            exec(self.examples['structured-budget-widget'],ns)
        widget = ns['widget_instance']
        try:
            export = next(block for block in re.findall(r'pyodide\.runPython\(`(.*?)`\)',(ROOT/'src/pyodide-worker.js').read_text(),re.S)
                          if 'from ipywidgets.embed import dependency_state' in block)
            exec(export,ns)
            state = json.loads(ns['_widget_json_result'])['state']
            self.assertEqual(state[widget.model_id]['state']['_echarts_callback'],'show_structured_budget_echart')
            self.assertEqual(state[widget.model_id]['state']['_echarts_kwargs'],{'cash_rate_percent':5.,'volatility_percent':20.})
            self.assertEqual({x['state']['_echarts_parameter'] for x in state.values() if x['model_name']=='FloatSliderModel'},
                             {'cash_rate_percent','volatility_percent'})
        finally:
            widget.close()


if __name__=='__main__':
    unittest.main()
