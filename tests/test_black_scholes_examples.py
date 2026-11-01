"""Independent integration, differential, budget, and cross-course convention checks."""
import ast
import contextlib
import importlib.util
import io
import json
import re
import unittest

import numpy as np
import pandas as pd
from scipy.integrate import quad
from scipy.stats import norm
import PortfolioOptimizationKit as pok

from test_return_annualization import ROOT, MODULE_PATHS


class BlackScholesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.markdown = (ROOT / 'docs/black-scholes.md').read_text()
        cls.examples = {editor: code for code, editor in re.findall(
            r'```python:line-numbers\n(.*?)\n```\s*<Editor id="([^"]+)"\s*/>', cls.markdown, re.S)}
        cls.v = {}
        with contextlib.redirect_stdout(output := io.StringIO()):
            for editor, code in cls.examples.items():
                exec(compile(code, editor, 'exec'), cls.v)
        cls.charts = {}
        for line in output.getvalue().splitlines():
            if line.startswith('<ECHARTS_DATA>'):
                cls.charts.update(json.loads(line[len('<ECHARTS_DATA>'):]))

    @classmethod
    def tearDownClass(cls):
        cls.v['widget_instance'].close()

    def test_all_cells_charts_and_units(self):
        ids = re.findall(r'<Editor id="([^"]+)"', self.markdown)
        self.assertEqual(ids, list(self.examples))
        self.assertEqual(len(ids), 11)
        self.assertEqual(len(set(ids)), 11)
        self.assertEqual(len(self.charts), 10)
        for chart in self.charts.values():
            self.assertTrue(chart['xAxis']['name'])
            self.assertTrue(chart['yAxisName'])
            json.dumps(chart, allow_nan=False)
            for series in chart['series'].values():
                self.assertTrue(np.isfinite(series).all())

    def test_prices_against_direct_payoff_integration(self):
        # Integrate the lognormal payoff, not a second implementation of the CDF formula.
        for spot, strike, time, rate, vol in [(100, 100, 1, np.log(1.05), .2),
                (80, 85, .5, np.log(1.05), .3), (120, 90, 2, -.03, .4), (70, 110, .25, 0, .6)]:
            cutoff = (np.log(strike/spot)-(rate-vol**2/2)*time)/(vol*np.sqrt(time))
            terminal = lambda z: spot*np.exp((rate-vol**2/2)*time+vol*np.sqrt(time)*z)
            c = np.exp(-rate*time)*quad(lambda z: (terminal(z)-strike)*norm.pdf(z), cutoff, 12, epsabs=1e-10)[0]
            p = np.exp(-rate*time)*quad(lambda z: (strike-terminal(z))*norm.pdf(z), -12, cutoff, epsabs=1e-10)[0]
            actual = self.v['bs_values'](spot, strike, time, rate, vol)
            np.testing.assert_allclose(actual[:2], [c, p], atol=1e-9)
        self.assertAlmostEqual(self.v['call'], 10.38627949671952)
        self.assertAlmostEqual(self.v['put'], 5.62437473481475)
        self.assertAlmostEqual(self.v['integral_call'], self.v['call'])

    def test_finite_difference_delta_gamma_and_pde(self):
        f = self.v['bs_values']
        for s, k, t, r, vol in [(100, 100, 1, np.log(1.05), .2), (80, 85, .5, -.01, .3), (130, 100, 2, .04, .4)]:
            h, dt = .01, 1e-5
            call, _, delta = f(s, k, t, r, vol)
            up, down = f(s+h, k, t, r, vol)[0], f(s-h, k, t, r, vol)[0]
            delta_fd = (up-down)/(2*h)
            gamma_fd = (up-2*call+down)/h**2
            theta_fd = (f(s, k, t-dt, r, vol)[0]-f(s, k, t+dt, r, vol)[0])/(2*dt)
            self.assertAlmostEqual(delta, delta_fd, places=7)
            self.assertAlmostEqual(theta_fd+.5*vol**2*s**2*gamma_fd+r*s*delta_fd-r*call, 0, places=5)
        self.assertAlmostEqual(sum(self.v['pde_terms']), 0)

    def test_bounds_parity_monotonicity_and_limits(self):
        f = self.v['bs_values']
        for rate in (-.05, 0., np.log(1.05)):
            for time in (0., 1e-8, .5, 2.):
                for vol in (0., 1e-8, .2, .6):
                    previous = None
                    for s in (50., 80., 100., 120., 150.):
                        c, p, d = f(s, 100., time, rate, vol)
                        pv = 100*np.exp(-rate*time)
                        self.assertAlmostEqual(c-p, s-pv)
                        self.assertGreaterEqual(c+1e-12, max(s-pv, 0))
                        self.assertLessEqual(c, s+1e-12)
                        self.assertGreaterEqual(p+1e-12, max(pv-s, 0))
                        self.assertLessEqual(p, pv+1e-12)
                        if previous:
                            self.assertGreaterEqual(c+1e-12, previous[0])
                            self.assertLessEqual(p, previous[1]+1e-12)
                        previous = c, p
                        if time == 0 or vol == 0:
                            np.testing.assert_allclose([c, p], [max(s-pv, 0), max(pv-s, 0)], atol=1e-12)
        self.assertTrue(np.isnan(f(100, 100, 0, .05, .2)[2]))
        np.testing.assert_allclose(self.v['synthetic_profit'], self.v['fair_forward_payoff'], atol=1e-12)
        # Distribution-independent parity agrees with the earlier two-state prices.
        self.assertAlmostEqual(self.v['call']-self.v['put'], 250/21-50/7)
        for bad in [(0, 100, 1, .05, .2), (100, -1, 1, .05, .2), (100, 100, -1, .05, .2),
                    (100, 100, 1, .05, -.2), (100, 100, 1, np.nan, .2)]:
            with self.assertRaises(ValueError):
                f(*bad)

    def test_stock_budget_and_discounted_gains_identity(self):
        v = self.v
        for n, ledger in v['stock_ledgers'].items():
            t, s, q, cash, wealth = [ledger[name].to_numpy() for name in ('Time', 'Spot', 'Units', 'Cash', 'Wealth')]
            np.testing.assert_allclose(q*s+cash, wealth, atol=1e-12)
            np.testing.assert_allclose(ledger['Budget error'], 0, atol=1e-12)
            # Global discounted gains identity follows from self financing, including every rebalance.
            discounted_s = s*np.exp(-v['r']*t)
            reconstructed = v['call']+np.r_[0, np.cumsum(q[:-1]*np.diff(discounted_s))]
            np.testing.assert_allclose(wealth*np.exp(-v['r']*t), reconstructed, atol=3e-11)
            self.assertEqual(q[-1], 0)
            self.assertAlmostEqual(cash[-1], wealth[-1])
            np.testing.assert_allclose(s, v['fine_spots'][::1024//n])
        row = v['hand_ledger'].iloc[1]
        self.assertAlmostEqual(row['Wealth'], v['delta']*105+v['cash']*1.05**.25)
        self.assertGreater(abs(row['Wealth']-row['Call']), .8)  # never silently reset to model value

    def test_futures_discounted_settlements_and_exposure(self):
        v = self.v
        self.assertAlmostEqual(v['delta']*np.exp(-v['r'])*105, v['delta']*100)
        for n, ledger in v['futures_ledgers'].items():
            t, f, q, cash, vm = [ledger[name].to_numpy() for name in ('Time', 'Quote', 'Contracts', 'Cash', 'Variation')]
            np.testing.assert_allclose(vm[1:], q[:-1]*np.diff(f), atol=1e-12)
            reconstructed = v['call']+np.cumsum(vm*np.exp(-v['r']*t))
            np.testing.assert_allclose(cash*np.exp(-v['r']*t), reconstructed, atol=3e-11)
            self.assertEqual(q[-1], 0)
            self.assertAlmostEqual(f[-1], v['fine_spots'][-1])
        # Instantaneous quote exposure h*dF/dS equals stock delta, not h itself.
        self.assertAlmostEqual(v['delta']*np.exp(-v['r'])*np.exp(v['r']), v['delta'])

    def test_zero_volatility_replication_and_zero_rate_hedge_equivalence(self):
        # Run chapter functions in their own copied global namespace to change assumptions safely.
        ns = dict(self.v)
        for editor in ('bs-stock-hedge', 'bs-futures-hedge'):
            tree = ast.parse(self.examples[editor])
            function = next(node for node in tree.body if isinstance(node, ast.FunctionDef))
            exec(compile(ast.Module(body=[function], type_ignores=[]), editor, 'exec'), ns)
        ns['sigma'] = 0.
        dates = np.linspace(0, 1, 17)
        spots = 100*np.exp(ns['r']*dates)
        stock, future = ns['stock_hedge'](spots, dates), ns['futures_hedge'](spots, dates)
        self.assertAlmostEqual(stock['Wealth'].iloc[-1], 5)
        self.assertAlmostEqual(future['Cash'].iloc[-1], 5)
        ns['r'], ns['sigma'] = 0., .2
        spots = self.v['fine_spots'][::64]
        stock, future = ns['stock_hedge'](spots, dates), ns['futures_hedge'](spots, dates)
        np.testing.assert_allclose(stock['Wealth'], future['Cash'], atol=1e-11)

    def test_cross_course_rate_and_return_conventions(self):
        r = self.v['r']
        self.assertAlmostEqual(pok.compounding_rate_inv(.05), r)
        self.assertAlmostEqual(pok.compounding_rate(r), .05)
        liabilities = pd.DataFrame({'Pay': [100.]}, index=[.5])
        self.assertAlmostEqual(pok.present_value(liabilities, .05).iloc[0], 100*np.exp(-r*.5))
        # Exact deterministic GBM and geometric annualization recover e^mu-1, not mu.
        _, logs = pok.simulate_gbm_from_prices(n_years=1, n_scenarios=1, mu=.08, sigma=0,
                                              periods_per_year=12, start=100, seed=42)
        simple = np.expm1(logs.iloc[:, 0])
        self.assertAlmostEqual(pok.annualize_rets(simple, 12), np.expm1(.08))
        self.assertAlmostEqual(simple.mean()*12, 12*np.expm1(.08/12))
        # Return-series Sharpe converts effective cash to period cash; scalar API expects a matched basis.
        returns = pd.Series([.02, -.01, .04, .005])
        cash_m = np.expm1(r/12)
        expected = np.sqrt(12)*(returns-cash_m).mean()/returns.std(ddof=1)
        self.assertAlmostEqual(pok.sharpe_ratio(returns, .05, 12), expected)
        self.assertAlmostEqual(pok.sharpe_ratio(12*returns.mean(), 12*cash_m, 12,
                                              v=pok.annualize_vol(returns, 12)), expected)

    def test_exercise_answers_and_account_units(self):
        v = self.v
        np.testing.assert_allclose([v[k] for k in ('exercise_call', 'exercise_put', 'exercise_delta',
            'exercise_cash', 'exercise_futures', 'exercise_profit')],
            [5.5062464738, 8.4577526744, .4741978040, -32.4295778479, .4627696717, -.6422236520], atol=1e-8)
        self.assertGreater(v['delta']*100/v['call'], 6)
        self.assertAlmostEqual(v['exercise_call']-v['exercise_put'], 80-85/np.sqrt(1.05))

    def test_widget_all_settings_match_visible_formula(self):
        for time in np.arange(0, 2.01, .25):
            for vol in np.linspace(0, .6, 13):
                with contextlib.redirect_stdout(out := io.StringIO()):
                    pok.show_black_scholes_echart(float(time), float(vol))
                chart = json.loads(out.getvalue().split('<ECHARTS_DATA>')[1])['bsLimits']
                series = chart['series']
                calls, puts = np.array(series['Call']), np.array(series['Put'])
                expected = np.array([self.v['bs_values'](s, 100, time, self.v['r'], vol)[:2] for s in calls[:, 0]])
                np.testing.assert_allclose(calls[:, 1], expected[:, 0], atol=1e-12)
                np.testing.assert_allclose(puts[:, 1], expected[:, 1], atol=1e-12)
                np.testing.assert_allclose(series['Call at 100'][0], calls[50])
                np.testing.assert_allclose(series['Put at 100'][0], puts[50])
        for bad in [(-.25, .2), (2.1, .2), (1, -.1), (1, .7), (np.nan, .2)]:
            with self.assertRaises(ValueError):
                pok.show_black_scholes_echart(*bad)

    def test_helper_copies_and_standalone_serialization(self):
        definitions, outputs = [], []
        for index, path in enumerate(MODULE_PATHS):
            tree = ast.parse((ROOT/path).read_text())
            definitions.append(ast.dump(next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                                              and n.name == 'show_black_scholes_echart')))
            spec = importlib.util.spec_from_file_location(f'bs_copy_{index}', ROOT/path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with contextlib.redirect_stdout(out := io.StringIO()):
                module.show_black_scholes_echart()
            outputs.append(out.getvalue())
        self.assertEqual(len(definitions), 6)
        self.assertEqual(len(set(definitions)), 1)
        self.assertEqual(len(set(outputs)), 1)
        ns = {}
        with contextlib.redirect_stdout(io.StringIO()):
            exec(self.examples['bs-limits-widget'], ns)
        widget = ns['widget_instance']
        try:
            export = next(block for block in re.findall(r'pyodide\.runPython\(`(.*?)`\)',
                          (ROOT/'src/pyodide-worker.js').read_text(), re.S)
                          if 'from ipywidgets.embed import dependency_state' in block)
            exec(export, ns)
            state = json.loads(ns['_widget_json_result'])['state']
            self.assertEqual(state[widget.model_id]['state']['_echarts_callback'], 'show_black_scholes_echart')
            self.assertEqual(state[widget.model_id]['state']['_echarts_kwargs'], {'remaining': 1., 'volatility': .2})
            parameters = {item['state']['_echarts_parameter'] for item in state.values()
                          if item['model_name'] == 'FloatSliderModel'}
            self.assertEqual(parameters, {'remaining', 'volatility'})
        finally:
            widget.close()


if __name__ == '__main__':
    unittest.main()
