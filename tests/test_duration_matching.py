"""Budget, duration, and funding identities for a fixed-holdings LDI hedge."""

import __main__
import ast
import importlib.util
import json
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from test_return_annualization import MODULE_PATHS, ROOT


class DurationMatchingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules = {}
        for i, path in enumerate(MODULE_PATHS):
            spec = importlib.util.spec_from_file_location(f"matching_copy_{i}", ROOT / path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cls.modules[path] = module

    def portfolio(self, module, capital=130000, short_frequency=1, long_frequency=1):
        liability = pd.DataFrame({"L": [100000.0, 100000.0]}, index=[10, 12])
        short = module.bond_cash_flows(1000, 10, 0.05, short_frequency).rename(columns={0: "Short"})
        long = module.bond_cash_flows(1000, 20, 0.05, long_frequency).rename(columns={0: "Long"})
        short.index = short.index / short_frequency
        long.index = long.index / long_frequency
        flows = pd.concat([short, long], axis=1).fillna(0).sort_index()
        prices = module.present_value(flows, 0.04)
        durations = module.mac_duration(flows, 0.04)
        target = module.mac_duration(liability, 0.04)
        weights = np.array(module.duration_match_weight(*durations, target))
        units = weights * capital / prices
        portfolio = flows.mul(units, axis=1).sum(axis=1).to_frame("A")
        return portfolio, liability, prices, units, weights

    def test_market_value_weights_match_target_in_either_asset_order(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                np.testing.assert_allclose(module.duration_match_weight(5, 15, 11), [0.4, 0.6])
                np.testing.assert_allclose(module.duration_match_weight(15, 5, 11), [0.6, 0.4])
                self.assertEqual(module.duration_match_weight(5, 15, 5), (1, 0))
                self.assertEqual(module.duration_match_weight(5, 15, 15), (0, 1))

    def test_infeasible_and_underdetermined_matches_are_rejected(self):
        for path, module in self.modules.items():
            for durations in ((5, 15, 20), (5, 15, 1), (5, 5, 5), (-1, 5, 3), (1, np.inf, 3), (1, 5, np.nan)):
                with self.subTest(module=path, durations=durations), self.assertRaises(ValueError):
                    module.duration_match_weight(*durations)

    def test_quantities_reconcile_budget_and_duration_but_not_full_funding(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                portfolio, liability, prices, units, weights = self.portfolio(module)
                self.assertAlmostEqual((prices * units).sum(), 130000)
                self.assertAlmostEqual(module.present_value(portfolio, 0.04).iloc[0], 130000)
                self.assertAlmostEqual(module.mac_duration(portfolio, 0.04), module.mac_duration(liability, 0.04))
                self.assertAlmostEqual(weights[0], 0.48263092069478974)
                ratio = module.present_value(portfolio, 0.04).iloc[0] / module.present_value(liability, 0.04).iloc[0]
                self.assertAlmostEqual(ratio, 0.9998760012192471)
                self.assertLess(ratio, 1)

    def test_funding_ratio_slope_is_zero_while_underfunded_surplus_slope_is_not(self):
        module = self.modules["PortfolioOptimizationKit.py"]
        portfolio, liability, *_ = self.portfolio(module)
        h, rate = 1e-6, 0.04
        def values(r):
            return module.present_value(portfolio, r).iloc[0], module.present_value(liability, r).iloc[0]
        a0, l0 = values(rate)
        up, down = values(rate + h), values(rate - h)
        ratio_slope = (up[0] / up[1] - down[0] / down[1]) / (2 * h)
        self.assertAlmostEqual(ratio_slope, 0, places=7)
        surplus_slope = ((up[0] - up[1]) - (down[0] - down[1])) / (2 * h)
        expected = -module.mac_duration(liability, rate) / (1 + rate) * (a0 - l0)
        self.assertAlmostEqual(surplus_slope, expected, delta=0.001)
        self.assertGreater(abs(surplus_slope), 100)
        full = portfolio * l0 / a0
        full_up = module.present_value(full, rate + h).iloc[0] - up[1]
        full_down = module.present_value(full, rate - h).iloc[0] - down[1]
        self.assertAlmostEqual((full_up - full_down) / (2 * h), 0, delta=0.001)

    def test_nonparallel_curve_move_can_underfund_an_initially_fully_funded_match(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                portfolio, liability, *_ = self.portfolio(module)
                liability_pv = module.present_value(liability, 0.04).iloc[0]
                full = portfolio * liability_pv / 130000
                dates = full.index.to_numpy()
                discounts = (1 + np.where(dates >= 15, 0.05, 0.04)) ** -dates
                stressed_asset = (full.iloc[:, 0].to_numpy() * discounts).sum()
                self.assertAlmostEqual(module.present_value(full, 0.04).iloc[0], liability_pv)
                self.assertLess(stressed_asset / liability_pv, 0.96)

    def test_different_coupon_frequencies_preserve_exact_matching_on_one_curve(self):
        for path, module in self.modules.items():
            for short_frequency, long_frequency in ((2, 4), (12, 1)):
                with self.subTest(module=path, frequencies=(short_frequency, long_frequency)):
                    portfolio, liability, prices, units, _ = self.portfolio(module, short_frequency=short_frequency, long_frequency=long_frequency)
                    self.assertAlmostEqual((prices * units).sum(), 130000)
                    self.assertAlmostEqual(module.mac_duration(portfolio, 0.04), module.mac_duration(liability, 0.04))

    def test_widget_cashflows_and_rate_scenarios_reconcile_to_fixed_holdings(self):
        for path, module in self.modules.items():
            messages = []
            with self.subTest(module=path), patch.object(__main__, "_emit_echarts", messages.append, create=True):
                module.show_duration_matching_echart(short_frequency=2, long_frequency=4)
                text, encoded = messages[-1].split("<ECHARTS_DATA>")
                plots = json.loads(encoded)
                points = np.asarray(plots["matchingPayments"]["series"]["Matched"])
                asset = pd.DataFrame({"A": points[:, 1] * 1000}, index=points[:, 0])
                points_l = np.asarray(plots["matchingPayments"]["series"]["Liability"])
                liability = pd.DataFrame({"L": points_l[:, 1] * 1000}, index=points_l[:, 0])
                self.assertAlmostEqual(module.present_value(asset, 0.04).iloc[0], 130000)
                self.assertAlmostEqual(module.mac_duration(asset, 0.04), module.mac_duration(liability, 0.04))
                curve = np.asarray(plots["matchingFunding"]["series"]["Duration matched"])
                expected = module.present_value(asset, curve[:, 0] / 100) / module.present_value(liability, curve[:, 0] / 100)
                np.testing.assert_allclose(curve[:, 1], expected, rtol=1e-13)
                self.assertIn("locally flat", text)

    def test_widget_clears_charts_when_no_long_only_match_exists(self):
        for path, module in self.modules.items():
            messages = []
            with self.subTest(module=path), patch.object(__main__, "_emit_echarts", messages.append, create=True):
                module.show_duration_matching_echart(liability_delay=10)
                text, encoded = messages[-1].split("<ECHARTS_DATA>")
                self.assertIn("No unique long-only duration match", text)
                self.assertEqual(json.loads(encoded), {})

    def test_matching_helpers_are_identical_in_all_toolkit_copies(self):
        names = {"duration_match_weight", "show_duration_matching_echart"}
        definitions = []
        for path in MODULE_PATHS:
            definitions.append({node.name: ast.dump(node) for node in ast.parse((ROOT / path).read_text()).body
                                if isinstance(node, ast.FunctionDef) and node.name in names})
        self.assertEqual(set(definitions[0]), names)
        for candidate in definitions[1:]:
            self.assertEqual(candidate, definitions[0])


if __name__ == "__main__":
    unittest.main()
