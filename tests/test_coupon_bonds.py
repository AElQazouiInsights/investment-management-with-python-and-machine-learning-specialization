"""Coupon timing, curve pricing, reinvestment, and redemption accounting."""

import __main__
import ast
import importlib.util
import json
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from test_return_annualization import MODULE_PATHS, ROOT


class CouponBondTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules = {}
        for i, path in enumerate(MODULE_PATHS):
            spec = importlib.util.spec_from_file_location(f"coupon_copy_{i}", ROOT / path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cls.modules[path] = module

    def test_cashflows_count_coupon_and_face_value_once(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                flows = module.bond_cash_flows(100, 3, 0.03, 2)
                np.testing.assert_array_equal(flows.index, np.arange(1, 7))
                np.testing.assert_allclose(flows[0], [1.5] * 5 + [101.5])
                self.assertEqual(flows[0].sum(), 109)
                np.testing.assert_allclose(module.bond_cash_flows(100, 0.5, 0.03, 2)[0], [101.5])
                np.testing.assert_allclose(module.bond_cash_flows(100, 3, 0, 2)[0], [0] * 5 + [100])

    def test_discount_par_premium_and_zero_yield_match_dated_sums(self):
        for path, module in self.modules.items():
            for ytm in (-0.01, 0, 0.02, 0.03, 0.05):
                with self.subTest(module=path, ytm=ytm):
                    expected = sum(1.5 / (1 + ytm / 2) ** k for k in range(1, 7)) + 100 / (1 + ytm / 2) ** 6
                    self.assertAlmostEqual(module.bond_price(100, 3, 0.03, 2, ytm), expected)
            with self.subTest(module=path):
                self.assertAlmostEqual(module.bond_price(100, 3, 0.03, 2, 0), 109)
                self.assertAlmostEqual(module.bond_price(100, 3, 0.03, 2, 0.03), 100)

    def test_named_custom_schedule_is_discounted_and_remaining_payments_roll_off(self):
        flows = pd.DataFrame({"Cash": [2.0, 4.0, 100.0]}, index=[1, 2, 6])
        quotes = pd.DataFrame({"low": [0.02] * 7, "high": [0.06] * 7})
        for path, module in self.modules.items():
            with self.subTest(module=path):
                prices = module.bond_price(maturity=3, cf=flows, ytm=quotes)
                pd.testing.assert_index_equal(prices.index, quotes.index)
                pd.testing.assert_index_equal(prices.columns, quotes.columns)
                for step in range(7):
                    for name in quotes:
                        expected = sum(value / (1 + quotes.loc[step, name] / 2) ** (period - step)
                                       for period, value in flows["Cash"].items() if period > step)
                        self.assertAlmostEqual(prices.loc[step, name], expected)
                self.assertAlmostEqual(module.bond_price(maturity=3, cf=flows, ytm=0.02), prices.loc[0, "low"])

    def test_constant_yield_returns_include_coupons_and_final_redemption_exactly_once(self):
        quotes = pd.DataFrame({"Flat": np.full(37, 0.05)})
        for path, module in self.modules.items():
            for frequency in (1, 2, 4, 12):
                with self.subTest(module=path, coupon_frequency=frequency):
                    prices = module.bond_price(100, 3, 0.03, frequency, quotes, periods_per_year=12)
                    returns = module.bond_returns(100, prices, 0.03, frequency, 12)
                    expected = (1 + 0.05 / frequency) ** (frequency / 12) - 1
                    np.testing.assert_allclose(returns, expected, atol=2e-14)
                    np.testing.assert_array_equal(prices.iloc[-1], 0)
                    final_payment = 100 + 3 / frequency
                    self.assertAlmostEqual((1 + returns.iloc[-1, 0]) * prices.iloc[-2, 0], final_payment)
                    self.assertAlmostEqual(module.annualize_rets(returns, 12).iloc[0], (1 + 0.05 / frequency) ** frequency - 1)

    def test_truncating_a_longer_bond_does_not_redeem_it_early(self):
        quotes = pd.DataFrame({"Long bond": np.full(61, 0.04)})
        for path, module in self.modules.items():
            with self.subTest(module=path):
                prices = module.bond_price(100, 5, 0.03, 2, quotes, periods_per_year=12)
                shortened = prices.iloc[:25]
                self.assertGreater(shortened.iloc[-1, 0], 0)
                returns = module.bond_returns(100, shortened, 0.03, 2, 12)
                self.assertAlmostEqual((1 + returns.iloc[-1, 0]) * shortened.iloc[-2, 0] - shortened.iloc[-1, 0], 1.5)
                np.testing.assert_allclose(returns, 1.02 ** (1 / 6) - 1, atol=1e-14)

    def test_scalar_return_explicitly_means_zero_interest_coupon_holding(self):
        price = 94.49187463842017
        for path, module in self.modules.items():
            with self.subTest(module=path):
                actual = module.bond_returns(100, price, 0.03, 2, 12, maturity=3)
                self.assertAlmostEqual(actual, (109 / price) ** (1 / 3) - 1)
                self.assertLess(actual, 1.025 ** 2 - 1)

    def test_cir_price_is_a_strip_of_remaining_zero_coupons_at_the_current_rate(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                rates, _ = module.simulate_cir(3, 3, a=0.5, b=0.03, sigma=0.1, r0=0.05, seed=42)
                prices = module.cir_bond_price(rates, a=0.5, b=0.03, sigma=0.1)
                for step in (0, 1, 6, 18, 35, 36):
                    expected = sum((101.5 if period == 6 else 1.5) * module.cir_zero_coupon_price(
                        period / 2 - step / 12, rates.iloc[step].to_numpy(), a=0.5, b=0.03, sigma=0.1)
                        for period in range(1, 7) if period / 2 > step / 12)
                    np.testing.assert_allclose(prices.iloc[step], expected, rtol=1e-13)
                wrong_flat = module.bond_price(100, 3, 0.03, 2, 0.05)
                self.assertGreater(abs(prices.iloc[0, 0] - wrong_flat), 1)

    def test_flat_cir_curve_matches_equivalent_nominal_yield_and_effective_total_return(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                rates, _ = module.simulate_cir(3, 2, b=0.03, r0=0.03, sigma=0)
                cir_prices = module.cir_bond_price(rates, b=0.03, sigma=0)
                equivalent_ytm = 2 * (np.sqrt(1.03) - 1)
                quotes = pd.DataFrame(equivalent_ytm, index=rates.index, columns=rates.columns)
                flat_prices = module.bond_price(100, 3, 0.03, 2, quotes, periods_per_year=12)
                np.testing.assert_allclose(cir_prices, flat_prices, rtol=1e-13)
                returns = module.bond_returns(100, cir_prices, 0.03, 2, 12)
                np.testing.assert_allclose(module.annualize_rets(returns, 12), 0.03, atol=1e-13)

    def test_zero_coupon_limit_distinguishes_redemption_from_post_payment_value(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                rates, zero_prices = module.simulate_cir(3, 2, seed=42)
                coupon_prices = module.cir_bond_price(rates, coupon_rate=0)
                np.testing.assert_allclose(coupon_prices.iloc[:-1], 100 * zero_prices.iloc[:-1])
                np.testing.assert_array_equal(coupon_prices.iloc[-1], 0)
                returns = module.bond_returns(100, coupon_prices, 0, 2, 12)
                np.testing.assert_allclose((1 + returns).prod(), 100 / coupon_prices.iloc[0], rtol=1e-13)

    def test_widget_selected_values_and_reinvestment_identity(self):
        for path, module in self.modules.items():
            for coupon, reinvestment in ((0.03, 0), (0.03, 1.025 ** 2 - 1), (0, 0.10)):
                with self.subTest(module=path, coupon=coupon, reinvestment=reinvestment):
                    messages = []
                    with patch.object(__main__, "_emit_echarts", messages.append, create=True):
                        module.show_coupon_bond_echart(coupon_rate=coupon, reinvestment_rate=reinvestment)
                    text, encoded = messages[0].split("<ECHARTS_DATA>")
                    chart = json.loads(encoded)
                    price = module.bond_price(100, 3, coupon, 2, 0.05)
                    expected_terminal = 100 + sum(100 * coupon / 2 * (1 + reinvestment) ** (3 - k / 2) for k in range(1, 7))
                    np.testing.assert_allclose(chart["couponYield"]["series"]["Selected bond"], [[5, price]])
                    np.testing.assert_allclose(chart["couponReinvestment"]["series"]["Selected reinvestment"], [[100 * reinvestment, expected_terminal]])
                    self.assertEqual(chart["couponYield"]["seriesOptions"]["Selected bond"]["type"], "scatter")
                    self.assertIn("cash-flow IRR", text)
                    if reinvestment == 1.025 ** 2 - 1:
                        self.assertAlmostEqual(expected_terminal / price, 1.025 ** 6)

    def test_invalid_schedules_and_ambiguous_return_conventions_are_rejected(self):
        for path, module in self.modules.items():
            for kwargs in ({"maturity": 0.1}, {"maturity": 0}, {"principal": -100},
                           {"coupon_rate": -0.01}, {"coupons_per_year": None}):
                with self.subTest(module=path, kwargs=kwargs), self.assertRaises(ValueError):
                    module.bond_cash_flows(**kwargs)
            with self.subTest(module=path):
                with self.assertRaises(ValueError):
                    module.bond_price(ytm=-2)
                with self.assertRaises(ValueError):
                    module.bond_price(ytm=pd.DataFrame([0.03, 0.04], index=[1, 2]))
                with self.assertRaises(ValueError):
                    module.bond_price(ytm=pd.DataFrame([0.03, 0.04]), periods_per_year=1)
                with self.assertRaises(ValueError):
                    module.bond_returns(100, pd.DataFrame([100, 101.5]), 0.03, 2, 2, maturity=0.5)
                with self.assertRaises(ValueError):
                    module.bond_returns(100, pd.DataFrame([100, 0]), 0.03, 2, 2)

    def test_coupon_functions_are_identical_across_all_toolkit_copies(self):
        names = {"bond_cash_flows", "_bond_grid", "bond_price", "bond_returns", "cir_bond_price", "show_coupon_bond_echart"}
        definitions = []
        for path in MODULE_PATHS:
            definitions.append({node.name: ast.dump(node) for node in ast.parse((ROOT / path).read_text()).body
                                if isinstance(node, ast.FunctionDef) and node.name in names})
        self.assertEqual(set(definitions[0]), names)
        for candidate in definitions[1:]:
            self.assertEqual(candidate, definitions[0])


if __name__ == "__main__":
    unittest.main()
