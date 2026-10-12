"""Simple-return mixing, paired simulations, terminal outcomes, and chart units."""

import __main__
import ast
import importlib.util
import json
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from test_return_annualization import MODULE_PATHS, ROOT


class FixedMixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules = {}
        for i, path in enumerate(MODULE_PATHS):
            spec = importlib.util.spec_from_file_location(f"mix_copy_{i}", ROOT / path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cls.modules[path] = module

    def test_fixed_mix_is_rebalanced_rather_than_buy_and_hold(self):
        stocks = pd.DataFrame({"Path": [1.0, -0.5]}, index=[1, 2])
        bonds = stocks * 0
        for path, module in self.modules.items():
            with self.subTest(module=path):
                mixed = module.ldi_mixer(stocks, bonds, module.ldi_fixed_allocator, w1=0.5)
                np.testing.assert_allclose(mixed["Path"], [0.5, -0.25])
                self.assertAlmostEqual(module.terminal_wealth(mixed).iloc[0], 1.125)
                buy_hold = 0.5 * module.terminal_wealth(stocks) + 0.5 * module.terminal_wealth(bonds)
                self.assertAlmostEqual(buy_hold.iloc[0], 1)
                pd.testing.assert_frame_equal(module.ldi_mixer(stocks, bonds, module.ldi_fixed_allocator, w1=1), stocks)
                pd.testing.assert_frame_equal(module.ldi_mixer(stocks, bonds, module.ldi_fixed_allocator, w1=0), bonds)

    def test_same_shape_wrong_labels_or_incomplete_returns_are_rejected(self):
        first = pd.DataFrame({"A": [0.1, -0.1], "B": [0.02, 0.03]}, index=[1, 2])
        for path, module in self.modules.items():
            for second in (first.rename(columns={"A": "C"}), first[["B", "A"]], first.set_axis([0, 1]),
                           first * np.nan, first.assign(A=[-1.1, 0]), first.set_axis([1, 1])):
                with self.subTest(module=path), self.assertRaises(ValueError):
                    module.ldi_mixer(first, second, module.ldi_fixed_allocator, w1=0.7)
            for weight in (-0.1, 1.1, np.nan, np.inf):
                with self.subTest(module=path, weight=weight), self.assertRaises(ValueError):
                    module.ldi_mixer(first, first, module.ldi_fixed_allocator, w1=weight)
            for bad_weights in (first.rename(columns={"A": "C"}), first * np.nan, first * 0 + 2):
                with self.subTest(module=path), self.assertRaises(ValueError):
                    module.ldi_mixer(first, first, lambda a, b: bad_weights)

    def test_first_interval_is_included_and_allocation_does_not_mutate_inputs(self):
        first = pd.DataFrame({"A": [0.1, -0.2]}, index=[1, 2])
        second = pd.DataFrame({"A": [0.02, 0.03]}, index=[1, 2])
        for path, module in self.modules.items():
            with self.subTest(module=path):
                a, b = first.copy(), second.copy()
                result = module.ldi_mixer(a, b, module.ldi_fixed_allocator, w1=0.7)
                self.assertAlmostEqual(result.iloc[0, 0], 0.076)
                self.assertAlmostEqual(module.terminal_wealth(result).iloc[0], 1.076 * (1 - 0.14 + 0.009))
                pd.testing.assert_frame_equal(a, first)
                pd.testing.assert_frame_equal(b, second)

    def test_terminal_metrics_distinguish_cagr_dispersion_and_conditional_shortfall(self):
        rets = pd.DataFrame({"Loss": [-0.4, 0], "Equal": [-0.2, 0], "Gain": [0.4, 0]}, index=[1, 2])
        for path, module in self.modules.items():
            with self.subTest(module=path):
                stats = module.summary_stats_terminal(rets, floor=0.8, periods_per_year=1, target=1)["Stats"]
                terminal = np.array([0.6, 0.8, 1.4])
                self.assertAlmostEqual(stats["Mean ann. ret."], (np.sqrt(terminal) - 1).mean())
                self.assertAlmostEqual(stats["Mean wealth"], terminal.mean())
                self.assertAlmostEqual(stats["Mean wealth std"], terminal.std(ddof=1))
                self.assertAlmostEqual(stats["Prob breach"], 1 / 3)
                self.assertAlmostEqual(stats["Exp shortfall"], 0.2)
                self.assertAlmostEqual(stats["Mean shortfall"], 0.2 / 3)
                self.assertAlmostEqual(stats["Prob reach target"], 1 / 3)
                self.assertAlmostEqual(stats["Mean surplus"], 0.4 / 3)

    def test_terminal_statistics_do_not_count_interim_breaches(self):
        rets = pd.DataFrame({"Recovery": [-0.5, 1.0], "Flat": [0, 0]}, index=[1, 2])
        for path, module in self.modules.items():
            with self.subTest(module=path):
                stats = module.summary_stats_terminal(rets, floor=0.8)["Stats"]
                self.assertEqual(stats["Prob breach"], 0)
                self.assertEqual(stats["Exp shortfall"], 0)
                self.assertEqual(stats["Mean shortfall"], 0)
                loss = module.summary_stats_terminal(pd.DataFrame({"Loss": [-1, 1]}, index=[1, 2]))["Stats"]
                self.assertEqual(loss["Mean wealth"], 0)
                self.assertEqual(loss["Mean ann. ret."], -1)
                self.assertTrue(np.isnan(loss["Mean wealth std"]))
                for kwargs in ({"floor": -1}, {"floor": np.inf}, {"target": np.nan}, {"periods_per_year": 0}):
                    with self.assertRaises(ValueError):
                        module.summary_stats_terminal(rets, **kwargs)

    def test_simulated_return_dates_and_bond_redemption_are_correct(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                sample = module.simulate_psp_lhp(n_scenarios=5)
                self.assertEqual(sample["Stocks"].shape, (20, 5))
                np.testing.assert_array_equal(sample["Stocks"].index, np.arange(1, 21))
                np.testing.assert_allclose(sample["Stocks"], np.expm1(sample["Stock log returns"]))
                np.testing.assert_allclose((1 + sample["Stocks"]).prod(), sample["Stock prices"].iloc[-1] / 100)
                np.testing.assert_array_equal(sample["Short prices"].iloc[-1], 0)
                self.assertTrue((sample["Long prices"].iloc[-1] > 0).all())
                np.testing.assert_allclose(sample["Short returns"].iloc[-1], 101.4 / sample["Short prices"].iloc[-2] - 1)
                np.testing.assert_allclose(sample["Long returns"].iloc[-1],
                                           (sample["Long prices"].iloc[-1] + 1.75) / sample["Long prices"].iloc[-2] - 1)
                np.testing.assert_allclose(sample["Fixed mix"], 0.7 * sample["Stocks"] + 0.18 * sample["Short returns"] + 0.12 * sample["Long returns"])

    def test_deterministic_limit_matches_flat_curve_and_exact_stock_growth(self):
        for path, module in self.modules.items():
            for frequency in (2, 12):
                with self.subTest(module=path, frequency=frequency):
                    sample = module.simulate_psp_lhp(n_years=2, n_scenarios=2, periods_per_year=frequency, sigma=0, rate_sigma=0)
                    stock_return = np.expm1(0.07 / frequency)
                    bond_return = 1.03 ** (1 / frequency) - 1
                    np.testing.assert_allclose(sample["Stocks"], stock_return, atol=1e-14)
                    np.testing.assert_allclose(sample["Bonds"], bond_return, atol=1e-14)
                    np.testing.assert_allclose(sample["Fixed mix"], 0.7 * stock_return + 0.3 * bond_return, atol=1e-14)

    def test_weight_changes_keep_component_paths_and_global_rng_unchanged(self):
        module = self.modules["PortfolioOptimizationKit.py"]
        state = np.random.get_state()
        try:
            np.random.seed(123)
            expected_rng = np.random.random(3)
            np.random.seed(123)
            baseline = module.simulate_psp_lhp(n_years=2, n_scenarios=10)
            changed = module.simulate_psp_lhp(n_years=2, n_scenarios=10, psp_weight=0)
            np.testing.assert_array_equal(np.random.random(3), expected_rng)
            for name in ("Rates", "Stocks", "Bonds", "Short returns", "Long returns"):
                pd.testing.assert_frame_equal(baseline[name], changed[name])
            pd.testing.assert_frame_equal(changed["Fixed mix"], changed["Bonds"])
            changed_rate = module.simulate_psp_lhp(n_years=2, n_scenarios=10, rate_sigma=0.05)
            pd.testing.assert_frame_equal(baseline["Stocks"], changed_rate["Stocks"])
            self.assertFalse(baseline["Rates"].equals(changed_rate["Rates"]))
        finally:
            np.random.set_state(state)

    def test_chart_time_zero_threshold_and_cdf_units_reconcile(self):
        for path, module in self.modules.items():
            messages = []
            with self.subTest(module=path), patch.object(__main__, "_emit_echarts", messages.append, create=True):
                module.show_psp_lhp_echart(n_years=2, n_scenarios=10)
                text, encoded = messages[-1].split("<ECHARTS_DATA>")
                plots = json.loads(encoded)
                self.assertIn("Uncalibrated", text)
                self.assertIn("Wilson", text)
                self.assertIn("experiment horizon", text)
                sample = module.simulate_psp_lhp(n_years=2, n_scenarios=10)
                for name in ("Stocks", "Bonds", "Fixed mix"):
                    points = np.asarray(plots["pspLhpWealth"]["series"][f"{name} median"])
                    np.testing.assert_allclose(points[0], [0, 1])
                    self.assertEqual(points[-1, 0], 2)
                    cdf = np.asarray(plots["pspLhpTerminal"]["series"][name])
                    np.testing.assert_allclose(cdf[2:-1:2, 0], np.sort((1 + sample[name]).prod()))
                    np.testing.assert_allclose(cdf[2:-1:2, 1], np.arange(1, 11) * 10)
                    self.assertTrue((np.diff(cdf[:, 0]) >= 0).all())
                self.assertEqual(plots["pspLhpTerminal"]["series"]["Terminal threshold"], [[0.8, 0], [0.8, 100]])

    def test_simulation_horizon_and_coupon_grid_are_validated(self):
        for path, module in self.modules.items():
            for kwargs in ({"n_years": 11}, {"n_years": 0}, {"periods_per_year": 1}, {"periods_per_year": None}):
                with self.subTest(module=path, kwargs=kwargs), self.assertRaises(ValueError):
                    module.simulate_psp_lhp(**kwargs)

    def test_all_fixed_mix_helpers_match_across_toolkit_copies(self):
        names = {"_ldi_return_frame", "ldi_mixer", "ldi_fixed_allocator", "summary_stats_terminal", "simulate_psp_lhp", "show_psp_lhp_echart"}
        definitions = []
        for path in MODULE_PATHS:
            definitions.append({node.name: ast.dump(node) for node in ast.parse((ROOT / path).read_text()).body
                                if isinstance(node, ast.FunctionDef) and node.name in names})
        self.assertEqual(set(definitions[0]), names)
        for candidate in definitions[1:]:
            self.assertEqual(candidate, definitions[0])


if __name__ == "__main__":
    unittest.main()
