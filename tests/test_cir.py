"""CIR transition moments, pricing identities, boundary cases, and chart checks."""

import __main__
import importlib.util
import json
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from test_return_annualization import MODULE_PATHS, ROOT


class CirTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules = {}
        for i, path in enumerate(MODULE_PATHS):
            spec = importlib.util.spec_from_file_location(f"cir_copy_{i}", ROOT / path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cls.modules[path] = module

    def test_flat_rate_case_matches_effective_annual_discounting(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                rates, prices = module.simulate_cir(n_years=3, n_scenarios=2, a=0.5,
                                                    b=0.03, r0=0.03, sigma=0, seed=42)
                self.assertEqual(rates.shape, (37, 2))
                np.testing.assert_allclose(rates, 0.03)
                expected = 1.03 ** -(3 - np.arange(37) / 12)
                np.testing.assert_allclose(prices[0], expected)
                np.testing.assert_allclose(prices.iloc[-1], 1)

    def test_deterministic_mean_reversion_is_independent_of_observation_frequency(self):
        a, level, initial = 0.5, np.log1p(0.03), np.log1p(0.05)
        for path, module in self.modules.items():
            for frequency in (1, 12, 252):
                with self.subTest(module=path, frequency=frequency):
                    rates, prices = module.simulate_cir(n_years=2, n_scenarios=1, a=a,
                                                        b=0.03, r0=0.05, sigma=0, periods_per_year=frequency)
                    expected_rate = level + (initial - level) * np.exp(-a * 2)
                    self.assertAlmostEqual(np.log1p(rates.iloc[-1, 0]), expected_rate)
                    integrated_rate = level * 2 + (initial - level) * (1 - np.exp(-a * 2)) / a
                    self.assertAlmostEqual(prices.iloc[0, 0], np.exp(-integrated_rate))

    def test_affine_price_matches_the_textbook_formula_and_sigma_zero_limit(self):
        a, b, sigma, tau = 0.5, 0.03, 0.10, 5
        level = np.log1p(b)
        rates = np.array([0.01, 0.03, 0.05])
        h = np.sqrt(a * a + 2 * sigma * sigma)
        denominator = 2 * h + (a + h) * (np.exp(h * tau) - 1)
        A = (2 * h * np.exp((a + h) * tau / 2) / denominator) ** (2 * a * level / sigma ** 2)
        B = 2 * (np.exp(h * tau) - 1) / denominator
        expected = A * np.exp(-B * np.log1p(rates))
        for path, module in self.modules.items():
            with self.subTest(module=path):
                actual = module.cir_zero_coupon_price(tau, rates, a=a, b=b, sigma=sigma)
                np.testing.assert_allclose(actual, expected, rtol=1e-13)
                self.assertTrue((np.diff(actual) < 0).all())
                np.testing.assert_allclose(module.cir_zero_coupon_price(0, rates, a=a, b=b, sigma=sigma), 1)
                near_zero = module.cir_zero_coupon_price(5, rates, a=a, b=b, sigma=1e-8)
                deterministic = module.cir_zero_coupon_price(5, rates, a=a, b=b, sigma=0)
                np.testing.assert_allclose(near_zero, deterministic, atol=1e-12)

    def test_prices_use_current_rate_and_remaining_maturity(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                rates, prices = module.simulate_cir(n_years=2, n_scenarios=3, a=0.5,
                                                    b=0.03, r0=0.05, sigma=0.10, seed=42)
                for step in (0, 1, 12, 24):
                    expected = module.cir_zero_coupon_price(2 - step / 12, rates.iloc[step].to_numpy(),
                                                           a=0.5, b=0.03, sigma=0.10)
                    np.testing.assert_allclose(prices.iloc[step], expected, atol=1e-13)
                lagged = module.cir_zero_coupon_price(2 - 1 / 12, rates.iloc[0].to_numpy(), a=0.5, b=0.03, sigma=0.10)
                self.assertFalse(np.allclose(prices.iloc[1], lagged))

    def test_boundary_cases_remain_nonnegative_without_euler_clipping(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                rates, prices = module.simulate_cir(n_years=2, n_scenarios=50, a=0.05,
                                                    b=0.001, r0=0.01, sigma=0.30, seed=42)
                self.assertTrue(np.isfinite(rates.to_numpy()).all())
                self.assertTrue((rates >= 0).to_numpy().all())
                self.assertTrue(((prices > 0) & (prices <= 1 + 1e-12)).to_numpy().all())
                zero_rates, zero_prices = module.simulate_cir(n_years=1, n_scenarios=3,
                                                              a=0.5, b=0, r0=0, sigma=0.20, seed=42)
                np.testing.assert_allclose(zero_rates, 0)
                np.testing.assert_allclose(zero_prices, 1)

    def test_exact_transition_matches_conditional_mean_and_variance(self):
        module = self.modules["PortfolioOptimizationKit.py"]
        n, a, level, sigma, initial, dt = 50000, 0.5, np.log1p(0.03), 0.10, np.log1p(0.05), 0.25
        rates, _ = module.simulate_cir(n_years=dt, periods_per_year=4, n_scenarios=n,
                                       a=a, b=0.03, sigma=sigma, r0=0.05, seed=12345)
        sample = np.log1p(rates.iloc[-1].to_numpy())
        decay = np.exp(-a * dt)
        mean = level + (initial - level) * decay
        variance = initial * sigma ** 2 * decay * (1 - decay) / a + level * sigma ** 2 * (1 - decay) ** 2 / (2 * a)
        scale = sigma ** 2 * (1 - decay) / (4 * a)
        degrees = 4 * a * level / sigma ** 2
        noncentrality = decay * initial / scale
        fourth_moment = scale ** 4 * (48 * (degrees + 4 * noncentrality) + 12 * (degrees + 2 * noncentrality) ** 2)
        variance_se = np.sqrt((fourth_moment - (n - 3) / (n - 1) * variance ** 2) / n)
        self.assertLess(abs(sample.mean() - mean), 5 * np.sqrt(variance / n))
        self.assertLess(abs(sample.var(ddof=1) - variance), 5 * variance_se)

    def test_explicit_seed_is_reproducible_without_global_rng_changes(self):
        state = np.random.get_state()
        try:
            for path, module in self.modules.items():
                with self.subTest(module=path):
                    np.random.seed(19)
                    expected = np.random.random(3)
                    np.random.seed(19)
                    first = module.simulate_cir(n_years=1, n_scenarios=2, seed=42)
                    second = module.simulate_cir(n_years=1, n_scenarios=2, seed=42)
                    for actual, repeated in zip(first, second):
                        pd.testing.assert_frame_equal(actual, repeated)
                    np.testing.assert_array_equal(np.random.random(3), expected)
        finally:
            np.random.set_state(state)

    def test_cir_chart_units_dates_and_maturity_are_consistent(self):
        for path, module in self.modules.items():
            messages = []
            with self.subTest(module=path), patch.object(__main__, "_emit_echarts", messages.append, create=True):
                module.show_cir_echart()
                self.assertEqual(len(messages), 1)
                text, encoded = messages[0].split("<ECHARTS_DATA>")
                self.assertIn("Risk-neutral", text)
                chart = json.loads(encoded)
                rates, prices = module.simulate_cir(n_years=5, n_scenarios=5, a=0.5, b=0.03, sigma=0.10, r0=0.05, seed=42)
                for column in range(5):
                    rate_points = np.asarray(chart["cirRates"]["series"][f"Scenario {column + 1}"])
                    price_points = np.asarray(chart["cirBondPrices"]["series"][f"Scenario {column + 1}"])
                    np.testing.assert_allclose(rate_points[:, 0], np.arange(61) / 12)
                    np.testing.assert_allclose(rate_points[:, 1], np.log1p(rates[column]) * 100)
                    np.testing.assert_allclose(price_points[:, 1], prices[column])
                    np.testing.assert_allclose(price_points[-1], [5, 1])

    def test_invalid_model_parameters_are_rejected(self):
        for path, module in self.modules.items():
            for kwargs in ({"a": 0}, {"b": -0.01}, {"sigma": -0.1}, {"r0": -0.01},
                           {"n_years": 0.1}, {"n_scenarios": 0}, {"periods_per_year": None}):
                with self.subTest(module=path, kwargs=kwargs), self.assertRaises(ValueError):
                    module.simulate_cir(**kwargs)


if __name__ == "__main__":
    unittest.main()
