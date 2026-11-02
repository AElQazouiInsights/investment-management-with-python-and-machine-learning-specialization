"""Independent pricing-measure recovery, density resolution, and tail-identification checks."""
import ast
import contextlib
import importlib.util
import io
import itertools
import json
import re
import unittest

import numpy as np
from scipy.integrate import quad
from scipy.stats import lognorm
import PortfolioOptimizationKit as pok

from test_return_annualization import ROOT, MODULE_PATHS


class ImpliedDistributionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.markdown = (ROOT/'docs/implied-distributions.md').read_text()
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

    def near(self,a,b,atol=1e-9,rtol=1e-6):
        np.testing.assert_allclose(a,b,atol=atol,rtol=rtol)

    def test_cells_units_and_finite_chart_payloads(self):
        self.assertEqual((len(self.examples),len(self.charts)),(9,8))
        self.assertEqual(list(self.examples),re.findall(r'<Editor id="([^"]+)"',self.markdown))
        self.assertNotIn('—',self.markdown)
        for chart in self.charts.values():
            self.assertTrue(chart['xAxis']['name'])
            self.assertTrue(chart['yAxisName'])
            json.dumps(chart,allow_nan=False)
            for data in chart['series'].values():
                self.assertTrue(np.isfinite(data).all())

    def test_digital_ramp_discounting_and_tail_bounds(self):
        v = self.v
        for low,high in ((110,120),(90,120),(95,115),(125,145)):
            payoff = np.clip((v['states']-low)/(high-low),0,1)
            expectation = payoff@v['source_q']
            price = (v['state_calls'](low)-v['state_calls'](high))/(high-low)
            self.near(price,v['D']*expectation)
            self.assertLessEqual(v['source_q'][v['states']>=high].sum(),expectation+1e-12)
            self.assertLessEqual(expectation,v['source_q'][v['states']>low].sum()+1e-12)
        self.near(v['digital_cost'],2/7)
        self.near(v['digital_reading'],.3)

    def test_one_sided_derivatives_respect_atoms(self):
        v = self.v
        for strike in v['states']:
            step = .001
            left = (v['state_calls'](strike-step)-v['state_calls'](strike))/(step*v['D'])
            right = (v['state_calls'](strike)-v['state_calls'](strike+step))/(step*v['D'])
            self.near(left,v['source_q'][v['states']>=strike].sum())
            self.near(right,v['source_q'][v['states']>strike].sum())
        self.near([v['left_tail_105'],v['right_tail_105']],[.7,.3])

    def test_recovery_against_independent_linear_pricing_system(self):
        v = self.v
        # Solve state prices directly from payoff rows and the risk-free unit payment.
        matrix = np.vstack([np.maximum(v['recovered_states'][None,:]-v['strikes'][:,None],0),
                            np.ones(len(v['recovered_states']))])
        target = np.r_[v['calls'],v['D']]
        state_prices = np.linalg.lstsq(matrix,target,rcond=None)[0]
        self.near(state_prices,v['D']*v['recovered_q'])
        self.assertTrue(np.all(v['recovered_q']>=0))
        self.near(v['recovered_q'].sum(),1)
        self.near(v['recovered_states']@v['recovered_q'],105)
        self.near(v['recovered_q'],v['source_q'])

    def test_discrete_boundaries_and_unseen_strike_repricing(self):
        v = self.v
        k = np.linspace(0,250,1001)
        repriced = v['state_calls'](k,v['recovered_states'],v['recovered_q'])
        interpolated = np.interp(k,v['strikes'],v['calls'])
        interpolated[k<25] = v['D']*(105-k[k<25])
        self.near(repriced,interpolated)
        self.near(v['state_calls'](0),100)
        self.near(v['state_calls']([165,185,1000]),0)

    def test_smooth_density_normalization_mean_and_call_integrals(self):
        v = self.v
        law = lognorm(s=.2,scale=105*np.exp(-.02))
        self.near(v['exact_density'](v['density_grid']),law.pdf(v['density_grid']))
        self.near(quad(v['exact_density'],0,np.inf,epsabs=1e-10)[0],1)
        self.near(quad(lambda x:x*v['exact_density'](x),0,np.inf,epsabs=1e-9)[0],105)
        for strike in (65,105,145):
            integral = quad(lambda x:(x-strike)*law.pdf(x),strike,np.inf,epsabs=1e-9)[0]
            self.near(v['smooth_call'](strike),v['D']*integral)
        self.near(v['window_mass'],law.cdf(160)-law.cdf(60),atol=5e-6)
        self.assertLess(v['window_mass'],1)

    def test_butterfly_is_triangular_density_average(self):
        v = self.v
        for strike,gap in ((85,5),(105,1),(105,20),(125,10)):
            integral = quad(lambda x:(gap-abs(x-strike))*v['exact_density'](x),
                            strike-gap,strike+gap,points=[strike],epsabs=1e-11)[0]/gap**2
            self.near(v['butterfly_density'](strike,gap),integral)
        h = .001
        numerical_tail = (v['smooth_call'](110-h)-v['smooth_call'](110+h))/(2*h*v['D'])
        law = lognorm(s=.2,scale=105*np.exp(-.02))
        self.near(numerical_tail,law.sf(110))

    def test_exact_price_refinement_improves_central_density(self):
        v = self.v
        gaps = [20,10,5,1]
        errors = [abs(v['butterfly_density'](105,h)-v['exact_density'](105)) for h in gaps]
        self.assertTrue(np.all(np.diff(errors)<0))
        self.near(v['exact_density'](105),.018902502260810087)
        self.assertLess(errors[-1],4e-6)

    def test_noise_stencil_and_independent_quote_box_extremes(self):
        v = self.v
        delta = v['noisy_readings']-v['clean_readings']
        self.near(delta[18:21],[.03/v['D'],-.06/v['D'],.03/v['D']])
        self.near(delta.sum(),0)
        self.assertLess(v['noisy_readings'].min(),0)
        for gap in (1,5,10):
            quotes = v['smooth_call'](np.array([105-gap,105,105+gap]))
            quotes[1] += .03
            corners = [(quotes+np.array(signs)*.05)@np.array([1,-2,1])/(v['D']*gap**2)
                       for signs in itertools.product((-1,1),repeat=3)]
            middle = v['butterfly_density'](105,gap)-.06/(v['D']*gap**2)
            half_width = 4*.05/(v['D']*gap**2)
            self.near([min(corners),max(corners)],[middle-half_width,middle+half_width])
            self.assertLessEqual(min(corners),v['butterfly_density'](105,gap))
            self.assertGreaterEqual(max(corners),v['butterfly_density'](105,gap))

    def test_distinct_tails_share_all_observed_prices_and_forward(self):
        v = self.v
        strikes = np.linspace(0,125,251)
        self.near(v['state_calls'](strikes),v['state_calls'](strikes,v['alternative_states'],v['alternative_q']))
        self.near(v['alternative_q'].sum(),1)
        self.near(v['alternative_states']@v['alternative_q'],105)
        self.near(v['source_q'][v['states']>150].sum(),.02)
        self.near(v['alternative_q'][v['alternative_states']>150].sum(),.01)
        self.near(v['state_calls'](150),2/7)
        self.near(v['state_calls'](150,v['alternative_states'],v['alternative_q']),1.7047619047619)

    def test_truncation_cannot_be_hidden_by_preserving_conditional_mean(self):
        v = self.v
        self.near(v['exercise_mass'],.2)
        self.near(v['retained_q'].sum(),.8)
        self.near(v['recovered_states']@v['retained_q'],84)
        self.near(v['recovered_states']@v['conditional_q'],105)
        self.near(v['conditional_call'],100/21)
        self.assertGreater(abs(v['conditional_call']-v['state_calls'](105)),3)

    def test_moments_and_tail_sensitivity_against_expanded_samples(self):
        from scipy.stats import skew,kurtosis
        v = self.v
        for name,states,weights in (('Original',v['states'],v['source_q']),('Alternative',v['alternative_states'],v['alternative_q'])):
            sample = np.repeat(states,np.rint(100*weights).astype(int))
            expected = [sample.mean(),sample.var(),sample.std(),skew(sample),kurtosis(sample,fisher=False),kurtosis(sample)]
            self.near(v['moment_table'].loc[name].to_numpy(),expected)
        self.near(v['moment_table'].loc['Original','Variance GBP squared'],560)
        self.near(v['moment_table'].loc['Alternative','Variance GBP squared'],913.6)
        self.assertGreater(v['moment_table'].loc['Alternative','Kurtosis'],30)

    def test_all_110_widget_settings_preserve_negative_readings_and_noise_scaling(self):
        v = self.v
        for gap in range(1,11):
            for bump in np.round(np.linspace(-.05,.05,11),2):
                with contextlib.redirect_stdout(out := io.StringIO()):
                    pok.show_implied_density_echart(gap,bump)
                chart = json.loads(out.getvalue().split('<ECHARTS_DATA>')[1])['densityResolutionExperiment']
                clean = np.array(chart['series']['Clean price differences'])
                changed = np.array(chart['series']['Perturbed mid differences'])
                self.near(clean[:,1],v['butterfly_density'](clean[:,0],gap))
                expected = np.zeros(7);expected[2:5]=[bump,-2*bump,bump]
                self.near(changed[:,1]-clean[:,1],expected/(v['D']*gap**2))
                self.near(chart['series']['Selected central reading'],[changed[3].tolist()])
                if gap==1 and bump==.05:
                    self.assertLess(changed[3,1],0)
                self.assertEqual(chart['seriesOptions']['Selected central reading']['symbol'],'diamond')
        for args in [(0,0),(11,0),(5,-.06),(5,.06),(True,0),(5,np.nan),(5,'0')]:
            with self.assertRaises(ValueError):
                pok.show_implied_density_echart(*args)

    def test_six_copy_parity_and_standalone_serialization(self):
        definitions,outputs = [],[]
        for index,path in enumerate(MODULE_PATHS):
            tree = ast.parse((ROOT/path).read_text())
            definitions.append(ast.dump(next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='show_implied_density_echart')))
            spec = importlib.util.spec_from_file_location(f'density_copy_{index}',ROOT/path)
            module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            with contextlib.redirect_stdout(out := io.StringIO()):
                module.show_implied_density_echart()
            outputs.append(out.getvalue())
        self.assertEqual(len(set(definitions)),1)
        self.assertEqual(len(set(outputs)),1)
        ns = {}
        with contextlib.redirect_stdout(io.StringIO()):
            exec(self.examples['distribution-resolution-widget'],ns)
        widget = ns['widget_instance']
        try:
            export = next(block for block in re.findall(r'pyodide\.runPython\(`(.*?)`\)',(ROOT/'src/pyodide-worker.js').read_text(),re.S)
                          if 'from ipywidgets.embed import dependency_state' in block)
            exec(export,ns)
            state = json.loads(ns['_widget_json_result'])['state']
            self.assertEqual(state[widget.model_id]['state']['_echarts_callback'],'show_implied_density_echart')
            self.assertEqual(state[widget.model_id]['state']['_echarts_kwargs'],{'spacing':5.,'quote_change':.03})
            self.assertEqual({x['state']['_echarts_parameter'] for x in state.values() if x['model_name']=='FloatSliderModel'},
                             {'spacing','quote_change'})
        finally:
            widget.close()


if __name__=='__main__':
    unittest.main()
