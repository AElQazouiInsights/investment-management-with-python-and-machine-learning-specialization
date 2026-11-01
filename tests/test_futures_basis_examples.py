"""Independent cash-flow, inverse-pricing, calibration, and widget checks."""
import ast
import contextlib
import importlib.util
import io
import json
import re
import unittest

import numpy as np
from scipy.optimize import least_squares
import PortfolioOptimizationKit as pok

from test_return_annualization import ROOT, MODULE_PATHS


class FuturesBasisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.markdown = (ROOT/'docs/futures-basis.md').read_text()
        cls.examples = dict((editor, code) for code, editor in re.findall(
            r'```python:line-numbers\n(.*?)\n```\s*<Editor id="([^"]+)"\s*/>', cls.markdown, re.S))
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

    def test_cells_chart_units_and_finite_payloads(self):
        self.assertEqual(list(self.examples), re.findall(r'<Editor id="([^"]+)"', self.markdown))
        self.assertEqual(len(self.examples), 13)
        self.assertEqual(len(self.charts), 13)
        for chart in self.charts.values():
            self.assertTrue(chart['xAxis']['name'])
            self.assertTrue(chart.get('yAxisName') or chart['yAxis']['name'])
            json.dumps(chart, allow_nan=False)
            for series in chart['series'].values():
                self.assertTrue(np.isfinite(series).all())

    def test_terminal_replication_and_rate_conventions(self):
        v = self.v
        for final_spot in (1000., 5000., 9000.):
            net = final_spot+(5040-final_spot)+30-5000*np.exp(.01)
            self.assertAlmostEqual(net, v['gross_edge'])
        self.assertAlmostEqual(v['fair_future'], 5020.250835420839)
        self.assertAlmostEqual(pok.compounding_rate(.04), np.expm1(.04))
        self.assertAlmostEqual(v['implied_rate'], pok.compounding_rate_inv((5070/5000)**4-1))

    def test_entitlement_and_payment_date_cash_identity(self):
        v = self.v
        # Reduce debt at payment 0.10, then finance the retained receivable at delivery.
        debt_at_first_payment = 5000*np.exp(.04*.10)-10
        debt_at_expiry = debt_at_first_payment*np.exp(.04*.15)
        receivable_at_expiry = 20/np.exp(.04*.05)
        self.assertAlmostEqual(v['dated_quote'], debt_at_expiry-receivable_at_expiry)
        revised = v['events'].copy()
        revised.loc[1, 'Ex'] = .26
        self.assertAlmostEqual(v['dated_forward'](5000, .25, revised, v['flat_discount']), debt_at_expiry)
        self.assertTrue(np.all(np.diff(v['payment_quotes']) > 0))
        self.assertAlmostEqual(v['dated_forward'](5000, .25, v['events'], lambda t: 1.), 4970)

    def test_executable_thresholds_from_both_terminal_ledgers(self):
        v = self.v
        for final_spot in (3000., 5000., 7000.):
            long_cash = final_spot+v['future_bid']-final_spot+30-v['cash_ask']*np.exp(.04*.25)-1
            short_cash = v['cash_bid']*np.exp(.035*.25)-final_spot+final_spot-v['future_ask']-30-12.5-1
            self.assertAlmostEqual(long_cash, v['future_bid']-v['upper'])
            self.assertAlmostEqual(short_cash, v['lower']-v['future_ask'])
        self.assertLess(v['lower'], v['upper'])
        self.assertFalse(np.any((v['quote_grid']-.5 > v['upper']) & (v['quote_grid']+.5 < v['lower'])))

    def test_margin_budget_global_cashflow_identity_and_timing(self):
        v = self.v
        for key, quantity, rate, fee in [('path_a', 1, .04, 0), ('path_b', 1, .04, 0), ('reverse_ledger', -1, .035, 12.5)]:
            ledger = v[key]
            transfers = np.diff(ledger['Top-ups'], prepend=0)
            np.testing.assert_allclose(ledger['Transfer error'], 0, atol=1e-11)
            np.testing.assert_allclose(ledger.Variation.iloc[1:], -quantity*np.diff(ledger.Future), atol=1e-11)
            # Terminal wealth as independently accumulated dated external cash flows.
            # Margin transfers lose interest while retained in the zero-remuneration account.
            terminal = (-quantity*5000-.5)*np.exp(rate*.25)+250
            terminal += sum(ledger.Variation)+quantity*(5100+30)-fee-.5
            terminal -= np.sum(transfers*np.expm1(rate*(.25-ledger.Time)))
            self.assertAlmostEqual(terminal, ledger.Wealth.iloc[-1])
            np.testing.assert_allclose(ledger.Wealth.iloc[:-1],
                                      ledger.Cash.iloc[:-1]+ledger.Margin.iloc[:-1]+quantity*ledger.Spot.iloc[:-1])
            self.assertEqual(ledger.Margin.iloc[-1], 0)
        a, b = v['path_a'], v['path_b']
        self.assertEqual(a['Top-ups'].max(), 210)
        self.assertEqual(b['Top-ups'].max(), 210)
        expected_gap = 210*(np.exp(.04/6)-np.exp(.04/12))*10
        self.assertAlmostEqual(v['funded_profits']['B']-v['funded_profits']['A'], expected_gap)
        self.assertAlmostEqual(v['funded_profits']['A'], 148.26920670232937)

    def test_zero_rate_paths_and_dividend_stress(self):
        v = self.v
        a = v['carry_ledger']([5000, 5200, 4800, 5100], [5040, 5250, 4850, 5100], financing=0)
        b = v['carry_ledger']([5000, 4800, 5200, 5100], [5040, 4850, 5250, 5100], financing=0)
        self.assertAlmostEqual(a.Wealth.iloc[-1], b.Wealth.iloc[-1])
        self.assertAlmostEqual(a.Wealth.iloc[-1]-250, 5040+30-5000-1)
        self.assertAlmostEqual(v['stress_components'][2], -200)
        self.assertAlmostEqual(sum(v['stress_components'][:3]), v['joint_profit'])
        self.assertLess(v['joint_profit'], 0)

    def test_implied_roots_and_invalid_observations(self):
        v = self.v
        self.assertAlmostEqual(v['root_rate'], v['implied_rate'])
        self.assertAlmostEqual(v['dated_recovered_rate'], .04)
        self.assertLess(v['implied_bid'], v['implied_rate'])
        self.assertLess(v['implied_rate'], v['implied_ask'])
        f = v['implied_dated_rate']
        for rate in (-.02, 0., .08):
            price = v['dated_forward'](5000, .25, v['events'], lambda t: np.exp(-rate*t))
            self.assertAlmostEqual(f(5000, .25, v['events'], price, price), rate)
        for s, t, bid, ask in [(5000, 0, 5040, 5040), (0, .25, 5040, 5040),
                               (5000, .25, 5041, 5040), (5000, .25, np.nan, 5040),
                               (5000, .25, 10000, 10001)]:
            with self.assertRaises(ValueError):
                f(s, t, v['events'], bid, ask)

    def test_independent_curve_bootstrap_and_held_out_fit(self):
        v = self.v
        # Bootstrap from reinvested dividend PV, without using the interval helper.
        discount, prior_pv = [], 0.
        for price, dividend in zip(v['true_quotes'][:3], [30, 45, 20]):
            p = (5000-prior_pv)/(price+dividend)
            discount.append(p)
            prior_pv += dividend*p
        np.testing.assert_allclose(-np.diff(np.log([1., *discount]))/.25, [.04, .045, .05], atol=1e-12)
        clean = least_squares(lambda f: v['curve_quotes'](f)[:4]-v['true_quotes'][:4], [.03]*3,
                              xtol=1e-13, ftol=1e-13, gtol=1e-10)
        np.testing.assert_allclose(clean.x, v['true_forwards'], atol=1e-10)
        self.assertEqual(np.linalg.matrix_rank(v['plain_fit'].jac[:4]), 3)
        for fit in (v['plain_fit'], v['smooth_fit']):
            self.assertTrue(fit.success)
            self.assertTrue(np.all(abs(v['curve_quotes'](fit.x)-v['quote_mids']) < v['half_spreads']))
        self.assertAlmostEqual(v['curve_discount'](0, [-.01]*3), 1)
        self.assertGreater(v['curve_discount'](1, [-.01]*3), 1)

    def test_dividend_rank_recovery_and_nonidentification(self):
        v = self.v
        matrix = v['dividend_matrix']
        recovered = np.linalg.lstsq(matrix[:4], 5000/v['discounts'][:4]-v['true_quotes'][:4], rcond=None)[0]
        np.testing.assert_allclose(recovered, [30, 45, 20], atol=1e-9)
        self.assertEqual(np.linalg.matrix_rank(matrix[:2]), 2)
        np.testing.assert_array_equal(matrix[:2, 2], 0)
        self.assertLess(max(abs(v['dividend_reprices']-v['quote_mids'])), .13)
        np.testing.assert_allclose(v['snapshot_dividends_fixed_rate'], [30, 25])
        self.assertGreater(v['snapshot_rates'][1], v['snapshot_rates'][0])

    def test_parity_two_strike_extraction_and_contamination(self):
        v = self.v
        y = v['calls']-v['puts']
        discount = (y[1]-y[3])/200
        forward = 4900+y[1]/discount
        self.assertAlmostEqual(discount, np.exp(-.01))
        self.assertAlmostEqual(forward, v['fair_future'])
        self.assertAlmostEqual(v['clean_discount'], discount)
        self.assertAlmostEqual(v['clean_forward'], forward)
        self.assertGreater(max(abs(v['bad_residuals'])), 1)
        with self.assertRaises(ValueError):
            v['fit_parity'](v['strikes'])

    def test_calendar_attribution_and_sensitivity_units(self):
        v = self.v
        self.assertEqual(v['direct_calendar_pnl'], -20)
        self.assertEqual(v['model_contribution']+v['residual_contribution'], -20)
        self.assertAlmostEqual(v['neutral_near_quantity']*np.exp(.04*.25)-np.exp(.04*.5), 0)
        finite_difference = (5000*np.exp((.04+1e-6)*.25)-5000*np.exp((.04-1e-6)*.25))/2e-6
        self.assertAlmostEqual(v['rate_sensitivity'], finite_difference, places=5)
        self.assertLess(abs(v['one_bp_repricing']-v['rate_sensitivity']*.0001), .000002)

    def test_exercise_results(self):
        v = self.v
        self.assertAlmostEqual(v['exercise_fair'], 4060.805360107)
        self.assertAlmostEqual(v['exercise_rate'], .04938522518)
        self.assertAlmostEqual(v['exercise_implied_dividend'], .805360107)

    def test_widget_all_settings_reprice_fixed_quote(self):
        for rate in np.arange(4, 8.01, .25):
            with contextlib.redirect_stdout(out := io.StringIO()):
                pok.show_basis_identification_echart(float(rate))
            chart = json.loads(out.getvalue().split('<ECHARTS_DATA>')[1])['basisIdentification']
            for r, d in chart['series']['Compatible pairs']+chart['series']['Selected assumption']:
                self.assertAlmostEqual((5040+d)/5000, np.exp(r/100*.25))
            self.assertEqual(chart['series']['Selected assumption'][0][0], rate)
        for bad in (True, 3.99, 8.01, np.nan, np.inf, '5'):
            with self.assertRaises(ValueError):
                pok.show_basis_identification_echart(bad)

    def test_helper_copies_and_independent_widget_export(self):
        definitions, outputs = [], []
        for index, path in enumerate(MODULE_PATHS):
            tree = ast.parse((ROOT/path).read_text())
            definitions.append(ast.dump(next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                                              and n.name == 'show_basis_identification_echart')))
            spec = importlib.util.spec_from_file_location(f'basis_copy_{index}', ROOT/path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with contextlib.redirect_stdout(out := io.StringIO()):
                module.show_basis_identification_echart()
            outputs.append(out.getvalue())
        self.assertEqual(len(definitions), 6)
        self.assertEqual(len(set(definitions)), 1)
        self.assertEqual(len(set(outputs)), 1)
        ns = {}
        with contextlib.redirect_stdout(io.StringIO()):
            exec(self.examples['basis-identification-widget'], ns)
        widget = ns['widget_instance']
        try:
            export = next(block for block in re.findall(r'pyodide\.runPython\(`(.*?)`\)',
                          (ROOT/'src/pyodide-worker.js').read_text(), re.S)
                          if 'from ipywidgets.embed import dependency_state' in block)
            exec(export, ns)
            state = json.loads(ns['_widget_json_result'])['state']
            self.assertEqual(state[widget.model_id]['state']['_echarts_callback'], 'show_basis_identification_echart')
            self.assertEqual(state[widget.model_id]['state']['_echarts_kwargs'], {'financing_percent': 5.})
        finally:
            widget.close()


if __name__ == '__main__':
    unittest.main()
