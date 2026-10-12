"""Self-financing cash rollover, matching identities, and terminal distributions."""

import __main__
import ast
import importlib.util
import json
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from test_return_annualization import MODULE_PATHS, ROOT


class LiabilityHedgingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules = {}
        for i, path in enumerate(MODULE_PATHS):
            spec = importlib.util.spec_from_file_location(f"hedging_copy_{i}", ROOT / path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cls.modules[path] = module

    def chart(self, module, **kwargs):
        messages = []
        with patch.object(__main__, "_emit_echarts", messages.append, create=True):
            module.show_liability_hedging_echart(**kwargs)
        self.assertEqual(len(messages), 1)
        text, data = messages[0].split("<ECHARTS_DATA>")
        return text, json.loads(data)

    def test_flat_cash_growth_has_no_extra_interval_and_preserves_labels(self):
        index = pd.date_range("2026-01-01", periods=121, freq="MS", name="roll date")
        rates = pd.DataFrame(0.03, index=index, columns=["first", "second"])
        original = rates.copy()
        for path, module in self.modules.items():
            with self.subTest(module=path):
                cash = module.cir_cash_wealth(rates, initial_assets=0.75, b=0.03, sigma=0)
                np.testing.assert_allclose(cash["first"], 0.75 * 1.03 ** (np.arange(121) / 12), rtol=1e-13)
                pd.testing.assert_index_equal(cash.index, rates.index)
                pd.testing.assert_index_equal(cash.columns, rates.columns)
                pd.testing.assert_frame_equal(rates, original)

    def test_deterministic_mean_reversion_cash_and_bond_match_at_every_date(self):
        # Independent integrated-rate formula; tests non-flat rates as well as the flat limit.
        a, level, initial, assets, horizon = 0.5, np.log1p(0.03), np.log1p(0.08), 0.75, 3
        for path, module in self.modules.items():
            for frequency in (1, 12, 52):
                with self.subTest(module=path, frequency=frequency):
                    times = np.arange(horizon * frequency + 1) / frequency
                    continuous = level + (initial - level) * np.exp(-a * times)
                    rates = pd.DataFrame(np.expm1(continuous))
                    cash = module.cir_cash_wealth(rates, assets, a=a, b=0.03, sigma=0, periods_per_year=frequency)
                    integral = level * times + (initial - level) * (1 - np.exp(-a * times)) / a
                    expected_cash = assets * np.exp(integral)
                    np.testing.assert_allclose(cash[0], expected_cash, rtol=1e-13)
                    initial_price = np.exp(-integral[-1])
                    remaining_prices = np.exp(-(integral[-1] - integral))
                    np.testing.assert_allclose(cash[0], assets / initial_price * remaining_prices, rtol=1e-13)

    def test_rollover_is_self_financing_and_uses_only_beginning_information(self):
        quotes = pd.DataFrame({"low": [0.03, 0.01, 0.02], "high": [0.03, 0.10, 0.12]})
        for path, module in self.modules.items():
            with self.subTest(module=path):
                cash = module.cir_cash_wealth(quotes, initial_assets=0.75, a=0.5, b=0.03, sigma=0.10)
                self.assertEqual(cash.iloc[0, 0], 0.75)
                self.assertEqual(cash.iloc[1, 0], cash.iloc[1, 1])
                self.assertGreater(cash.iloc[-1, 1], cash.iloc[-1, 0])
                prices = module.cir_zero_coupon_price(1 / 12, quotes.iloc[:-1], a=0.5, b=0.03, sigma=0.10)
                # The face amount purchased is next period's wealth; cost equals available wealth.
                np.testing.assert_allclose(cash.iloc[1:].to_numpy() * prices, cash.iloc[:-1], rtol=1e-14)
                changed = quotes.copy()
                changed.iloc[-1] = 0.50
                pd.testing.assert_frame_equal(cash, module.cir_cash_wealth(changed, 0.75, a=0.5, b=0.03, sigma=0.10))

    def test_zero_rates_and_zero_capital_do_not_create_growth(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                rates, _ = module.simulate_cir(n_years=1, n_scenarios=2, b=0, r0=0, sigma=0.20, seed=42)
                np.testing.assert_allclose(module.cir_cash_wealth(rates, 0.75, b=0, sigma=0.20), 0.75)
                np.testing.assert_array_equal(module.cir_cash_wealth(rates, 0, b=0, sigma=0.20), 0)

    def test_matching_removes_rate_risk_without_removing_a_funding_deficit(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                _, prices = module.simulate_cir(n_years=3, n_scenarios=10, sigma=0.20, seed=42)
                liability = 2.0
                for initial_ratio in (0.8, 1, 1.2):
                    assets = initial_ratio * liability * prices.iloc[0, 0]
                    face = assets / prices.iloc[0, 0]
                    wealth = face * prices
                    np.testing.assert_allclose(wealth.iloc[0], assets)
                    np.testing.assert_allclose(wealth / (liability * prices), initial_ratio, rtol=1e-14)
                    np.testing.assert_allclose(wealth.iloc[-1], initial_ratio * liability)

    def test_chart_paths_and_cdfs_use_one_shared_sample_and_one_probability_scale(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                text, chart = self.chart(module, n_years=2, n_scenarios=20, initial_assets=0.8, liability=1.2)
                rates, prices = module.simulate_cir(n_years=2, n_scenarios=20, sigma=0.08, r0=0.03, seed=42)
                cash = module.cir_cash_wealth(rates, 0.8, sigma=0.08)
                ratios = cash / (1.2 * prices)
                self.assertIn("not a real-world forecast", text)
                self.assertIn("underfunded", text)
                for column in range(5):
                    points = np.asarray(chart["hedgingFunding"]["series"][f"Cash {column + 1}"])
                    np.testing.assert_allclose(points[:, 0], np.arange(25) / 12)
                    np.testing.assert_allclose(points[:, 1], ratios[column])
                cdf = chart["hedgingTerminal"]
                self.assertEqual(cdf["yAxis"]["max"], 100)
                for name in ("Cash", "Matching bond"):
                    points = np.asarray(cdf["series"][name])
                    self.assertEqual(points[0, 1], 0)
                    self.assertEqual(points[-1, 1], 100)
                    self.assertTrue((np.diff(points[:, 0]) >= 0).all())
                    self.assertTrue((np.diff(points[:, 1]) >= 0).all())
                points = np.asarray(cdf["series"]["Cash"])
                np.testing.assert_allclose(points[2:-1:2, 0], np.sort(ratios.iloc[-1]))
                np.testing.assert_allclose(points[2:-1:2, 1], np.arange(1, 21) * 5)
                np.testing.assert_allclose(np.asarray(cdf["series"]["Matching bond"])[1:3, 0], 0.8 / (1.2 * prices.iloc[0, 0]))

    def test_full_funding_equality_is_not_a_shortfall_even_with_a_cdf_jump(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                assets = 1.03 ** -10
                text, chart = self.chart(module, initial_assets=assets, sigma=0, n_scenarios=3)
                self.assertIn("fully funded or in surplus", text)
                self.assertIn("0/3 (0.0%)", text)
                np.testing.assert_allclose(np.asarray(chart["hedgingTerminal"]["series"]["Cash"])[1:-1, 0], 1, atol=1e-13)

    def test_seed_changes_cash_outcomes_but_not_the_matching_ratio(self):
        module = self.modules["PortfolioOptimizationKit.py"]
        _, first = self.chart(module, n_scenarios=10, seed=42)
        _, second = self.chart(module, n_scenarios=10, seed=43)
        self.assertNotEqual(first["hedgingFunding"]["series"]["Cash 1"], second["hedgingFunding"]["series"]["Cash 1"])
        self.assertEqual(first["hedgingFunding"]["series"]["Matching bond"], second["hedgingFunding"]["series"]["Matching bond"])

    def test_invalid_cash_and_liability_inputs_are_rejected(self):
        rates = pd.DataFrame({"scenario": [0.03, 0.04]})
        for path, module in self.modules.items():
            for kwargs in ({"initial_assets": -1}, {"initial_assets": np.nan}, {"periods_per_year": None}, {"periods_per_year": 0}):
                with self.subTest(module=path, kwargs=kwargs), self.assertRaises(ValueError):
                    module.cir_cash_wealth(rates, **kwargs)
            for bad in (rates.iloc[:1], rates.iloc[::-1], rates * np.nan, rates * -1,
                        pd.DataFrame([[0.03], [0.04]], index=[0, 0])):
                with self.subTest(module=path), self.assertRaises(ValueError):
                    module.cir_cash_wealth(bad)
            for kwargs in ({"liability": 0}, {"liability": -1}, {"liability": np.inf}, {"initial_assets": -1}):
                with self.subTest(module=path, kwargs=kwargs), self.assertRaises(ValueError):
                    module.show_liability_hedging_echart(**kwargs)

    def test_hedging_helpers_are_identical_in_all_published_copies(self):
        names = {"cir_cash_wealth", "show_liability_hedging_echart"}
        definitions = []
        for path in MODULE_PATHS:
            tree = ast.parse((ROOT / path).read_text())
            definitions.append({node.name: ast.dump(node) for node in tree.body
                                if isinstance(node, ast.FunctionDef) and node.name in names})
        self.assertEqual(set(definitions[0]), names)
        for definition in definitions[1:]:
            self.assertEqual(definition, definitions[0])


if __name__ == "__main__":
    unittest.main()
