"""Independent checks of stock inputs, constrained solves, and frontier semantics."""

import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from test_return_annualization import MODULE_PATHS, ROOT


class PortfolioConstructionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules = {}
        for i, path in enumerate(MODULE_PATHS):
            spec = importlib.util.spec_from_file_location(f"construction_copy_{i}", ROOT / path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cls.modules[path] = module

    def test_stock_loader_preserves_price_units_and_trading_dates(self):
        for path, pok in self.modules.items():
            with self.subTest(module=path), patch.object(pok, "path_to_data_folder", return_value=str(ROOT / "data")):
                prices = pok.get_stock_dynamic()
                self.assertEqual(prices.shape, (3519, 3))
                self.assertEqual(prices.index[0], pd.Timestamp("2011-01-10"))
                self.assertEqual(prices.index[-1], pd.Timestamp("2025-01-03"))
                self.assertIsNone(prices.index.tz)
                np.testing.assert_allclose(prices.iloc[0], [9.23, 20.62, 21.73])
                self.assertEqual(len(pok.compute_returns(prices).dropna()), 3518)

    def test_stock_loader_rejects_missing_prices_and_duplicate_trading_dates(self):
        fixtures = [
            "Date,A\n2024-01-02,100\n2024-01-03,\n",
            "Date,A\n2024-01-02,100\n2024-01-02,101\n",
            "Date,A\n2024-01-02,100\n2024-01-03,0\n",
        ]
        with tempfile.TemporaryDirectory() as folder:
            for fixture in fixtures:
                (Path(folder) / "stocks_dynamic.csv").write_text(fixture)
                for path, pok in self.modules.items():
                    with self.subTest(module=path, fixture=fixture), patch.object(pok, "path_to_data_folder", return_value=folder):
                        with self.assertRaises(ValueError):
                            pok.get_stock_dynamic()

    def test_browser_stock_datasets_match_the_tested_snapshot(self):
        expected = pd.read_csv(ROOT / "data/stocks_dynamic.csv", index_col=0)
        for folder in ("assets/data", "public/assets/data", "docs/public/assets/data"):
            with self.subTest(folder=folder):
                pd.testing.assert_frame_equal(pd.read_csv(ROOT / folder / "stocks_dynamic.csv", index_col=0), expected)

    def test_gmv_and_tangent_weights_match_closed_form_solutions(self):
        means = pd.Series([0.08, 0.12], index=["A", "B"])
        covariance = pd.DataFrame([[0.01, 0.005], [0.005, 0.04]], index=means.index, columns=means.index)
        for path, pok in self.modules.items():
            with self.subTest(module=path):
                np.testing.assert_allclose(pok.minimize_volatility(means, covariance), [0.875, 0.125], atol=1e-5)
                np.testing.assert_allclose(pok.maximize_sharpe_ratio(means, covariance, 0.0, 1), [13 / 17, 4 / 17], atol=1e-5)
                np.testing.assert_allclose(pok.minimize_volatility(means, covariance, 0.10), [0.5, 0.5], atol=1e-7)
                # Solve 0.04*w^2 - 0.07*w + 0.04 = 0.15^2; only one root is long-only.
                weight_at_target_vol = (0.07 - np.sqrt(0.0021)) / 0.08
                np.testing.assert_allclose(
                    pok.maximize_sharpe_ratio(means, covariance, 0.0, 1, target_volatility=0.15),
                    [weight_at_target_vol, 1 - weight_at_target_vol], atol=1e-5,
                )

    def test_infeasible_targets_and_misaligned_assets_are_rejected(self):
        means = pd.Series([0.08, 0.12], index=["A", "B"])
        covariance = pd.DataFrame(np.eye(2), index=means.index, columns=means.index)
        for path, pok in self.modules.items():
            with self.subTest(module=path):
                with self.assertRaisesRegex(ValueError, "feasible long-only range"):
                    pok.minimize_volatility(means, covariance, target_return=0.20)
                with self.assertRaisesRegex(ValueError, "same asset order"):
                    pok.minimize_volatility(means, covariance.loc[["B", "A"], ["B", "A"]])
                with self.assertRaisesRegex(ValueError, "positive semidefinite"):
                    pok.minimize_volatility(np.array([0.08, 0.12]), np.array([[1.0, 2.0], [2.0, 1.0]]))

    def test_target_volatility_range_is_annual_and_excludes_zero_sharpe_denominator(self):
        means = np.array([0.08, 0.12])
        annual_covariance = np.array([[0.01, 0.005], [0.005, 0.04]])
        for path, pok in self.modules.items():
            for periods in (1, 12, 252):
                with self.subTest(module=path, periods=periods):
                    for target in (0.09, 0.21):
                        with self.assertRaisesRegex(ValueError, "feasible long-only range"):
                            pok.maximize_sharpe_ratio(means, annual_covariance / periods, 0.0, periods, target)
                    for target in (0.0, -0.1, np.nan, np.inf):
                        with self.assertRaisesRegex(ValueError, "positive and finite"):
                            pok.maximize_sharpe_ratio(means, annual_covariance / periods, 0.0, periods, target)
                    weights = pok.maximize_sharpe_ratio(means, annual_covariance / periods, 0.0, periods, 0.15)
                    self.assertAlmostEqual(weights @ annual_covariance @ weights, 0.15 ** 2, places=9)
            for rate in (np.nan, np.inf, -np.inf):
                with self.subTest(module=path, rate=rate), self.assertRaisesRegex(ValueError, "risk_free_rate must be finite"):
                    pok.maximize_sharpe_ratio(means, annual_covariance, rate, 1)

    def test_exact_volatility_selects_the_better_of_two_feasible_allocations(self):
        covariance = np.array([[0.01, 0.005], [0.005, 0.04]])
        # Both roots of 0.04*w_A^2 - 0.07*w_A + 0.04 = 0.099^2 lie in [0, 1].
        roots = np.roots([0.04, -0.07, 0.04 - 0.099 ** 2])
        for path, pok in self.modules.items():
            for means in (np.array([0.12, 0.08]), np.array([0.08, 0.12])):
                candidates = np.column_stack([roots, 1 - roots])
                expected = candidates[np.argmax(candidates @ means)]
                for rate in (0.0, 0.02):
                    with self.subTest(module=path, means=means, rate=rate):
                        weights = pok.maximize_sharpe_ratio(means, covariance, rate, 1, 0.099)
                        np.testing.assert_allclose(weights, expected, atol=1e-6)

    def test_exact_volatility_handles_a_constant_risk_surface(self):
        for path, pok in self.modules.items():
            with self.subTest(module=path):
                weights = pok.maximize_sharpe_ratio(np.array([0.08, 0.12]), np.full((2, 2), 0.01), 0.0, 1, 0.10)
                np.testing.assert_allclose(weights, [0.0, 1.0], atol=1e-7)

    def test_solver_failure_and_invalid_success_results_are_not_silenced(self):
        means = np.array([0.08, 0.12])
        covariance = np.diag([0.01, 0.04])
        outcomes = [
            SimpleNamespace(success=False, message="forced failure"),
            SimpleNamespace(success=True, x=np.array([0.7, 0.7]), fun=0.1),
            SimpleNamespace(success=True, x=np.array([np.nan, 1.0]), fun=0.1),
        ]
        for path, pok in self.modules.items():
            for outcome in outcomes:
                with self.subTest(module=path, outcome=outcome), patch.object(pok, "minimize", return_value=outcome):
                    with self.assertRaises(RuntimeError):
                        pok.minimize_volatility(means, covariance)
                    with self.assertRaises(RuntimeError):
                        pok.maximize_sharpe_ratio(means, covariance, 0.0, 1)

    def test_solver_success_still_requires_target_constraint_satisfaction(self):
        wrong_target = SimpleNamespace(success=True, x=np.array([0.5, 0.5]), fun=0.1)
        means = np.array([0.08, 0.12])
        covariance = np.diag([0.01, 0.04])
        for path, pok in self.modules.items():
            with self.subTest(module=path), patch.object(pok, "minimize", return_value=wrong_target):
                with self.assertRaisesRegex(RuntimeError, "target return"):
                    pok.minimize_volatility(means, covariance, target_return=0.11)
                with self.assertRaisesRegex(RuntimeError, "target volatility"):
                    pok.maximize_sharpe_ratio(means, covariance, 0.0, 1, target_volatility=0.15)

    def test_frontier_uses_arithmetic_moments_and_starts_at_gmv(self):
        returns = pd.DataFrame({"A": [0.01, 0.03, -0.01, 0.02], "B": [0.02, -0.01, 0.01, 0.04]})
        covariance = returns.cov()
        means = returns.mean() * 12
        closed_gmv = np.linalg.solve(covariance, np.ones(2))
        closed_gmv /= closed_gmv.sum()
        for path, pok in self.modules.items():
            with self.subTest(module=path):
                frontier = pok.efficient_frontier(5, returns, covariance, 12)
                weights = frontier[[0, 1]].to_numpy()
                self.assertEqual(len(frontier), 5)
                np.testing.assert_allclose(frontier["return"], weights @ means.to_numpy(), atol=1e-9)
                np.testing.assert_allclose(weights[0], closed_gmv, atol=1e-5)
                self.assertGreater(frontier["return"].iloc[0], means.min())
                self.assertAlmostEqual(frontier["return"].iloc[-1], means.max())
                self.assertTrue((frontier["volatility"].diff().dropna() >= -1e-9).all())
                self.assertTrue((frontier["return"].diff().dropna() >= -1e-9).all())

    def test_flat_variance_boundary_retains_only_the_highest_return(self):
        returns = pd.DataFrame({"A": [0.0, 0.20, 0.0, 0.20], "B": [0.05, 0.25, 0.05, 0.25]})
        for path, pok in self.modules.items():
            with self.subTest(module=path):
                frontier = pok.efficient_frontier(4, returns, returns.cov(), 1)
                self.assertEqual(len(frontier), 1)
                self.assertAlmostEqual(frontier["return"].iloc[0], 0.15)

    def test_frontier_rejects_partially_missing_observations(self):
        returns = pd.DataFrame({"A": [0.01, np.nan, 0.03], "B": [0.02, 0.01, 0.04]})
        for path, pok in self.modules.items():
            with self.subTest(module=path):
                with self.assertRaisesRegex(ValueError, "common sample"):
                    pok.efficient_frontier(4, returns, returns.cov(), 12)

    def test_plotting_optional_portfolios_preserves_frontier_column_names(self):
        returns = pd.DataFrame({"A": [0.01, 0.03, -0.01, 0.02], "B": [0.02, -0.01, 0.01, 0.04]})
        for path, pok in self.modules.items():
            with self.subTest(module=path):
                frontier, ax = pok.efficient_frontier(4, returns, returns.cov(), 12,
                                                     iplot=True, hsr=True, mvp=True, ewp=True)
                self.assertEqual(frontier.columns.tolist(), ["volatility", "return", "sharpe ratio", 0, 1])
                self.assertTrue(np.isfinite(frontier.to_numpy()).all())
                pok.plt.close(ax.figure)


if __name__ == "__main__":
    unittest.main()
