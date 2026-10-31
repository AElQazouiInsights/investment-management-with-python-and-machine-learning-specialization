"""Independent margin ledgers, dated funding, deterministic replication, and charts."""
import ast
import contextlib
from decimal import Decimal
import importlib.util
import io
import json
import re
import unittest

import numpy as np
import pandas as pd
import PortfolioOptimizationKit as pok

from test_return_annualization import ROOT, MODULE_PATHS


class FuturesExampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.markdown = (ROOT / 'docs/d.2-futures.md').read_text()
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

    def test_all_examples_execute_and_calendar_is_explicit(self):
        ids = re.findall(r'<Editor id="([^"]+)"', self.markdown)
        self.assertEqual(ids, list(self.examples))
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 9)
        self.assertEqual(self.markdown.count('```python'), 9)
        self.assertEqual(len(self.charts), 8)
        v = self.values
        self.assertEqual(len(v['days']), 366)
        np.testing.assert_array_equal(v['days'], np.arange(366))
        np.testing.assert_allclose(v['variation_a'][:362], 0)
        np.testing.assert_allclose(v['variation_a'][-4:], [-50, -20, 140, 80])
        np.testing.assert_allclose(v['cumulative_variation'][-5:], [0, -50, -70, 70, 150])
        self.assertEqual(np.count_nonzero(v['forward_cash']), 1)
        self.assertEqual(v['forward_cash'][-1], 150)

    def test_worked_margin_cash_flows_and_exercise(self):
        a = self.values['margin_a'].loc[[0, 361, 362, 363, 364, 365]]
        expected = {
            'Before funding/close (GBP)': [0, 100, 50, 80, 220, 300],
            'Deposit (GBP)': [100, 0, 50, 0, 0, 0],
            'Close-out transfer (GBP)': [0, 0, 0, 0, 0, 300],
            'Closing balance (GBP)': [100, 100, 100, 80, 220, 0],
            'Outside cash flow (GBP)': [-100, 0, -50, 0, 0, 300],
        }
        for column, values in expected.items():
            np.testing.assert_allclose(a[column], values)
        exercise = self.values['exercise_ledger']
        np.testing.assert_allclose(exercise['Variation (GBP)'], [0, -30, -10, 70])
        np.testing.assert_allclose(exercise['Deposit (GBP)'], [100, 30, 0, 0])
        np.testing.assert_allclose(exercise['Close-out transfer (GBP)'], [0, 0, 0, 160])
        self.assertEqual(self.values['exercise_gain'], 30)

    def test_account_cash_conservation_for_long_short_and_negative_quotes(self):
        for prices in ([105, 102, 101, 108], [20, -10, -30, 5], [100, 100, 100], [100, 90]):
            for quantity in (10, -10, 2.5):
                ledger = pok.futures_margin_ledger(prices, quantity)
                previous = ledger['Closing balance (GBP)'].shift(fill_value=0)
                np.testing.assert_allclose(previous + ledger['Variation (GBP)'],
                                           ledger['Closing balance (GBP)'] + ledger['Outside cash flow (GBP)'])
                self.assertAlmostEqual(ledger['Outside cash flow (GBP)'].sum(), quantity * (prices[-1] - prices[0]))
                self.assertEqual(ledger['Closing balance (GBP)'].iloc[-1], 0)
                self.assertTrue((ledger['Deposit (GBP)'] >= 0).all())

    def test_exact_maintenance_boundary_and_final_debit(self):
        at_boundary = pok.futures_margin_ledger([105, 102.5, 110])
        below = pok.futures_margin_ledger([105, 102.4, 110])
        self.assertEqual(at_boundary['Before funding/close (GBP)'].iloc[1], 75)
        self.assertEqual(at_boundary['Deposit (GBP)'].iloc[1], 0)
        self.assertAlmostEqual(below['Deposit (GBP)'].iloc[1], 26)
        final_loss = pok.futures_margin_ledger([100, 90], initial_margin=50, maintenance_margin=25)
        np.testing.assert_allclose(final_loss['Deposit (GBP)'], [50, 0])
        np.testing.assert_allclose(final_loss['Close-out transfer (GBP)'], [0, -50])
        np.testing.assert_allclose(final_loss['Outside cash flow (GBP)'], [-50, -50])
        self.assertEqual(final_loss['Closing balance (GBP)'].iloc[-1], 0)

    def test_visible_ledger_and_toolkit_agree_across_rules_and_scale(self):
        visible = self.values['margin_ledger']
        for prices in ([105., 100., 98., 112., 120.], [105., 102.5, 101., 108.], [100., 90.]):
            for quantity, initial, maintenance in ((10, 100, 75), (-10, 100, 75), (2.5, 30, 30)):
                pd.testing.assert_frame_equal(visible(prices, quantity, initial, maintenance),
                                              pok.futures_margin_ledger(prices, quantity, initial, maintenance))
        base = pok.futures_margin_ledger([105, 100, 98, 120])
        scaled = pok.futures_margin_ledger([105, 100, 98, 120], quantity=30, initial_margin=300, maintenance_margin=225)
        np.testing.assert_allclose(scaled.iloc[:, 1:], 3 * base.iloc[:, 1:])

    def test_funding_dates_match_recursive_cash_account(self):
        v = self.values
        expected_a = float(Decimal(300) - Decimal(100) * Decimal('1.05')
                           - Decimal(50) * Decimal('1.05') ** (Decimal(3) / Decimal(365)))
        self.assertAlmostEqual(v['funded_gains']['A: fall then recover'], expected_a)
        self.assertAlmostEqual(v['funded_gains']['B: steady rise'], 145)
        self.assertAlmostEqual(v['funded_gains']['Forward'], 150)
        daily_growth = 1.05 ** (1 / 365)
        for name, ledger in v['path_ledgers'].items():
            cash = ledger['Outside cash flow (GBP)'].iloc[0]
            for payment in ledger['Outside cash flow (GBP)'].iloc[1:]:
                cash = cash * daily_growth + payment
            self.assertAlmostEqual(cash, v['funded_gains'][name], places=8)
        np.testing.assert_allclose(v['funding_comparison']['Funded purchase cost (GBP)'], [1055.0200547732625, 1055, 1050])

    def test_ideal_tailing_uses_known_growth_and_matches_forward_payoff(self):
        v = self.values
        self.assertEqual(v['adjusted_units'][-1], 10)
        self.assertTrue((np.diff(v['adjusted_units']) > 0).all())
        self.assertAlmostEqual(v['adjusted_units'][361] * -5 * 1.05 ** (3 / 365), -50)
        np.testing.assert_allclose(v['replication']['Adjusted units: reinvested VM (GBP)'], 150)
        np.testing.assert_allclose(v['replication']['Fixed units: reinvested VM (GBP)'], [149.99331293103864, 150.0374341470127])
        # A different terminal price must alter the replication payoff, not leave a hard-coded 150.
        for final in (80, 105, 150):
            prices = v['prices_a'].copy()
            prices[-1] = final
            amount = np.sum(v['adjusted_units'] * np.diff(prices) * v['settlement_growth'])
            self.assertAlmostEqual(amount, 10 * (final - 105))

    def test_chart_values_labels_and_account_close_agree(self):
        v, charts = self.values, self.charts
        np.testing.assert_allclose(charts['futuresDailyCash']['series']['Long'], [-50, -20, 140, 80])
        np.testing.assert_allclose(charts['futuresDailyCash']['series']['Short'], [50, 20, -140, -80])
        self.assertEqual(charts['futuresDailyCash']['xAxis']['data'], ['362', '363', '364', '365'])
        np.testing.assert_allclose(charts['futuresCashTiming']['series']['Futures'], v['cumulative_variation'][v['last_days']])
        np.testing.assert_allclose(charts['futuresCashTiming']['series']['Forward'], [0, 0, 0, 0, 150])
        balances = charts['futuresMarginBalance']
        self.assertEqual(balances['xAxis']['data'], ['0', '361', '362', '363', '364', '365'])
        for name in ('Before funding/close', 'Closing balance'):
            np.testing.assert_allclose(balances['series'][name], v['margin_a'].loc[v['shown_days'], name + ' (GBP)'])
        self.assertIsNone(balances['series']['Maintenance level'][-1])
        np.testing.assert_allclose(charts['futuresOutsideCash']['series']["Owner's cash flow"], [-100, 0, -50, 0, 0, 300])
        for name, prices in [('A: fall then recover', v['prices_a']), ('B: steady rise', v['prices_b'])]:
            np.testing.assert_allclose(charts['futuresTwoPaths']['series'][name], prices[-5:])
        np.testing.assert_allclose(charts['futuresFundedComparison']['series']['After funding'], list(v['funded_gains'].values()))
        for chart in charts.values():
            self.assertIn('GBP', chart['yAxisName'])

    def test_widget_all_settings_match_independent_deposit_answers(self):
        totals = [100, 100, 128, 130, 140, 150, 160, 198, 212, 226, 240, 254, 268, 282, 296, 310]
        for dip, expected_total in enumerate(totals):
            with contextlib.redirect_stdout(output := io.StringIO()):
                pok.show_futures_liquidity_echart(dip)
            text = output.getvalue()
            payload = json.loads(text.split('<ECHARTS_DATA>')[1])
            self.assertIn(f'Total deposits: {expected_total:.2f} GBP', text)
            self.assertIn(f'Close-out receipt: {expected_total + 150:.2f} GBP', text)
            self.assertIn('Net cash before interest: 150.00 GBP', text)
            np.testing.assert_allclose(payload['futuresPathExperiment']['series']['Selected path'], [105, 105-dip, 105-1.4*dip, 112, 120])
            deposits = payload['futuresDepositExperiment']['series']
            self.assertEqual(deposits['Selected path'][0], 100)
            self.assertAlmostEqual(deposits['Selected path'][-1], expected_total)
            np.testing.assert_allclose(deposits['Steady rise'], 100)

    def test_invalid_ledger_and_widget_inputs(self):
        for prices in ([], [105], [[105, 106]], [105, np.nan], [np.inf, 105], None):
            with self.subTest(prices=prices), self.assertRaises(ValueError):
                pok.futures_margin_ledger(prices)
        for kwargs in ({'quantity': 0}, {'quantity': True}, {'quantity': np.nan}, {'initial_margin': 0},
                       {'maintenance_margin': 101}, {'maintenance_margin': -1}, {'initial_margin': '100'}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                pok.futures_margin_ledger([105, 106], **kwargs)
        for dip in (-1, 16, 5.0, True, '5', None):
            with self.subTest(dip=dip), self.assertRaises(ValueError):
                pok.show_futures_liquidity_echart(dip)

    def test_six_published_copies_match_and_execute(self):
        definitions = {name: [] for name in ('futures_margin_ledger', 'show_futures_liquidity_echart')}
        payloads = []
        for i, path in enumerate(MODULE_PATHS):
            for node in ast.parse((ROOT / path).read_text()).body:
                if isinstance(node, ast.FunctionDef) and node.name in definitions:
                    definitions[node.name].append(ast.dump(node))
            spec = importlib.util.spec_from_file_location(f'futures_copy_{i}', ROOT / path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with contextlib.redirect_stdout(output := io.StringIO()):
                module.show_futures_liquidity_echart(15)
            payloads.append(output.getvalue())
        for values in definitions.values():
            self.assertEqual(len(values), 6)
            self.assertEqual(len(set(values)), 1)
        self.assertEqual(len(set(payloads)), 1)

    def test_standalone_widget_and_exported_callback_keyword(self):
        with contextlib.redirect_stdout(io.StringIO()):
            namespace = {}
            exec(self.examples['futures-liquidity-widget'], namespace)
        box = namespace['widget_instance']
        try:
            export = next(block for block in re.findall(r'pyodide\.runPython\(`(.*?)`\)',
                          (ROOT / 'src/pyodide-worker.js').read_text(), re.S)
                          if 'from ipywidgets.embed import dependency_state' in block)
            exec(export, namespace)
            state = json.loads(namespace['_widget_json_result'])['state'][box.model_id]['state']
            self.assertEqual(state['_echarts_callback'], 'show_futures_liquidity_echart')
            self.assertEqual(state['_echarts_kwargs'], {'dip': 5})
        finally:
            box.close()


if __name__ == '__main__':
    unittest.main()
