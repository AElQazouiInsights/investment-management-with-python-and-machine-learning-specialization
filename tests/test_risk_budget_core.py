"""Independent Euler identities, risk-budget solutions, and validation cases."""
import ast
import importlib.util
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from test_return_annualization import ROOT, MODULE_PATHS


class RiskBudgetCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules = {}
        for i, path in enumerate(MODULE_PATHS):
            spec = importlib.util.spec_from_file_location(f"risk_budget_copy_{i}", ROOT / path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cls.modules[path] = module

    def setUp(self):
        self.assets = pd.Index(["Equity", "Bonds"])
        self.covariance = pd.DataFrame([[0.04, 0.005], [0.005, 0.01]], index=self.assets, columns=self.assets)

    def test_reviewed_helpers_match_across_all_copies(self):
        names = {"_unit_shares", "enc", "encb", "risk_contribution_report", "portfolio_risk_contributions",
                 "msd_risk_contrib", "_risk_budget_solution", "portfolio_risk_contrib_optimizer",
                 "risk_parity_weigths", "weight_rp", "show_risk_parity_echart"}
        baseline = None
        for path in MODULE_PATHS:
            definitions = {node.name: ast.dump(node) for node in ast.parse((ROOT / path).read_text()).body
                           if isinstance(node, ast.FunctionDef) and node.name in names}
            self.assertEqual(set(definitions), names)
            if baseline is None:
                baseline = definitions
            with self.subTest(copy=path):
                self.assertEqual(definitions, baseline)

    def test_effective_counts_require_nonnegative_normalized_shares(self):
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                for helper in (pok.enc, pok.encb):
                    self.assertAlmostEqual(helper([0.25] * 4), 4)
                    self.assertAlmostEqual(helper([0.7, 0.1, 0.1, 0.1]), 1 / 0.52)
                    self.assertAlmostEqual(helper([1, 0, 0]), 1)
                    for bad in ([], [0, 0], [0.6, 0.6], [1.1, -0.1], [np.nan, 1], [np.inf, 0], [[0.5, 0.5]]):
                        with self.assertRaises(ValueError):
                            helper(bad)

    def test_euler_attribution_matches_worked_values_and_finite_differences(self):
        weights = np.array([0.5, 0.5])
        volatility = np.sqrt(0.015)
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                report = pok.risk_contribution_report(weights, self.covariance)
                np.testing.assert_allclose(report["Relative risk"], [0.75, 0.25])
                np.testing.assert_allclose(report["Component volatility"], np.array([0.01125, 0.00375]) / volatility)
                self.assertAlmostEqual(report["Component volatility"].sum(), volatility)
                for i in range(2):
                    shift = np.eye(2)[i] * 1e-6
                    upper, lower = weights + shift, weights - shift
                    finite_difference = (np.sqrt(upper @ self.covariance @ upper) - np.sqrt(lower @ self.covariance @ lower)) / 2e-6
                    self.assertAlmostEqual(report["Marginal volatility"].iloc[i], finite_difference, places=8)

    def test_exposure_and_covariance_scaling_obey_homogeneity(self):
        weights = pd.Series([0.6, 0.4], index=self.assets)
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                base = pok.risk_contribution_report(weights, self.covariance)
                levered = pok.risk_contribution_report(weights * 3, self.covariance)
                annualized = pok.risk_contribution_report(weights, self.covariance * 12)
                np.testing.assert_allclose(levered["Relative risk"], base["Relative risk"])
                np.testing.assert_allclose(levered["Component volatility"], base["Component volatility"] * 3)
                np.testing.assert_allclose(levered["Marginal volatility"], base["Marginal volatility"])
                np.testing.assert_allclose(annualized["Relative risk"], base["Relative risk"])
                np.testing.assert_allclose(annualized["Component volatility"], base["Component volatility"] * np.sqrt(12))

    def test_negative_hedge_contributions_are_retained_but_not_reported_as_counts(self):
        covariance = pd.DataFrame([[0.04, -0.018], [-0.018, 0.01]], index=self.assets, columns=self.assets)
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                shares = pok.portfolio_risk_contributions(np.array([0.9, 0.1]), covariance)
                np.testing.assert_allclose(shares, np.array([0.03078, -0.00152]) / 0.02926)
                self.assertAlmostEqual(shares.sum(), 1)
                with self.assertRaises(ValueError):
                    pok.encb(shares)

    def test_zero_risk_portfolios_and_missing_asset_labels_are_rejected(self):
        perfect_hedge = pd.DataFrame([[0.04, -0.02], [-0.02, 0.01]], index=self.assets, columns=self.assets)
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                for w, cov in (([0, 0], self.covariance), ([1/3, 2/3], perfect_hedge), ([0.5, 0.5], self.covariance * 0)):
                    with self.assertRaisesRegex(ValueError, "positive portfolio variance"):
                        pok.portfolio_risk_contributions(np.array(w), cov)
                with self.assertRaises(ValueError):
                    pok.portfolio_risk_contributions(pd.Series([0.5, 0.5], index=["Wrong", "Bonds"]), self.covariance)
                expected = pok.portfolio_risk_contributions(pd.Series([0.7, 0.3], index=self.assets), self.covariance)
                actual = pok.portfolio_risk_contributions(pd.Series([0.3, 0.7], index=self.assets[::-1]), self.covariance.iloc[:, ::-1])
                pd.testing.assert_series_equal(actual, expected)

    def test_equal_risk_contributors_can_still_share_one_factor(self):
        covariance = pd.DataFrame(0.04, index=list("ABCD"), columns=list("ABCD"))
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                shares = pok.portfolio_risk_contributions(np.repeat(0.25, 4), covariance)
                self.assertAlmostEqual(pok.encb(shares), 4)
                self.assertEqual(np.linalg.matrix_rank(covariance), 1)
                self.assertAlmostEqual(pok.portfolio_volatility(np.repeat(0.25, 4), covariance), 0.20)

    def test_two_asset_erc_equals_inverse_volatility_for_all_nondegenerate_correlations(self):
        for path, pok in self.modules.items():
            for correlation in (-0.9, 0, 0.25, 0.9):
                covariance = pd.DataFrame([[0.04, correlation * 0.02], [correlation * 0.02, 0.01]], index=self.assets, columns=self.assets)
                with self.subTest(copy=path, correlation=correlation):
                    weights = pok.risk_parity_weigths(covariance)
                    self.assertEqual(weights.index.tolist(), self.assets.tolist())
                    np.testing.assert_allclose(weights, [1/3, 2/3], atol=1e-8)
                    np.testing.assert_allclose(pok.portfolio_risk_contributions(weights, covariance), [0.5, 0.5], atol=1e-8)

    def test_diagonal_unequal_budgets_have_sqrt_budget_inverse_vol_solution(self):
        labels = pd.Index(list("ABC"))
        volatilities = np.array([0.1, 0.2, 0.3])
        covariance = pd.DataFrame(np.diag(volatilities ** 2), index=labels, columns=labels)
        budgets = pd.Series([0.2, 0.3, 0.5], index=labels)
        expected = np.sqrt(budgets) / volatilities
        expected /= expected.sum()
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                for scale in (1e-6, 1, 12, 1e6):
                    np.testing.assert_allclose(pok.portfolio_risk_contrib_optimizer(budgets.iloc[::-1], covariance * scale), expected, atol=1e-9)

    def test_correlated_budget_solution_matches_an_independently_constructed_optimum(self):
        weights = np.array([0.2, 0.3, 0.5])
        budgets = np.array([0.1, 0.2, 0.7])
        covariance = np.full((3, 3), 0.1)
        np.fill_diagonal(covariance, (budgets / weights - 0.1 * (1 - weights)) / weights)
        covariance = pd.DataFrame(covariance * 0.01, index=list("ABC"), columns=list("ABC"))
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                actual = pok.portfolio_risk_contrib_optimizer(budgets, covariance)
                np.testing.assert_allclose(actual, weights, atol=1e-8)
                self.assertLess(pok.msd_risk_contrib(actual, budgets, covariance), 1e-15)
                with self.assertRaises(ValueError):
                    pok.msd_risk_contrib(actual, [0.5, 0.5], covariance)

    def test_positive_budget_solver_rejects_singular_covariance_and_infeasible_budgets(self):
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                for cov in (self.covariance * 0, pd.DataFrame(0.04, index=self.assets, columns=self.assets)):
                    with self.assertRaisesRegex(ValueError, "positive-definite"):
                        pok.risk_parity_weigths(cov)
                for budget in ([0, 1], [-0.1, 1.1], [0.4, 0.4], [np.nan, 1], [1]):
                    with self.assertRaises(ValueError):
                        pok.portfolio_risk_contrib_optimizer(budget, self.covariance)

    def test_failed_or_unverified_numerical_solutions_are_not_returned(self):
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                for result in (np.array([np.nan, 1]), np.array([-1, 2]), np.array([1]), np.ones(2)):
                    with patch.object(pok, "_risk_budget_solution", return_value=result), self.assertRaises(RuntimeError):
                        pok.risk_parity_weigths(self.covariance)
                with patch.object(pok.np.linalg, "solve", return_value=np.zeros(2)), self.assertRaisesRegex(RuntimeError, "did not converge"):
                    pok.risk_parity_weigths(self.covariance)

    def test_weight_rule_preserves_labels_and_observation_timing(self):
        returns = pd.DataFrame(np.random.default_rng(4).normal(0.01, [0.02, 0.01], (10, 2)), columns=self.assets)
        expected = []
        for t in range(4, len(returns)):
            inverse_vol = 1 / returns.iloc[t-4:t].std(ddof=1)
            expected.append(returns.iloc[t] @ (inverse_vol / inverse_vol.sum()))
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                actual = pok.backtest_weight_scheme(returns, window=4, weight_scheme=pok.weight_rp)
                self.assertTrue(actual.iloc[:4].isna().all())
                np.testing.assert_allclose(actual.iloc[4:], expected, atol=1e-8)

    def test_widget_payloads_keep_capital_weights_and_signed_risk_shares_distinct(self):
        for path, pok in self.modules.items():
            captures = []
            with self.subTest(copy=path), patch.object(pok, "_publish_echarts", side_effect=lambda plots, text: captures.append(plots)):
                pok.show_risk_parity_echart()
                np.testing.assert_allclose(captures[-1]["riskParityWeights"]["series"]["Risk budget"], [100/3, 200/3])
                np.testing.assert_allclose(captures[-1]["riskParityShares"]["series"]["Risk budget"], [50, 50])
                np.testing.assert_allclose(captures[-1]["riskParityShares"]["series"]["EW"], [75, 25])
                pok.show_risk_parity_echart(correlation=-0.9, equity_budget=0.1)
                self.assertLess(captures[-1]["riskParityShares"]["series"]["EW"][1], 0)
                np.testing.assert_allclose(captures[-1]["riskParityShares"]["series"]["Risk budget"], [10, 90], atol=1e-6)


if __name__ == "__main__":
    unittest.main()
