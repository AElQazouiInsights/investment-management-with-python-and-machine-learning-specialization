"""Causal floor decisions, hedge consistency, reserve identities, and gap losses."""

import __main__
import ast
import importlib.util
import json
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from test_return_annualization import MODULE_PATHS, ROOT


class FloorAllocatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules = {}
        for i, path in enumerate(MODULE_PATHS):
            spec = importlib.util.spec_from_file_location(f"floor_copy_{i}", ROOT / path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cls.modules[path] = module

    def test_one_interval_gap_matches_hand_accounting(self):
        prices = pd.DataFrame({"Shock": [0.95, 1]}, index=[0, 1])
        stocks = pd.DataFrame({"Shock": [-0.5]}, index=[1])
        bonds = prices.pct_change(fill_method=None).iloc[1:]
        for path, module in self.modules.items():
            for multiplier, weight, terminal in ((1, 0.24, 0.92), (3, 0.72, 0.6547368421052632), (5, 1, 0.5)):
                with self.subTest(module=path, m=multiplier):
                    result = module.ldi_floor_backtest(stocks, bonds, prices, 0.8, multiplier)
                    self.assertAlmostEqual(result["Risky allocation"].iloc[0, 0], weight)
                    np.testing.assert_allclose(result["Wealth"]["Shock"], [1, terminal])
                    np.testing.assert_allclose(result["Floor value"]["Shock"], [0.76, 0.8])
                    self.assertAlmostEqual(result["Cushions"].iloc[0, 0], 0.24)
                    self.assertEqual(result["Floor breaches"].iloc[-1, 0], multiplier > 1)

    def test_m1_is_a_static_bond_reserve_plus_nonnegative_stock_value(self):
        prices = pd.DataFrame({"A": [0.9, 0.8, 1], "B": [0.9, 0.95, 1]})
        stocks = pd.DataFrame({"A": [-0.5, 0.8], "B": [0.2, -1]}, index=[1, 2])
        bonds = prices.pct_change(fill_method=None).iloc[1:]
        stock_growth = np.vstack([np.ones(2), (1 + stocks).cumprod().to_numpy()])
        expected = 0.8 * prices + stock_growth * (1 - 0.8 * prices.iloc[0].to_numpy())
        for path, module in self.modules.items():
            with self.subTest(module=path):
                result = module.ldi_floor_backtest(stocks, bonds, prices, 0.8, 1)
                np.testing.assert_allclose(result["Wealth"], expected, atol=1e-14)
                self.assertFalse(result["Floor breaches"].to_numpy().any())
                self.assertAlmostEqual(result["Wealth"].iloc[-1, 1], 0.8)
                for multiplier in (0, 0.5):
                    reserve = module.ldi_floor_backtest(stocks, bonds, prices, 0.8, multiplier)
                    self.assertFalse(reserve["Floor breaches"].to_numpy().any())
                all_bond = module.ldi_floor_backtest(stocks, bonds, prices, 0.8, 0)
                np.testing.assert_allclose(all_bond["Wealth"], prices / prices.iloc[0])

    def test_first_decision_does_not_use_end_price_or_current_stock_return(self):
        prices = pd.DataFrame({"A": [0.9, 0.95, 1]})
        changed_prices = pd.DataFrame({"A": [0.9, 0.8, 1]})
        stocks = pd.DataFrame({"A": [0.1, 0.2]}, index=[1, 2])
        changed_stocks = pd.DataFrame({"A": [-0.2, 0.8]}, index=[1, 2])
        for path, module in self.modules.items():
            with self.subTest(module=path):
                first = module.ldi_floor_backtest(stocks, prices.pct_change().iloc[1:], prices, 0.8, 1)
                changed = module.ldi_floor_backtest(changed_stocks, changed_prices.pct_change().iloc[1:], changed_prices, 0.8, 1)
                self.assertAlmostEqual(first["Risky allocation"].iloc[0, 0], 0.28)
                self.assertEqual(first["Risky allocation"].iloc[0, 0], changed["Risky allocation"].iloc[0, 0])
                self.assertNotAlmostEqual(first["Risky allocation"].iloc[1, 0], changed["Risky allocation"].iloc[1, 0])

    def test_relative_bond_performance_can_cause_a_breach_and_the_deficit_locks_in(self):
        prices = pd.DataFrame({"A": [0.8, 0.99, 1]})
        stocks = pd.DataFrame({"A": [-0.2, 1]}, index=[1, 2])
        bonds = prices.pct_change(fill_method=None).iloc[1:]
        for path, module in self.modules.items():
            with self.subTest(module=path):
                result = module.ldi_floor_backtest(stocks, bonds, prices, 0.95, 3)
                self.assertGreater(stocks.iloc[0, 0], -1 / 3)
                self.assertLess((1 + stocks.iloc[0, 0]) / (1 + bonds.iloc[0, 0]) - 1, -1 / 3)
                self.assertAlmostEqual(result["Wealth"].iloc[1, 0], 0.9225)
                self.assertTrue(result["Floor breaches"].iloc[1, 0])
                self.assertEqual(result["Risky allocation"].iloc[1, 0], 0)
                self.assertAlmostEqual(result["Wealth"].iloc[-1, 0], 0.9225 / 0.99)
                ratio = result["Wealth"]["A"] / result["Floor value"]["A"]
                self.assertAlmostEqual(ratio.iloc[1], ratio.iloc[2])

    def test_unfunded_promise_is_recorded_at_time_zero_and_cannot_be_repaired_by_the_rule(self):
        prices = pd.DataFrame({"A": [0.8, 0.9, 1]})
        stocks = pd.DataFrame({"A": [1, 1]}, index=[1, 2])
        bonds = prices.pct_change().iloc[1:]
        for path, module in self.modules.items():
            with self.subTest(module=path):
                result = module.ldi_floor_backtest(stocks, bonds, prices, 1.5, 3)
                np.testing.assert_array_equal(result["Risky allocation"], 0)
                self.assertTrue(result["Floor breaches"].to_numpy().all())
                self.assertAlmostEqual(result["Wealth"].iloc[-1, 0], 1.25)

    def test_depleted_account_stays_zero_and_has_no_defined_later_return(self):
        prices = pd.DataFrame({"A": [0.9, 0.95, 1]})
        stocks = pd.DataFrame({"A": [-1, 2]}, index=[1, 2])
        for path, module in self.modules.items():
            with self.subTest(module=path):
                result = module.ldi_floor_backtest(stocks, prices.pct_change().iloc[1:], prices, 0.8, 5)
                np.testing.assert_array_equal(result["Wealth"].iloc[1:], 0)
                self.assertEqual(result["Returns"].iloc[0, 0], -1)
                self.assertTrue(np.isnan(result["Returns"].iloc[1, 0]))
                self.assertEqual(result["Risky allocation"].iloc[1, 0], 0)

    def test_allocator_wrapper_reconstructs_the_same_funded_account(self):
        prices = pd.DataFrame({"A": [0.9, 0.8, 1], "B": [0.9, 0.95, 1]})
        stocks = pd.DataFrame({"A": [-0.1, 0.3], "B": [0.2, -0.1]}, index=[1, 2])
        original_prices, original_stocks = prices.copy(), stocks.copy()
        bonds = prices.pct_change().iloc[1:]
        for path, module in self.modules.items():
            with self.subTest(module=path):
                result = module.ldi_floor_backtest(stocks, bonds, prices, 0.8, 3)
                mixed = module.ldi_mixer(stocks, bonds, module.ldi_floor_allocator, zcb_price=prices, floor=0.8, m=3)
                np.testing.assert_allclose(mixed, result["Returns"], atol=1e-14)
                np.testing.assert_allclose((1 + mixed).cumprod(), result["Wealth"].iloc[1:], atol=1e-14)
                pd.testing.assert_frame_equal(prices, original_prices)
                pd.testing.assert_frame_equal(stocks, original_stocks)

    def test_missing_initial_prices_wrong_hedge_and_invalid_contracts_are_rejected(self):
        prices = pd.DataFrame({"A": [0.9, 0.95, 1]})
        stocks = pd.DataFrame({"A": [0.1, 0.2]}, index=[1, 2])
        bonds = prices.pct_change().iloc[1:]
        for path, module in self.modules.items():
            for bad in (prices.iloc[1:], prices.rename(columns={"A": "B"}), prices * 0, prices * np.nan, prices * 0.9):
                with self.subTest(module=path), self.assertRaises(ValueError):
                    module.ldi_floor_backtest(stocks, bonds, bad)
            with self.subTest(module=path), self.assertRaisesRegex(ValueError, "Hedge returns"):
                module.ldi_floor_backtest(stocks, bonds * 0, prices)
            for kwargs in ({"floor": -1}, {"floor": np.inf}, {"m": -1}, {"m": np.nan}):
                with self.subTest(module=path, kwargs=kwargs), self.assertRaises(ValueError):
                    module.ldi_floor_backtest(stocks, bonds, prices, **kwargs)

    def test_selected_path_and_floor_curve_are_paired_and_do_not_change_statistics(self):
        for path, module in self.modules.items():
            messages = []
            with self.subTest(module=path), patch.object(__main__, "_emit_echarts", messages.append, create=True):
                module.show_floor_echart(n_years=1, n_scenarios=4, scenario=1)
                module.show_floor_echart(n_years=1, n_scenarios=4, scenario=2)
                first_text, first_data = messages[0].split("<ECHARTS_DATA>")
                second_text, second_data = messages[1].split("<ECHARTS_DATA>")
                self.assertEqual(first_text, second_text)
                first, second = json.loads(first_data), json.loads(second_data)
                self.assertNotEqual(first["floorWealth"]["series"]["Floor PV"], second["floorWealth"]["series"]["Floor PV"])
                rate_seed, _ = np.random.SeedSequence(42).spawn(2)
                _, prices = module.simulate_cir(1, 4, a=0.05, b=0.03, sigma=0.02, r0=0.03, seed=rate_seed)
                np.testing.assert_allclose(np.asarray(second["floorWealth"]["series"]["Floor PV"])[:, 1], 0.8 * prices[1])
                points = np.asarray(second["floorWeights"]["series"]["Floor allocator"])
                self.assertAlmostEqual(points[0, 1], (1 - 0.8 * prices.iloc[0, 1]) * 100)
                self.assertEqual(points[-1, 0], 1)
                self.assertEqual(points[-1, 1], points[-2, 1])

    def test_floor_helpers_match_across_toolkit_copies(self):
        names = {"ldi_floor_allocator", "ldi_floor_backtest", "show_floor_echart"}
        definitions = []
        for path in MODULE_PATHS:
            definitions.append({node.name: ast.dump(node) for node in ast.parse((ROOT / path).read_text()).body
                                if isinstance(node, ast.FunctionDef) and node.name in names})
        self.assertEqual(set(definitions[0]), names)
        for candidate in definitions[1:]:
            self.assertEqual(candidate, definitions[0])


if __name__ == "__main__":
    unittest.main()
