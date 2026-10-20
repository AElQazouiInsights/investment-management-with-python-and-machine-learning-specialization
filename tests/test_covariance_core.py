"""Independent identities and edge cases for covariance-based allocations."""

import ast
import importlib.util
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from test_return_annualization import ROOT, MODULE_PATHS


class CovarianceCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules = {}
        for i, path in enumerate(MODULE_PATHS):
            spec = importlib.util.spec_from_file_location(f"covariance_copy_{i}", ROOT / path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cls.modules[path] = module

    def test_reviewed_helper_definitions_match_all_published_copies(self):
        names = {"_covariance_returns", "sample_cov", "cc_cov", "shrinkage_cov", "annualize_vol_ewa", "weight_minvar"}
        baseline = None
        for path in MODULE_PATHS:
            definitions = {node.name: ast.dump(node) for node in ast.parse((ROOT / path).read_text()).body
                           if isinstance(node, ast.FunctionDef) and node.name in names}
            self.assertEqual(set(definitions), names)
            if baseline is None:
                baseline = definitions
            with self.subTest(copy=path):
                self.assertEqual(definitions, baseline)

    def test_sample_covariance_matches_hand_calculation_and_preserves_asset_order(self):
        r = pd.DataFrame({"A": [-0.02, 0.0, 0.02], "B": [0.01, -0.01, 0.0]})
        expected = np.array([[0.0004, -0.0001], [-0.0001, 0.0001]])
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                result = pok.sample_cov(r)
                self.assertEqual(result.columns.tolist(), ["A", "B"])
                np.testing.assert_allclose(result, expected)
                np.testing.assert_allclose(pok.sample_cov(r[["B", "A"]]), expected[::-1, ::-1])
                self.assertAlmostEqual(np.array([0.6, 0.4]) @ result @ np.array([0.6, 0.4]), 0.000112)

    def test_pairwise_missing_data_can_be_indefinite_and_are_rejected(self):
        r = pd.DataFrame({"A": [1, -1, 1, -1, np.nan, np.nan],
                          "B": [1, -1, np.nan, np.nan, 1, -1],
                          "C": [np.nan, np.nan, 1, -1, -1, 1]})
        self.assertLess(np.linalg.eigvalsh(r.cov()).min(), 0)
        for path, pok in self.modules.items():
            for estimator in (pok.sample_cov, pok.cc_cov, pok.shrinkage_cov):
                with self.subTest(copy=path, estimator=estimator.__name__), self.assertRaisesRegex(ValueError, "common sample"):
                    estimator(r)

    def test_covariance_rejects_nonfinite_insufficient_and_duplicate_inputs(self):
        r = pd.DataFrame({"A": [0.01, 0.02, -0.01], "B": [0.02, -0.01, 0.01]})
        fixtures = [r.iloc[:1], r.iloc[:, :0], r.assign(A=np.inf), r.set_axis([0, 0, 1]),
                    r.set_axis(["A", "A"], axis=1)]
        for path, pok in self.modules.items():
            for estimator in (pok.sample_cov, pok.cc_cov, pok.shrinkage_cov):
                for fixture in fixtures:
                    with self.subTest(copy=path, estimator=estimator.__name__), self.assertRaises(ValueError):
                        estimator(fixture)

    def test_constant_correlation_averages_unique_pairs_and_preserves_diagonal(self):
        r = pd.DataFrame({"A": [0.02, -0.01, 0.03, 0.0, 0.01],
                          "B": [0.01, 0.03, -0.02, -0.01, 0.0],
                          "C": [-0.03, -0.01, 0.02, 0.04, 0.0]})
        covariance = np.cov(r.to_numpy(), rowvar=False, ddof=1)
        std = np.sqrt(np.diag(covariance))
        rho = (covariance[0, 1] / (std[0]*std[1]) + covariance[0, 2] / (std[0]*std[2])
               + covariance[1, 2] / (std[1]*std[2])) / 3
        expected = rho * np.outer(std, std)
        np.fill_diagonal(expected, std ** 2)
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                np.testing.assert_allclose(pok.cc_cov(r), expected, atol=1e-15)
                self.assertGreaterEqual(np.linalg.eigvalsh(pok.cc_cov(r)).min(), -1e-15)

    def test_constant_single_and_two_asset_cases_have_defined_covariance(self):
        r = pd.DataFrame({"A": [-0.02, 0, 0.02], "B": [0.01, -0.01, 0]})
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                np.testing.assert_allclose(pok.cc_cov(r), np.cov(r, rowvar=False))
                np.testing.assert_allclose(pok.cc_cov(r[["A"]]), [[0.0004]])
                extended = pok.cc_cov(r.assign(Cash=0.003))
                np.testing.assert_allclose(extended.loc[["A", "B"], ["A", "B"]], pok.cc_cov(r))
                np.testing.assert_array_equal(extended.loc["Cash"], [0, 0, 0])
                np.testing.assert_array_equal(pok.cc_cov(r * 0 + 0.003), np.zeros((2, 2)))

    def test_shrinkage_endpoints_convex_blend_and_positive_definiteness(self):
        r = pd.DataFrame(np.random.default_rng(12).normal(0, 0.02, (6, 12)))
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                sample, target = pok.sample_cov(r), pok.cc_cov(r)
                self.assertLessEqual(np.linalg.matrix_rank(sample), 5)
                np.testing.assert_allclose(pok.shrinkage_cov(r, delta=0), sample, atol=1e-15)
                np.testing.assert_allclose(pok.shrinkage_cov(r, delta=1), target, atol=1e-15)
                blended = pok.shrinkage_cov(r, delta=0.3)
                np.testing.assert_allclose(blended, 0.7 * sample + 0.3 * target, atol=1e-15)
                np.testing.assert_allclose(np.diag(blended), np.diag(sample))
                self.assertGreater(np.linalg.eigvalsh(blended).min(), 0)
                for delta in (-0.1, 1.1, np.inf, np.nan):
                    with self.assertRaisesRegex(ValueError, "delta"):
                        pok.shrinkage_cov(r, delta=delta)

    def test_ewa_named_date_indexed_series_matches_normalized_weighted_moment(self):
        r = pd.Series([-0.02, 0, 0.02], index=pd.period_range("2024-01", periods=3, freq="M"), name="Named asset")
        expected_variance = 5 / 7 * 0.02 ** 2
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                self.assertAlmostEqual(pok.annualize_vol_ewa(r, decay=0.5), np.sqrt(12 * expected_variance))
                self.assertAlmostEqual(pok.annualize_vol_ewa(r + 0.1, decay=0.5), np.sqrt(12 * expected_variance))
                self.assertAlmostEqual(pok.annualize_vol_ewa(r, decay=1), np.std(r, ddof=0) * np.sqrt(12))
                frame = pd.DataFrame({"First": r, "Second": 2 * r})
                values = pok.annualize_vol_ewa(frame, decay=0.5)
                self.assertEqual(values.index.tolist(), ["First", "Second"])
                np.testing.assert_allclose(values, np.sqrt(12 * expected_variance) * np.array([1, 2]))

    def test_ewa_is_sensitive_to_order_but_annualization_depends_only_on_frequency(self):
        r = pd.Series([0.01, -0.01, 0, 0.10])
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                forward = pok.annualize_vol_ewa(r, decay=0.5, periods_per_year=1)
                reverse = pok.annualize_vol_ewa(pd.Series(r.to_numpy()[::-1]), decay=0.5, periods_per_year=1)
                self.assertGreater(forward, reverse)
                self.assertAlmostEqual(pok.annualize_vol_ewa(r, decay=0.5, periods_per_year=252), forward * np.sqrt(252))

    def test_ewa_rejects_invalid_parameters_and_incomplete_or_unordered_history(self):
        r = pd.Series([0.01, -0.01, 0.02])
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                for decay in (0, -0.5, 1.1, np.nan, np.inf):
                    with self.assertRaises(ValueError):
                        pok.annualize_vol_ewa(r, decay=decay)
                for frequency in (0, -1, np.nan, np.inf):
                    with self.assertRaises(ValueError):
                        pok.annualize_vol_ewa(r, periods_per_year=frequency)
                for fixture in (r.iloc[:0], r.iloc[::-1], r.mask(r == 0.02), r * np.inf):
                    with self.assertRaises(ValueError):
                        pok.annualize_vol_ewa(fixture)

    def test_minvar_returns_labeled_closed_form_weights_without_a_return_forecast(self):
        r = pd.DataFrame({"A": [0.01, 0.03, -0.01], "B": [0.02, -0.01, 0.03]})
        covariance = pd.DataFrame([[0.01, 0.005], [0.005, 0.04]], index=r.columns, columns=r.columns)
        for path, pok in self.modules.items():
            with self.subTest(copy=path), patch.object(pok, "annualize_rets", side_effect=AssertionError("GMV needs no mean forecast")):
                for frequency in (1, 12, 252):
                    weights = pok.weight_minvar(r, periods_per_year=frequency, cov_estimator=lambda _: covariance)
                    self.assertIsInstance(weights, pd.Series)
                    self.assertEqual(weights.index.tolist(), ["A", "B"])
                    np.testing.assert_allclose(weights, [0.875, 0.125], atol=1e-7)
                    scaled = pok.weight_minvar(r, cov_estimator=lambda _: covariance * frequency)
                    np.testing.assert_allclose(weights, scaled, atol=1e-7)

    def test_minvar_handles_singular_hedges_and_zero_variance(self):
        r = pd.DataFrame({"A": [-0.02, 0, 0.02], "B": [0.02, 0, -0.02]})
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                np.testing.assert_allclose(pok.weight_minvar(r), [0.5, 0.5], atol=1e-7)
                np.testing.assert_allclose(pok.weight_minvar(r * 0), [0.5, 0.5])
                np.testing.assert_allclose(pok.weight_minvar(r.assign(B=0.0)), [0, 1], atol=1e-7)
                np.testing.assert_allclose(pok.weight_minvar(r[["A"]]), [1])

    def test_minvar_rejects_invalid_covariance_order_and_solver_results(self):
        r = pd.DataFrame({"A": [-0.02, 0, 0.02], "B": [0.01, -0.01, 0]})
        outcomes = [SimpleNamespace(success=False, message="forced failure"),
                    SimpleNamespace(success=True, x=np.array([0.7, 0.7]), fun=0.1),
                    SimpleNamespace(success=True, x=np.array([0.5, 0.5]), fun=np.nan)]
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                with self.assertRaisesRegex(ValueError, "same asset order"):
                    pok.weight_minvar(r, cov_estimator=lambda x: x.cov().loc[["B", "A"], ["B", "A"]])
                with self.assertRaisesRegex(ValueError, "positive semidefinite"):
                    pok.weight_minvar(r, cov_estimator=lambda _: np.array([[1, 2], [2, 1]]))
                for outcome in outcomes:
                    with patch.object(pok, "minimize", return_value=outcome), self.assertRaises(RuntimeError):
                        pok.weight_minvar(r)

    def test_minvar_backtest_matches_two_asset_closed_form_using_prior_window_only(self):
        r = pd.DataFrame(np.random.default_rng(13).normal(0.01, 0.03, (12, 2)), columns=["A", "B"])
        expected = []
        for t in range(4, len(r)):
            cov = np.cov(r.iloc[t-4:t], rowvar=False)
            weight_a = np.clip((cov[1, 1] - cov[0, 1]) / (cov[0, 0] + cov[1, 1] - 2 * cov[0, 1]), 0, 1)
            expected.append(weight_a * r.iloc[t, 0] + (1 - weight_a) * r.iloc[t, 1])
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                actual = pok.backtest_weight_scheme(r, window=4, weight_scheme=pok.weight_minvar)
                self.assertTrue(actual.iloc[:4].isna().all())
                np.testing.assert_allclose(actual.iloc[4:], expected, atol=1e-8)
                changed = r.copy()
                changed.iloc[-1] = [0.9, -0.5]
                revised = pok.backtest_weight_scheme(changed, window=4, weight_scheme=pok.weight_minvar)
                np.testing.assert_allclose(revised.iloc[:-1], actual.iloc[:-1])


if __name__ == "__main__":
    unittest.main()
