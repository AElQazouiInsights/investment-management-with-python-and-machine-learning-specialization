"""Independent price inversion, quote conditioning, calibration, and surface checks."""
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


class ImpliedVolatilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.markdown = (ROOT/'docs/implied-volatility-surfaces.md').read_text()
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

    def near(self,actual,expected,atol=1e-8,rtol=1e-6):
        np.testing.assert_allclose(actual,expected,atol=atol,rtol=rtol)

    def test_cells_finite_charts_and_units(self):
        self.assertEqual(list(self.examples),re.findall(r'<Editor id="([^"]+)"',self.markdown))
        self.assertEqual((len(self.examples),len(self.charts)),(15,16))
        self.assertNotIn('—',self.markdown)
        for chart in self.charts.values():
            self.assertTrue(chart['xAxis']['name'])
            self.assertTrue(chart['yAxisName'])
            json.dumps(chart,allow_nan=False)
            for data in chart['series'].values():
                self.assertTrue(np.isfinite(data).all())

    def test_black_prices_against_payoff_integrals_and_parity(self):
        price = self.v['black_price']
        for f,k,t,d,vol in [(105,100,1,1/1.05,.2),(80,90,.5,1.02,.35),(120,115,2,.9,.4)]:
            scale = vol*np.sqrt(t)
            cut = (np.log(k/f)+.5*scale**2)/scale
            final = lambda z:f*np.exp(-.5*scale**2+scale*z)
            c = d*quad(lambda z:(final(z)-k)*norm.pdf(z),cut,12,epsabs=1e-10)[0]
            p = d*quad(lambda z:(k-final(z))*norm.pdf(z),-12,cut,epsabs=1e-10)[0]
            self.near(price(f,k,t,d,vol),c)
            self.near(price(f,k,t,d,vol,'put'),p)
            self.near(c-p,d*(f-k))
        self.near(price(105,np.array([100,110]),0,1,.2),[5,0])
        self.near(price(105,100,1,.95,0),4.75)

    def test_call_put_iv_recovery_and_expanding_bracket(self):
        v = self.v
        for f,k,t,d in [(105,100,1,v['D0']),(95,100,.5,1.01),(120,110,2,.90)]:
            for vol in (.15,.2,.8,2.5):
                for kind in ('call','put'):
                    premium = v['black_price'](f,k,t,d,vol,kind)
                    recovered = v['implied_vol'](premium,f,k,t,d,kind)
                    self.near(recovered,vol)
                    self.near(v['black_price'](f,k,t,d,recovered,kind),premium)

    def test_inversion_boundaries_invalid_inputs_and_bracket_limit(self):
        v = self.v
        for kind in ('call','put'):
            lower = v['D0']*max(105-100 if kind=='call' else 100-105,0)
            upper = v['D0']*(105 if kind=='call' else 100)
            self.near(v['implied_vol'](lower,105,100,1,v['D0'],kind),0)
            for bad in (lower-.001,upper,upper+.01,np.nan):
                with self.assertRaises(ValueError):
                    v['implied_vol'](bad,105,100,1,v['D0'],kind)
        for args in [(5,105,100,0,1),(5,0,100,1,1),(5,105,0,1,1),(5,105,100,1,0)]:
            with self.assertRaises(ValueError):
                v['implied_vol'](*args)
        huge_vol_price = v['black_price'](100,100,.001,1,20)
        with self.assertRaisesRegex(ValueError,'bracket'):
            v['implied_vol'](huge_vol_price,100,100,.001,1)

    def test_quote_snapshot_validation(self):
        v = self.v
        for field,bad in [('Bid',200),('Ask',0),('Mid',np.nan),('T',0),('F',-1),('D',0),('As of','other time')]:
            frame = v['snapshot'].copy()
            frame.loc[0,field] = bad
            with self.assertRaises(ValueError):
                v['quote_ivs'](frame)
        with self.assertRaises(ValueError):
            v['quote_ivs'](v['snapshot'].iloc[:0])
        for frame in (v['snapshot'],v['held_out'],v['snapshot_b']):
            for side in ('Bid','Mid','Ask'):
                self.near(v['black_price'](frame['F'],frame['K'],frame['T'],frame['D'],frame[side+' IV']),frame[side],atol=1e-9)

    def test_vega_and_inverse_quote_resolution(self):
        v = self.v
        numerical = derivative(lambda vol:v['black_price'](105,100,1,v['D0'],vol),.2,1e-5)
        self.near(v['base_vega'],numerical)
        inverse = derivative(lambda p:v['implied_vol'](p,105,100,1,v['D0']),v['base_premium'],1e-4)
        self.near(inverse,1/v['base_vega'])
        self.near(v['quote_vols'],[.19733973826257,.2,.20265851052318])
        self.assertGreater(v['conditioning'].iloc[-1]['One-penny higher IV %'],37)
        self.assertLess(v['conditioning'].iloc[-1]['Vega GBP/unit vol'],.00002)

    def test_forward_error_chain_rule_with_fixed_premium(self):
        v = self.v
        numerical = derivative(lambda f:v['implied_vol'](v['base_premium'],f,100,1,v['D0']),105,.001)
        self.near(v['iv_forward_slope'],numerical)
        self.near(v['forward_scenarios']['Assumed forward 105'],20)
        self.assertTrue(np.all(v['forward_scenarios']['Assumed forward 103']>20))
        self.assertTrue(np.all(v['forward_scenarios']['Assumed forward 107']<20))

    def test_total_variance_and_hand_weighted_fit(self):
        v = self.v
        self.near(v['variance_slope'],.043)
        self.near(v['hand_shift'],1/15)
        self.near(v['hand_errors'],[-1/75,1/25])
        # Normal equation of the weighted linear model, independent of its displayed solution.
        gradient = 2*np.sum(v['local_vegas']*v['hand_errors']/v['local_widths']**2)
        self.near(gradient,0)
        self.near(v['term_variance'][0],.008875)
        self.near(v['term_variance'][-1],.04)

    def test_surface_mid_and_interval_fit_price_acceptance(self):
        v = self.v
        for fit in v['fits'].values():
            self.assertTrue(fit.success,fit.message)
        mid,interval = v['fits']['Weighted mid'].x,v['fits']['Interval'].x
        self.assertLess(np.max(np.abs(v['mid_residual'](mid))),.31)
        self.near(v['interval_residual'](interval),0,atol=1e-7)
        self.assertGreater(np.linalg.norm(mid-interval),.005)
        self.assertLess(np.sum(v['mid_residual'](mid)**2),np.sum(v['mid_residual'](v['truth'])**2))
        generating = v['surface_prices'](v['truth'],v['snapshot'])
        self.assertTrue(np.all(generating>=v['snapshot']['Bid']))
        self.assertTrue(np.all(generating<=v['snapshot']['Ask']))

    def test_regularization_market_error_is_separate_from_preference(self):
        v = self.v
        fit = v['fits']['Interval + prior']
        prices = v['surface_prices'](fit.x,v['snapshot'])
        outside = np.maximum(v['snapshot']['Bid']-prices,0)+np.maximum(prices-v['snapshot']['Ask'],0)
        market = np.sum((outside/v['widths'])**2)
        penalty = v['prior_weight']*np.sum(((fit.x-v['prior'])/v['parameter_scales'])**2)
        self.near(2*fit.cost,market+penalty)
        self.assertGreater(market,0)
        self.assertGreater(penalty,0)
        self.assertLess(np.linalg.norm((fit.x-v['prior'])/v['parameter_scales']),
                        np.linalg.norm((v['fits']['Interval'].x-v['prior'])/v['parameter_scales']))

    def test_joint_jacobian_against_analytic_price_directions(self):
        v = self.v
        fit = v['joint_fit']; f,d,a,b,c = fit.x
        k = np.log(v['joint_strikes']/f)
        vol = np.sqrt(a+b*k+c*k*k)
        d1 = -k/vol+vol/2
        vega = d*f*norm.pdf(d1)
        price = v['joint_prices'](fit.x)
        analytic = np.column_stack([d*norm.cdf(d1)-vega*(b+2*c*k)/(2*vol*f),price/d,
                                    vega/(2*vol),vega*k/(2*vol),vega*k*k/(2*vol)])
        analytic = analytic/v['joint_widths'][:,None]*v['joint_scales']
        self.near(v['scaled_jacobian'][:5],analytic,atol=1e-4,rtol=1e-4)
        self.assertTrue(fit.success)
        self.assertEqual(np.linalg.matrix_rank(v['scaled_jacobian']),5)
        self.assertLess(v['anchored_singular_values'][0]/v['anchored_singular_values'][-1],50)
        self.assertGreater(v['quote_singular_values'][0]/v['quote_singular_values'][-1],1000)
        self.assertEqual(np.linalg.matrix_rank(v['single_quote_sensitivity']),1)

    def test_held_out_contracts_and_model_choice_remain_separate(self):
        v = self.v
        training = set(zip(v['snapshot']['T'],v['snapshot']['k']))
        testing = set(zip(v['held_out']['T'],v['held_out']['k']))
        self.assertFalse(training & testing)
        self.near(v['chosen_params'],v['fits']['Weighted mid'].x)
        self.assertTrue(np.all(np.abs(v['held_errors'])<1))
        self.assertEqual(set(v['held_out']['T']),{.75})

    def test_strike_constraints_and_executable_butterfly_cashflows(self):
        v = self.v
        self.assertTrue((v['strike_check_table'].iloc[:,1:]>=-1e-9).all().all())
        prices = np.r_[np.linspace(0,200,401),10000.]
        payoff = np.maximum(prices-90,0)-2*np.maximum(prices-100,0)+np.maximum(prices-110,0)
        self.assertGreaterEqual(payoff.min(),0)
        self.near(payoff.max(),10)
        for mids,expected in [(v['small_fault'],.16),(v['large_fault'],-.40)]:
            # Buy the two wing asks, sell twice the central bid.
            cash_cost = mids[0]+.05+mids[2]+.05-2*(mids[1]-.05)
            self.near(cash_cost,expected)
        # Nonuniform strikes use slopes; test independent centered strike curvature.
        f = lambda strike:v['black_price'](105,strike,1,v['D0'],v['surface_vol'](v['chosen_params'],np.log(strike/105),1))
        for strike in (85.,100.,125.):
            self.assertGreater((f(strike+.01)-2*f(strike)+f(strike-.01))/.01**2,0)

    def test_carry_normalized_calendar_consistency(self):
        v = self.v
        self.assertTrue(np.all(v['calendar_increments']>0))
        self.assertTrue(np.all(np.diff(v['normalized_grid'],axis=0)>0))
        for t in (.25,.5,1.):
            f,d = 100*1.05**t,1.05**(-t)
            k = v['audit_k']; vol = v['surface_vol'](v['chosen_params'],k,t)
            raw = v['black_price'](f,f*np.exp(k),t,d,vol)
            self.near(raw/(d*f),v['black_price'](1,np.exp(k),t,1,vol))
        self.assertLess(v['bad_calendar_prices'][1],v['bad_calendar_prices'][0])

    def test_later_snapshot_preserves_contracts_and_ages_expiries(self):
        v = self.v
        self.near(v['snapshot_b']['K'],v['snapshot']['K'])
        self.near(v['snapshot']['T']-v['snapshot_b']['T'],5/(365*24*60))
        self.near(v['snapshot_b']['F']*v['snapshot_b']['D'],101)
        self.assertGreater(np.max(np.abs(v['later_errors'])),1)
        self.near(v['chosen_params'],v['fits']['Weighted mid'].x)
        self.assertEqual(set(v['snapshot_b']['As of']),{'B 09:35'})

    def test_worked_quote_and_multiplier_invariance(self):
        v = self.v
        self.near(v['exercise_ivs']*100,[19.747052075,20.,20.252806884])
        self.near(v['exercise_repricing'],0,atol=1e-9)
        self.near(v['exercise_forward_iv']*100,18.915415085)
        self.near(.1/v['exercise_vega_point'],10/(100*v['exercise_vega_point']))

    def test_all_widget_settings_reprice_selected_quote(self):
        v = self.v
        for forward in np.linspace(103,107,17):
            for change in np.round(np.linspace(-.5,.5,11),1):
                with contextlib.redirect_stdout(out := io.StringIO()):
                    pok.show_implied_volatility_echart(forward,change)
                chart = json.loads(out.getvalue().split('<ECHARTS_DATA>')[1])['ivInputExperiment']
                selected = chart['series']['Selected assumption'][0]
                curve = np.array(chart['series']['Quote-consistent pairs'])
                premium = v['black_price'](105,105,1,v['D0'],.2)+change
                self.near(v['black_price'](selected[0],105,1,v['D0'],selected[1]/100),premium)
                self.near(v['black_price'](curve[:,0],105,1,v['D0'],curve[:,1]/100),premium)
                self.assertTrue(np.all(np.diff(curve[:,1])<0))
                self.assertEqual(chart['seriesOptions']['Selected assumption']['symbol'],'diamond')
        for args in [(102,0),(108,0),(105,-.6),(105,.6),(True,0),(105,np.nan),(105,'0')]:
            with self.assertRaises(ValueError):
                pok.show_implied_volatility_echart(*args)

    def test_six_copy_helper_and_standalone_serialization(self):
        definitions,outputs = [],[]
        for index,path in enumerate(MODULE_PATHS):
            tree = ast.parse((ROOT/path).read_text())
            definitions.append(ast.dump(next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='show_implied_volatility_echart')))
            spec = importlib.util.spec_from_file_location(f'iv_copy_{index}',ROOT/path)
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            with contextlib.redirect_stdout(out := io.StringIO()):
                module.show_implied_volatility_echart()
            outputs.append(out.getvalue())
        self.assertEqual(len(set(definitions)),1)
        self.assertEqual(len(set(outputs)),1)
        ns = {}
        with contextlib.redirect_stdout(io.StringIO()):
            exec(self.examples['iv-input-widget'],ns)
        widget = ns['widget_instance']
        try:
            export = next(block for block in re.findall(r'pyodide\.runPython\(`(.*?)`\)',(ROOT/'src/pyodide-worker.js').read_text(),re.S)
                          if 'from ipywidgets.embed import dependency_state' in block)
            exec(export,ns)
            state = json.loads(ns['_widget_json_result'])['state']
            self.assertEqual(state[widget.model_id]['state']['_echarts_callback'],'show_implied_volatility_echart')
            self.assertEqual(state[widget.model_id]['state']['_echarts_kwargs'],{'assumed_forward':105.,'premium_change':0.})
            self.assertEqual({x['state']['_echarts_parameter'] for x in state.values() if x['model_name']=='FloatSliderModel'},
                             {'assumed_forward','premium_change'})
        finally:
            widget.close()


if __name__ == '__main__':
    unittest.main()
