"""Worked forward answers, dated cash flows, chart parity, and widget routing."""
import ast
import contextlib
from decimal import Decimal
import importlib.util
import io
import json
import re
import unittest

import numpy as np
import PortfolioOptimizationKit as pok

from test_return_annualization import ROOT, MODULE_PATHS


class ForwardExampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.markdown = (ROOT / 'docs/d.1-forwards.md').read_text()
        cls.examples = {editor: code for code, editor in re.findall(
            r'```python:line-numbers\n(.*?)\n```\s*<Editor id="([^"]+)"\s*/>', cls.markdown, re.S)}
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

    def test_every_cell_and_chart_executes_in_document_order(self):
        ids = re.findall(r'<Editor id="([^"]+)"', self.markdown)
        self.assertEqual(ids, list(self.examples))
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 8)
        self.assertEqual(self.markdown.count('```python'), 8)
        self.assertEqual(len(self.charts), 6)

    def test_obligations_signs_quantity_and_break_even(self):
        v = self.values
        np.testing.assert_allclose(v['long_payoffs'], [-250, -50, 0, 150, 350])
        np.testing.assert_allclose(v['long_payoffs'] + v['short_payoffs'], 0)
        physical_delivery_value = v['quantity'] * v['terminal_spots'] - 1050
        np.testing.assert_allclose(v['long_payoffs'], physical_delivery_value)

    def test_financing_and_both_arbitrage_ledgers(self):
        v = self.values
        self.assertAlmostEqual(v['fair_delivery'], 105)
        np.testing.assert_allclose(v['financing_table']['Cash flow per unit (GBP)'], [100, -100, -105])
        np.testing.assert_allclose(v['arbitrage_cashflows'].iloc[:2].sum(), [0, 0])
        np.testing.assert_allclose(v['arbitrage_cashflows'].iloc[2:].sum(), [5, 5])
        # Two annual repayments: 100 principal + 5 first-year interest + 5.25 second-year interest.
        index = np.flatnonzero(np.isclose(v['maturities'], 2))[0]
        self.assertAlmostEqual(v['new_forward_quotes'][index], 110.25)

    def test_existing_value_matches_offsetting_terminal_cashflows(self):
        v = self.values
        factor = Decimal('1.05').sqrt()
        expected_quote = float(Decimal(110) * factor)
        expected_value = float(Decimal(10) * (Decimal(110) - Decimal(105) / factor))
        self.assertAlmostEqual(v['replacement_quote'], expected_quote)
        self.assertAlmostEqual(v['contract_value'], expected_value)
        # A replacement short offsets every possible maturity spot, not only the review spot.
        replacement_short = v['quantity'] * (v['replacement_quote'] - v['terminal_spots'])
        locked = v['long_payoffs'] + replacement_short
        np.testing.assert_allclose(locked, v['locked_terminal_difference'])
        np.testing.assert_allclose(locked * v['discount_factor'], v['contract_value'])
        self.assertEqual(v['delivery_price'], 105)
        self.assertGreater(v['locked_terminal_difference'], v['contract_value'])

    def test_hedge_reconciles_purchase_and_negative_forward_receipts(self):
        v = self.values
        np.testing.assert_allclose(v['market_purchase_costs'], [800, 1000, 1050, 1200, 1400])
        np.testing.assert_allclose(v['net_purchase_costs'], 1050)
        self.assertEqual(v['net_purchase_costs'][0], 800 + 250)
        self.assertEqual(v['net_purchase_costs'][3], 1200 - 150)
        self.assertAlmostEqual(v['exercise_delivery'], 135.2)
        self.assertAlmostEqual(v['exercise_review_value'], 40)
        self.assertAlmostEqual(v['exercise_payoff'], -60.8)

    def test_chart_curves_reconcile_to_tables_units_and_dates(self):
        v, charts = self.values, self.charts
        payoff = charts['forwardPayoffs']
        for name, column in [('Long', 'Long payoff (GBP)'), ('Short', 'Short payoff (GBP)')]:
            curve = dict(payoff['series'][name])
            np.testing.assert_allclose([curve[x] for x in v['terminal_spots']], v['payoff_table'][column])
        self.assertEqual(payoff['xAxis']['name'], 'Maturity spot (GBP/unit)')
        review = charts['forwardReview']
        self.assertEqual(review['xAxis']['name'], 'Current spot (GBP/unit)')
        self.assertIn('today', review['yAxisName'])
        line = np.array(review['series']['Existing long'])
        np.testing.assert_allclose(line[:, 1], v['review_values'])
        self.assertAlmostEqual(dict(review['series']['Existing long'])[110], v['contract_value'])
        hedge = charts['forwardHedge']['series']
        np.testing.assert_allclose(np.array(hedge['Purchase plus long forward'])[:, 1], 1050)
        np.testing.assert_allclose(np.array(hedge['Market purchase alone'])[:, 1], 10 * v['payoff_grid'])
        self.assertEqual(dict(charts['forwardArbitrage']['series']['Buy asset; sell forward'])[110], 5)
        self.assertEqual(dict(charts['forwardArbitrage']['series']['Sell asset; buy forward'])[100], 5)
        np.testing.assert_allclose(np.array(charts['forwardMaturities']['series']['Financed purchase'])[:, 1], v['new_forward_quotes'])
        for chart in charts.values():
            self.assertIn('GBP', chart['yAxisName'])
            self.assertNotIn('%', chart['yAxisName'])

    def test_widget_standalone_fixed_terms_and_linear_changes(self):
        output, namespace = io.StringIO(), {}
        with contextlib.redirect_stdout(output):
            exec(self.examples['forward-value-widget'], namespace)
        namespace['widget_instance'].close()
        self.assertIn('Current spot: 110.00', output.getvalue())
        base_value = self.values['contract_value']
        for spot in (60, 100, 110, 115, 150, float(Decimal(105) / Decimal('1.05').sqrt())):
            with contextlib.redirect_stdout(output := io.StringIO()):
                pok.show_forward_value_echart(spot)
            text = output.getvalue()
            chart = json.loads(text.split('<ECHARTS_DATA>')[1])['forwardValueExperiment']
            selected = chart['series']['Selected spot'][0]
            self.assertEqual(selected[0], spot)
            self.assertAlmostEqual(selected[1], base_value + 10 * (spot - 110))
            self.assertIn('Existing delivery price: 105.00 GBP/unit', text)
            self.assertIn('Remaining term: 0.50 years', text)
            grid = np.array(chart['series']['Existing long'])
            np.testing.assert_allclose(np.diff(grid[:, 1]), 10 * np.diff(grid[:, 0]))

    def test_widget_rejects_invalid_spots(self):
        for spot in (-1, 0, np.nan, np.inf, True, np.bool_(False), '110', None, [110]):
            with self.subTest(spot=spot), self.assertRaises(ValueError):
                pok.show_forward_value_echart(spot)

    def test_published_copies_match_and_execute(self):
        definitions, payloads = [], []
        for i, path in enumerate(MODULE_PATHS):
            node = next(n for n in ast.parse((ROOT / path).read_text()).body
                        if isinstance(n, ast.FunctionDef) and n.name == 'show_forward_value_echart')
            definitions.append(ast.dump(node))
            spec = importlib.util.spec_from_file_location(f'forward_copy_{i}', ROOT / path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with contextlib.redirect_stdout(output := io.StringIO()):
                module.show_forward_value_echart(60)
            payloads.append(output.getvalue())
        self.assertEqual(len(set(definitions)), 1)
        self.assertEqual(len(set(payloads)), 1)

    def test_worker_exports_real_callback_and_spot_keyword(self):
        source = (ROOT / 'src/pyodide-worker.js').read_text()
        export = next(block for block in re.findall(r'pyodide\.runPython\(`(.*?)`\)', source, re.S)
                      if 'from ipywidgets.embed import dependency_state' in block)
        box = self.values['widget_instance']
        namespace = {'widget_instance': box}
        exec(export, namespace)
        state = json.loads(namespace['_widget_json_result'])['state'][box.model_id]['state']
        self.assertEqual(state['_echarts_callback'], 'show_forward_value_echart')
        self.assertEqual(state['_echarts_kwargs'], {'spot': 110})


if __name__ == '__main__':
    unittest.main()
