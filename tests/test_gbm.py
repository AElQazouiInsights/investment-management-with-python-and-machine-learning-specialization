"""Analytical limits, paired shocks, and distribution checks for GBM simulators."""

import importlib.util
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from test_return_annualization import MODULE_PATHS, ROOT


class GbmTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules = {}
        for i, path in enumerate(MODULE_PATHS):
            spec = importlib.util.spec_from_file_location(f"gbm_copy_{i}", ROOT / path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cls.modules[path] = module

    def test_zero_volatility_matches_continuous_and_discrete_compounding(self):
        for path, module in self.modules.items():
            for frequency in (1, 12, 252):
                with self.subTest(module=path, frequency=frequency):
                    inputs = dict(n_years=2, n_scenarios=2, mu=0.07, sigma=0, periods_per_year=frequency, start=100, seed=7)
                    euler, simple = module.simulate_gbm_from_returns(**inputs)
                    exact, logs = module.simulate_gbm_from_prices(**inputs)
                    steps = np.arange(2 * frequency + 1)
                    self.assertEqual(euler.shape, (2 * frequency + 1, 2))
                    self.assertEqual(exact.shape, euler.shape)
                    self.assertEqual(simple.shape, (2 * frequency, 2))
                    self.assertEqual(logs.shape, simple.shape)
                    np.testing.assert_allclose(euler[0], 100 * (1 + 0.07 / frequency) ** steps)
                    np.testing.assert_allclose(exact[0], 100 * np.exp(0.07 * steps / frequency))
                    np.testing.assert_allclose(simple, 0.07 / frequency)
                    np.testing.assert_allclose(logs, 0.07 / frequency)
                    self.assertEqual(simple.index[0], 0)
                    self.assertEqual(logs.index[0], 1)

    def test_paired_methods_share_shocks_and_returns_reconcile_with_prices(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                inputs = dict(n_years=1, n_scenarios=4, mu=0.07, sigma=0.15, periods_per_year=12, seed=42)
                euler, simple = module.simulate_gbm_from_returns(**inputs)
                exact, logs = module.simulate_gbm_from_prices(**inputs)
                # Same shocks imply this deterministic difference between the two increments.
                np.testing.assert_allclose(simple.to_numpy() - logs.to_numpy(), 0.15 ** 2 / 24, atol=1e-15)
                np.testing.assert_allclose(euler.pct_change().iloc[1:].to_numpy(), simple, atol=1e-14)
                np.testing.assert_allclose(exact.pct_change().iloc[1:].to_numpy(), np.expm1(logs), atol=1e-14)
                np.testing.assert_allclose(exact.iloc[-1], 100 * np.exp(logs.sum()))
                np.testing.assert_allclose(euler.iloc[0], 100)
                np.testing.assert_allclose(exact.iloc[0], 100)

    def test_explicit_seed_is_reproducible_without_changing_global_rng(self):
        state = np.random.get_state()
        try:
            for path, module in self.modules.items():
                for function in (module.simulate_gbm_from_returns, module.simulate_gbm_from_prices):
                    with self.subTest(module=path, function=function.__name__):
                        np.random.seed(101)
                        expected_next = np.random.standard_normal(3)
                        np.random.seed(101)
                        first, _ = function(n_years=1, n_scenarios=2, seed=42)
                        second, _ = function(n_years=1, n_scenarios=2, seed=42)
                        pd.testing.assert_frame_equal(first, second)
                        np.testing.assert_array_equal(np.random.standard_normal(3), expected_next)
                        np.random.seed(13)
                        legacy_first, _ = function(n_years=1, n_scenarios=2)
                        np.random.seed(13)
                        legacy_second, _ = function(n_years=1, n_scenarios=2)
                        pd.testing.assert_frame_equal(legacy_first, legacy_second)
        finally:
            np.random.set_state(state)

    def test_exact_transition_stays_positive_when_euler_step_is_invalid(self):
        for path, module in self.modules.items():
            with self.subTest(module=path), patch.object(module.np.random, "standard_normal", return_value=np.array([[-3.0]])):
                with self.assertRaisesRegex(ValueError, "Euler approximation produced an invalid return"):
                    module.simulate_gbm_from_returns(n_years=1, n_scenarios=1, periods_per_year=1, mu=0.07, sigma=0.50)
                exact, logs = module.simulate_gbm_from_prices(n_years=1, n_scenarios=1, periods_per_year=1, mu=0.07, sigma=0.50)
                self.assertAlmostEqual(logs.iloc[0, 0], -1.555)
                self.assertAlmostEqual(exact.iloc[-1, 0], 21.118938264097117)

    def test_invalid_parameters_and_fractional_periods_are_rejected(self):
        invalid_inputs = [dict(n_years=0), dict(n_years=0.1), dict(n_scenarios=0),
                          dict(n_scenarios=1.5), dict(n_scenarios=True), dict(periods_per_year=0),
                          dict(mu=np.nan), dict(sigma=-0.1), dict(sigma=np.inf), dict(start=0)]
        for path, module in self.modules.items():
            for function in (module.simulate_gbm_from_returns, module.simulate_gbm_from_prices):
                for inputs in invalid_inputs:
                    with self.subTest(module=path, function=function.__name__, inputs=inputs), self.assertRaises(ValueError):
                        function(**inputs)
                with self.subTest(module=path, function=function.__name__, partial_year=True):
                    prices, returns = function(n_years=0.5, n_scenarios=2, seed=7)
                    self.assertEqual(prices.shape, (7, 2))
                    self.assertEqual(returns.shape, (6, 2))

    def test_exact_underflow_or_overflow_does_not_return_invalid_prices(self):
        for path, module in self.modules.items():
            for drift in (-1000, 1000):
                with self.subTest(module=path, drift=drift), self.assertRaisesRegex(ValueError, "nonfinite or nonpositive prices"):
                    module.simulate_gbm_from_prices(n_years=1, n_scenarios=1, periods_per_year=1, mu=drift, sigma=0, seed=7)

    def test_exact_population_moments_and_brownian_level_covariance(self):
        module = self.modules["PortfolioOptimizationKit.py"]
        n = 30000
        mu, sigma, horizon = 0.07, 0.15, 2
        prices, logs = module.simulate_gbm_from_prices(n_years=horizon, n_scenarios=n,
                                                     mu=mu, sigma=sigma, periods_per_year=4, seed=12345)
        terminal_log = logs.sum().to_numpy()
        log_mean = (mu - sigma ** 2 / 2) * horizon
        log_variance = sigma ** 2 * horizon
        self.assertLess(abs(terminal_log.mean() - log_mean), 5 * np.sqrt(log_variance / n))
        self.assertLess(abs(terminal_log.var(ddof=1) - log_variance), 5 * log_variance * np.sqrt(2 / (n - 1)))
        expected_mean = 100 * np.exp(mu * horizon)
        expected_std = expected_mean * np.sqrt(np.expm1(sigma ** 2 * horizon))
        self.assertLess(abs(prices.iloc[-1].mean() - expected_mean), 5 * expected_std / np.sqrt(n))
        # Recover W at t=0.5 and t=1.0: covariance should be min(0.5, 1.0).
        w_half = (np.log(prices.iloc[2].to_numpy() / 100) - (mu - sigma ** 2 / 2) * 0.5) / sigma
        w_one = (np.log(prices.iloc[4].to_numpy() / 100) - (mu - sigma ** 2 / 2)) / sigma
        covariance = np.cov(w_half, w_one)[0, 1]
        self.assertLess(abs(covariance - 0.5), 5 * np.sqrt(0.75 / n))

    def test_exact_simple_returns_can_be_passed_to_cppi(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                prices, logs = module.simulate_gbm_from_prices(n_years=1, n_scenarios=3, seed=42)
                result = module.cppi(np.expm1(logs), start_value=100, floor=0, m=1)
                np.testing.assert_allclose(result["CPPI wealth"], prices.iloc[1:], atol=1e-12)


if __name__ == "__main__":
    unittest.main()
