"""Verify the lesson's signed cash accounts, pricing identities, and expiry scenarios."""
import ast
import contextlib
from fractions import Fraction
import importlib.util
import io
import json
import re
import unittest

import numpy as np
import PortfolioOptimizationKit as pok

from test_return_annualization import ROOT, MODULE_PATHS


class OptionExampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.markdown = (ROOT / 'docs/d.3-options.md').read_text()
        cls.examples = dict((editor, code) for code, editor in re.findall(
            r'```python:line-numbers\n(.*?)\n```\s*<Editor id="([^"]+)"\s*/>', cls.markdown, re.S))
        cls.values, output = {}, io.StringIO()
        with contextlib.redirect_stdout(output):
            for editor, code in cls.examples.items():
                exec(compile(code, editor, 'exec'), cls.values)
        cls.charts = {}
        for line in output.getvalue().splitlines():
            if line.startswith('<ECHARTS_DATA>'):
                cls.charts.update(json.loads(line[len('<ECHARTS_DATA>'):]))

    @classmethod
    def tearDownClass(cls):
        cls.values['widget_instance'].close()

    def test_every_example_executes_and_charts_are_finite(self):
        ids = re.findall(r'<Editor id="([^"]+)"', self.markdown)
        self.assertEqual(ids, list(self.examples))
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 10)
        self.assertEqual(self.markdown.count('```python'), 10)
        self.assertEqual(len(self.charts), 11)
        for chart in self.charts.values():
            self.assertIn('GBP', chart['yAxisName'])
            json.dumps(chart, allow_nan=False)
            for data in chart['series'].values():
                self.assertTrue(np.isfinite(data).all())

    def test_payoff_kinks_and_signed_writer_obligations(self):
        v = self.values
        expected = [[80, 0, 20, 0, -20], [100, 0, 0, 0, 0], [120, 20, 0, -20, 0]]
        np.testing.assert_allclose(v['payoff_table'], expected)
        for name, long in [('Call', v['call_payoff']), ('Put', v['put_payoff'])]:
            holder = self.charts['optionsPayoffHolder']['series'][name]
            writer = self.charts['optionsPayoffWriter']['series'][name]
            np.testing.assert_allclose(np.array(holder)[:, 0], v['final_prices'])
            np.testing.assert_allclose(np.array(holder)[:, 1], long)
            np.testing.assert_allclose(np.array(writer)[:, 1], -long)
        np.testing.assert_allclose(np.diff(v['call_payoff'])[:100], 0)
        np.testing.assert_allclose(np.diff(v['call_payoff'])[100:], 1)
        np.testing.assert_allclose(np.diff(v['put_payoff'])[:100], -1)
        np.testing.assert_allclose(np.diff(v['put_payoff'])[100:], 0)

    def test_financed_profit_break_even_and_limits(self):
        v = self.values
        self.assertAlmostEqual(v['call_cost_at_expiry'], 12.5)
        self.assertAlmostEqual(v['put_cost_at_expiry'], 7.5)
        for index, expected_call, expected_put in [(0, -12.5, 92.5), (80, -12.5, 12.5),
                                                    (100, -12.5, -7.5), (110, -2.5, -7.5), (120, 7.5, -7.5)]:
            self.assertAlmostEqual(v['call_profit'][index], expected_call)
            self.assertAlmostEqual(v['put_profit'][index], expected_put)
        for name, values in [('Call', v['call_profit']), ('Put', v['put_profit'])]:
            np.testing.assert_allclose(np.array(self.charts['optionsProfitHolder']['series'][name])[:, 1], values)
            np.testing.assert_allclose(np.array(self.charts['optionsProfitWriter']['series'][name])[:, 1], -values)
        self.assertAlmostEqual(112.5 - 100 - v['call_cost_at_expiry'], 0)
        self.assertAlmostEqual(100 - 92.5 - v['put_cost_at_expiry'], 0)
        self.assertGreater(20 - v['call_premium'], v['call_profit'][120])

    def test_replication_values_and_net_initial_cash_funding(self):
        v = self.values
        # Exact rational answers, including the cash sign, independently of numpy arithmetic.
        for name, delta, cash, price, payments in [
            ('call', Fraction(1, 2), Fraction(-800, 21), Fraction(250, 21), [0, 20]),
            ('put', Fraction(-1, 2), Fraction(400, 7), Fraction(50, 7), [20, 0]),
        ]:
            self.assertAlmostEqual(v[name + '_delta'], float(delta))
            self.assertAlmostEqual(v[name + '_cash_today'], float(cash))
            self.assertAlmostEqual(v['replicated_' + name + '_price'], float(price))
            self.assertAlmostEqual(v[name + '_premium'], float(price))
            # At entry: premium supplied - asset bought - cash deposited = 0.
            self.assertAlmostEqual(float(price) - v[name + '_delta'] * 100 - v[name + '_cash_today'], 0)
            np.testing.assert_allclose(v[name + '_replication'], payments, atol=1e-12)
            chart = self.charts['options' + name.title() + 'Replication']['series']
            np.testing.assert_allclose(chart['Net portfolio'], payments, atol=1e-12)
            np.testing.assert_allclose(chart[name.title() + ' payoff'], payments)
        # Outside the two-state model, the static call hedge does not reproduce its kink.
        self.assertAlmostEqual(v['call_delta'] * 100 + v['call_cash_today'] * v['growth'], 10)
        self.assertEqual(v['call_payoff'][100], 0)
        surplus = 13 - v['replicated_call_price']
        np.testing.assert_allclose(v['call_replication'] - v['call_states'] + surplus * v['growth'], 1.15)

    def test_pricing_weight_versus_real_probability_and_bounds(self):
        v = self.values
        self.assertEqual(v['pricing_weight'], .625)
        self.assertLess(80, 100 * v['growth'])
        self.assertLess(100 * v['growth'], 120)
        self.assertAlmostEqual(v['weighted_call_price'], float(Fraction(250, 21)))
        self.assertAlmostEqual(v['weighted_put_price'], float(Fraction(50, 7)))
        self.assertAlmostEqual(v['expected_call_profit'][50], -2.5)
        self.assertAlmostEqual(v['expected_call_profit'][80], 3.5)
        chart = np.array(self.charts['optionsForecastProfit']['series']['Expected profit'])
        np.testing.assert_allclose(chart[:, 0], 100 * v['real_up_probabilities'])
        np.testing.assert_allclose(chart[:, 1], v['expected_call_profit'])
        np.testing.assert_allclose(v['bound_table'], [[100/21, 250/21, 100], [0, 50/7, 2000/21]])
        # The £3 quote violates the lower bound; the proposed trades leave no future liability.
        self.assertAlmostEqual(100 - 3 - v['strike_present_value'], 37/21)
        self.assertTrue((v['call_payoff'] + 100 - v['final_prices'] >= 0).all())

    def test_all_price_parity_and_funded_synthetic_forward(self):
        v = self.values
        np.testing.assert_allclose(v['package_a'], v['package_b'])
        np.testing.assert_allclose(v['synthetic_forward'], v['final_prices'] - 100)
        initial_difference = v['call_premium'] - v['put_premium']
        self.assertAlmostEqual(initial_difference, 100/21)
        np.testing.assert_allclose(v['synthetic_forward'] - initial_difference * v['growth'], v['final_prices'] - 105)
        for name in ('optionsParityPackages', 'optionsSyntheticForward'):
            series = list(self.charts[name]['series'].values())
            np.testing.assert_allclose(series[0], series[1])

    def test_changed_strike_exercise_and_changed_up_state(self):
        v = self.values
        np.testing.assert_allclose(v['exercise_results'], [
            [0, 10, .25, -400/21, 125/21, 116.25],
            [30, 0, -.75, 600/7, 75/7, 98.75],
        ])
        self.assertAlmostEqual(v['exercise_call'] - v['exercise_put'], -100/21)
        altered = dict(v)
        with contextlib.redirect_stdout(io.StringIO()):
            exec(self.examples['options-call-replication'].replace('[80., 120.]', '[80., 140.]'), altered)
        self.assertAlmostEqual(altered['call_delta'], 2/3)
        self.assertAlmostEqual(altered['call_cash_today'], -3200/63)
        self.assertAlmostEqual(altered['replicated_call_price'], 1000/63)
        np.testing.assert_allclose(altered['call_replication'], [0, 40], atol=1e-12)

    def test_widget_all_81_settings_payoffs_and_fixed_premium_gaps(self):
        for spot in np.arange(0, 200.1, 2.5):
            with contextlib.redirect_stdout(output := io.StringIO()):
                pok.show_option_payoff_echart(spot)
            text, raw = output.getvalue().split('<ECHARTS_DATA>')
            charts = json.loads(raw)
            self.assertIn(f'Final asset price: {spot:.2f} GBP/unit', text)
            for name, sign, cost in [('Call', 1, 12.5), ('Put', -1, 7.5)]:
                series = charts['option' + name + 'Experiment']['series']
                payment = max(sign * (spot - 100), 0)
                np.testing.assert_allclose(series['Selected payoff'], [[spot, payment]])
                np.testing.assert_allclose(series['Selected profit'], [[spot, payment - cost]], atol=1e-12)
                points = np.array(series['Payoff'])
                profits = np.array(series['Financed profit'])
                np.testing.assert_allclose(points[:, 1] - profits[:, 1], cost)
                np.testing.assert_allclose(points[:, 1], self.values[name.lower() + '_payoff'])
                self.assertIn(f'{name} positive exercise benefit: {"yes" if payment > 0 else "no"}', text)

    def test_widget_invalid_inputs(self):
        for spot in (-1, 201, np.nan, np.inf, True, None, '100'):
            with self.subTest(spot=spot), self.assertRaises(ValueError):
                pok.show_option_payoff_echart(spot)

    def test_six_helper_copies_match_and_execute(self):
        definitions, outputs = [], []
        for index, path in enumerate(MODULE_PATHS):
            nodes = ast.parse((ROOT / path).read_text()).body
            definitions.append(ast.dump(next(node for node in nodes if isinstance(node, ast.FunctionDef)
                                              and node.name == 'show_option_payoff_echart')))
            spec = importlib.util.spec_from_file_location(f'option_copy_{index}', ROOT / path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with contextlib.redirect_stdout(output := io.StringIO()):
                module.show_option_payoff_echart(92.5)
            outputs.append(output.getvalue())
        self.assertEqual(len(definitions), 6)
        self.assertEqual(len(set(definitions)), 1)
        self.assertEqual(len(set(outputs)), 1)

    def test_widget_standalone_and_float_callback_metadata(self):
        namespace = {}
        with contextlib.redirect_stdout(io.StringIO()):
            exec(self.examples['options-payoff-widget'], namespace)
        widget = namespace['widget_instance']
        try:
            export = next(block for block in re.findall(r'pyodide\.runPython\(`(.*?)`\)',
                          (ROOT / 'src/pyodide-worker.js').read_text(), re.S)
                          if 'from ipywidgets.embed import dependency_state' in block)
            exec(export, namespace)
            state = json.loads(namespace['_widget_json_result'])['state']
            box = state[widget.model_id]['state']
            self.assertEqual(box['_echarts_callback'], 'show_option_payoff_echart')
            self.assertEqual(box['_echarts_kwargs'], {'final_spot': 120.})
            slider = next(item['state'] for item in state.values() if item['model_name'] == 'FloatSliderModel')
            self.assertEqual(slider['step'], 2.5)
            self.assertEqual(slider['_echarts_parameter'], 'final_spot')
        finally:
            widget.close()


if __name__ == '__main__':
    unittest.main()
