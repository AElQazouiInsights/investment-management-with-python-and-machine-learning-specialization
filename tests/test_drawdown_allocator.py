"""High-water timing, gap risk, defensive-sleeve losses, and observed drawdowns."""

import __main__
import ast
import importlib.util
import json
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from test_return_annualization import MODULE_PATHS, ROOT


class DrawdownAllocatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules = {}
        for i, path in enumerate(MODULE_PATHS):
            spec = importlib.util.spec_from_file_location(f"drawdown_copy_{i}", ROOT / path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cls.modules[path] = module

    def test_gain_gap_and_defensive_loss_match_hand_calculations(self):
        stocks = pd.DataFrame({"Path": [0.5, -0.3, 0.2]}, index=[1, 2, 3])
        cash = stocks * 0
        bonds = pd.DataFrame({"Path": [0, 0, -0.1]}, index=stocks.index)
        for path, module in self.modules.items():
            with self.subTest(module=path):
                safe = module.ldi_drawdown_backtest(stocks, cash, 0.2)
                risky_hedge = module.ldi_drawdown_backtest(stocks, bonds, 0.2)
                np.testing.assert_allclose(safe["Risky allocation"].iloc[:, 0], [1, 1, 0], atol=1e-14)
                np.testing.assert_allclose(safe["Wealth"].iloc[:, 0], [1.5, 1.05, 1.05])
                np.testing.assert_allclose(risky_hedge["Wealth"].iloc[:, 0], [1.5, 1.05, 0.945])
                np.testing.assert_allclose(safe["Prior peaks"].iloc[:, 0], [1, 1.5, 1.5])
                np.testing.assert_allclose(safe["Floor value"].iloc[:, 0], [0.8, 1.2, 1.2])
                np.testing.assert_allclose(safe["Next floor"].iloc[:, 0], 1.2)
                self.assertAlmostEqual(safe["Drawdown"].min().iloc[0], -0.3)
                self.assertAlmostEqual(risky_hedge["Drawdown"].min().iloc[0], -0.37)
                self.assertGreater(risky_hedge["Wealth"].iloc[-1, 0], 0.8)

    def test_initial_wealth_is_a_peak_and_every_requested_limit_starts_fully_in_stocks(self):
        stocks = pd.DataFrame({"A": [-0.1, 0.1]}, index=[1, 2])
        for path, module in self.modules.items():
            for limit in (0.05, 0.2, 0.5, 1):
                with self.subTest(module=path, limit=limit):
                    result = module.ldi_drawdown_backtest(stocks, stocks * 0, limit)
                    self.assertAlmostEqual(result["Risky allocation"].iloc[0, 0], 1)
                    self.assertEqual(result["Peaks"].iloc[0, 0], 1)
                    self.assertAlmostEqual(result["Drawdown"].iloc[0, 0], -0.1)
                    self.assertAlmostEqual(result["m"], 1 / limit)

    def test_decisions_use_prior_peaks_and_only_next_decisions_see_changed_returns(self):
        first = pd.DataFrame({"A": [0.1, -0.1, 0.2]}, index=[1, 2, 3])
        changed = pd.DataFrame({"A": [0.1, 0.3, -0.2]}, index=first.index)
        for path, module in self.modules.items():
            with self.subTest(module=path):
                base = module.ldi_drawdown_backtest(first, first * 0)
                alternative = module.ldi_drawdown_backtest(changed, changed * 0)
                np.testing.assert_allclose(base["Risky allocation"].iloc[:2], alternative["Risky allocation"].iloc[:2])
                np.testing.assert_allclose(base["Floor value"].iloc[:2], alternative["Floor value"].iloc[:2])
                self.assertNotAlmostEqual(base["Risky allocation"].iloc[2, 0], alternative["Risky allocation"].iloc[2, 0])
                self.assertNotAlmostEqual(base["Next floor"].iloc[1, 0], alternative["Next floor"].iloc[1, 0])

    def test_accounts_use_their_own_wealth_peaks_and_preserve_budget_and_labels(self):
        stocks = pd.DataFrame({"A": [0.5, -0.1, 0.5, -0.1], "B": [-0.1, 0.5, -0.2, 0]}, index=[1, 2, 3, 4])
        original = stocks.copy()
        for path, module in self.modules.items():
            with self.subTest(module=path):
                result = module.ldi_drawdown_backtest(stocks, stocks * 0)
                self.assertAlmostEqual(result["Prior peaks"].loc[4, "A"], 1.725)
                self.assertAlmostEqual(result["Prior peaks"].loc[4, "B"], 1.15)
                for name in stocks:
                    alone = module.ldi_drawdown_backtest(stocks[[name]], stocks[[name]] * 0)
                    pd.testing.assert_series_equal(result["Wealth"][name], alone["Wealth"][name])
                mixed = module.ldi_mixer(stocks, stocks * 0, module.ldi_drawdown_allocator, maxdd=0.2)
                np.testing.assert_allclose((1 + mixed).cumprod(), result["Wealth"], atol=1e-14)
                pd.testing.assert_index_equal(result["Wealth"].columns, stocks.columns)
                pd.testing.assert_frame_equal(stocks, original)

    def test_positive_cash_can_restore_a_cushion_after_a_breach(self):
        stocks = pd.DataFrame({"A": [0.5, -0.3, 0.2, 0.1]}, index=[1, 2, 3, 4])
        cash = pd.DataFrame({"A": [0, 0, 0.2, 0]}, index=stocks.index)
        for path, module in self.modules.items():
            with self.subTest(module=path):
                result = module.ldi_drawdown_backtest(stocks, cash)
                np.testing.assert_allclose(result["Wealth"].iloc[:, 0], [1.5, 1.05, 1.26, 1.29])
                self.assertEqual(result["Risky allocation"].iloc[2, 0], 0)
                self.assertGreater(result["Risky allocation"].iloc[3, 0], 0)
                self.assertEqual(result["Drawdown breaches"].iloc[:, 0].tolist(), [False, True, False, False])

    def test_depletion_does_not_resurrect_and_invalid_limits_or_alignment_are_rejected(self):
        stocks = pd.DataFrame({"A": [-1, 2]}, index=[1, 2])
        for path, module in self.modules.items():
            with self.subTest(module=path):
                result = module.ldi_drawdown_backtest(stocks, stocks * 0, maxdd=0.5)
                np.testing.assert_allclose(result["Wealth"], 0)
                np.testing.assert_allclose(result["Drawdown"], -1)
                self.assertTrue(np.isnan(result["Returns"].iloc[1, 0]))
                self.assertEqual(result["Risky allocation"].iloc[1, 0], 0)
                for limit in (0, -0.2, 1.1, np.nan, None):
                    with self.assertRaises(ValueError):
                        module.ldi_drawdown_backtest(stocks, stocks * 0, limit)
                for bad in (stocks.rename(columns={"A": "B"}), stocks.set_axis([0, 1]), stocks * np.nan):
                    with self.assertRaises(ValueError):
                        module.ldi_drawdown_backtest(stocks, bad)

    def test_chart_selector_preserves_scenarios_and_drawdown_denominators(self):
        for path, module in self.modules.items():
            messages = []
            with self.subTest(module=path), patch.object(__main__, "_emit_echarts", messages.append, create=True):
                module.show_drawdown_echart(n_years=1, n_scenarios=4, hedge="cash")
                module.show_drawdown_echart(n_years=1, n_scenarios=4, hedge="zcb")
                first_text, first_data = messages[0].split("<ECHARTS_DATA>")
                next_text, next_data = messages[1].split("<ECHARTS_DATA>")
                self.assertEqual(first_text, next_text)
                first, second = json.loads(first_data), json.loads(next_data)
                self.assertEqual(first["drawdownLoss"], second["drawdownLoss"])
                for plot, name in ((first, "cash"), (second, "ZCB")):
                    series = plot["drawdownWealth"]["series"]
                    wealth = np.asarray(series["Policy wealth"])[:, 1]
                    peaks = np.asarray(series["High-water mark"])[:, 1]
                    np.testing.assert_allclose(peaks, np.maximum.accumulate(wealth))
                    np.testing.assert_allclose(np.asarray(series["High-water floor"])[:, 1], 0.8 * peaks)
                    np.testing.assert_allclose(np.asarray(plot["drawdownLoss"]["series"][f"Policy + {name}"])[:, 1],
                                               (wealth / peaks - 1) * 100, atol=1e-12)
                self.assertEqual(first["drawdownLoss"]["series"]["Drawdown limit"], [[0, -20], [1, -20]])

    def test_drawdown_helpers_match_across_toolkit_copies(self):
        names = {"ldi_drawdown_allocator", "ldi_drawdown_backtest", "show_drawdown_echart"}
        definitions = []
        for path in MODULE_PATHS:
            definitions.append({node.name: ast.dump(node) for node in ast.parse((ROOT / path).read_text()).body
                                if isinstance(node, ast.FunctionDef) and node.name in names})
        self.assertEqual(set(definitions[0]), names)
        for candidate in definitions[1:]:
            self.assertEqual(candidate, definitions[0])


if __name__ == "__main__":
    unittest.main()
