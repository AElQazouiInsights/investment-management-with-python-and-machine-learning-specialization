"""Independent Gaussian conditioning, allocation, and labeling checks."""
import ast
import importlib.util
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from test_return_annualization import ROOT, MODULE_PATHS


class BlackLittermanCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules = {}
        for i, path in enumerate(MODULE_PATHS):
            spec = importlib.util.spec_from_file_location(f"bl_copy_{i}", ROOT / path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cls.modules[path] = module

    def setUp(self):
        self.assets = pd.Index(["Equity", "Bonds"])
        self.sigma = pd.DataFrame([[0.04, 0.006], [0.006, 0.01]], index=self.assets, columns=self.assets)
        self.weights = pd.Series([0.6, 0.4], index=self.assets)
        self.P = pd.DataFrame([[1., -1.]], index=["Spread"], columns=self.assets)
        self.Q = pd.Series([0.08], index=self.P.index)

    def test_all_reviewed_definitions_match_across_six_copies(self):
        names = {"_bl_matrix", "_bl_vector", "_bl_views", "implied_returns", "omega_uncertain_prior",
                 "black_litterman", "bl_portfolio_weights", "show_black_litterman_echart"}
        baseline = None
        for path in MODULE_PATHS:
            definitions = {node.name: ast.dump(node) for node in ast.parse((ROOT / path).read_text()).body
                           if isinstance(node, ast.FunctionDef) and node.name in names}
            self.assertEqual(set(definitions), names)
            if baseline is None:
                baseline = definitions
            with self.subTest(copy=path):
                self.assertEqual(definitions, baseline)

    def test_reverse_optimization_and_default_omega_match_hand_calculations(self):
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                pi = pok.implied_returns(self.sigma, self.weights)
                np.testing.assert_allclose(pi, [0.066, 0.019])
                np.testing.assert_allclose(np.linalg.solve(self.sigma, pi) / 2.5, self.weights)
                np.testing.assert_allclose(pok.omega_uncertain_prior(self.sigma, 0.05, self.P), [[0.0019]])

    def test_single_view_update_and_predictive_covariance_are_distinct(self):
        cross = np.array([0.0017, -0.0002])
        expected_mean = np.array([0.066, 0.019]) + cross / 0.0038 * 0.033
        expected_M = 0.05 * self.sigma.to_numpy() - np.outer(cross, cross) / 0.0038
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                mean, predictive = pok.black_litterman(self.weights, self.sigma, self.P, self.Q, tau=0.05)
                np.testing.assert_allclose(mean, expected_mean, atol=1e-13)
                np.testing.assert_allclose(predictive - self.sigma, expected_M, atol=1e-13)
                self.assertAlmostEqual(float((self.P @ mean).iloc[0]), 0.0635)
                self.assertAlmostEqual(np.array([1, -1]) @ expected_M @ np.array([1, -1]), 0.00095)

    def test_multiple_correlated_views_match_the_independent_precision_formula(self):
        P = pd.DataFrame([[1., 0.], [1., -1.]], index=["Absolute", "Spread"], columns=self.assets)
        Q = pd.Series([0.08, 0.04], index=P.index)
        omega = pd.DataFrame([[0.002, 0.0003], [0.0003, 0.001]], index=P.index, columns=P.index)
        C = 0.05 * self.sigma.to_numpy()
        prior = 2.5 * self.sigma.to_numpy() @ self.weights.to_numpy()
        precision = np.linalg.inv(C) + P.to_numpy().T @ np.linalg.solve(omega, P)
        M = np.linalg.inv(precision)
        mean = M @ (np.linalg.solve(C, prior) + P.to_numpy().T @ np.linalg.solve(omega, Q))
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                actual_mean, predictive = pok.black_litterman(self.weights, self.sigma, P, Q, omega, tau=0.05)
                np.testing.assert_allclose(actual_mean, mean, atol=1e-12)
                np.testing.assert_allclose(predictive, self.sigma + M, atol=1e-12)
                self.assertGreaterEqual(np.linalg.eigvalsh(C - M).min(), -1e-12)
                self.assertGreaterEqual(np.linalg.eigvalsh(M).min(), -1e-12)

    def test_asset_and_view_permutations_align_by_label_without_mutating_inputs(self):
        P = pd.DataFrame([[1., 0.], [1., -1.]], index=["Absolute", "Spread"], columns=self.assets)
        Q = pd.Series([0.08, 0.04], index=P.index)
        omega = pd.DataFrame([[0.002, 0.0003], [0.0003, 0.001]], index=P.index, columns=P.index)
        original = self.sigma.copy()
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                expected = pok.black_litterman(self.weights, self.sigma, P, Q, omega)
                actual = pok.black_litterman(self.weights.iloc[::-1].to_frame(), self.sigma.iloc[::-1, :],
                                             P.iloc[::-1, ::-1], Q.to_frame(), omega.iloc[:, ::-1])
                pd.testing.assert_series_equal(actual[0].reindex(self.assets), expected[0])
                pd.testing.assert_frame_equal(actual[1].reindex(index=self.assets, columns=self.assets), expected[1])
                pd.testing.assert_frame_equal(self.sigma, original)

    def test_one_asset_returns_labeled_objects_instead_of_squeezing_to_a_scalar(self):
        sigma = pd.DataFrame([[0.04]], index=["Only"], columns=["Only"])
        weight = pd.Series([1.], index=sigma.index)
        P = pd.DataFrame([[1.]], index=["Absolute"], columns=sigma.index)
        Q = pd.Series([0.12], index=P.index)
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                self.assertIsInstance(pok.implied_returns(sigma, weight), pd.Series)
                mean, predictive = pok.black_litterman(weight.to_frame(), sigma, P, Q.to_frame(), tau=0.05)
                self.assertEqual(mean.index.tolist(), ["Only"])
                self.assertAlmostEqual(mean.iloc[0], 0.11)
                self.assertAlmostEqual(predictive.iloc[0, 0], 0.041)
                np.testing.assert_allclose(pok.bl_portfolio_weights(mean, predictive), [1])

    def test_no_views_and_uninformative_views_recover_prior_beliefs(self):
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                mean, predictive = pok.black_litterman(self.weights, self.sigma, self.P.iloc[:0], self.Q.iloc[:0], tau=0.05)
                np.testing.assert_allclose(mean, [0.066, 0.019])
                np.testing.assert_allclose(predictive, 1.05 * self.sigma)
                weak = pd.DataFrame([[1e8]], index=self.P.index, columns=self.P.index)
                weak_mean, weak_pred = pok.black_litterman(self.weights, self.sigma, self.P, self.Q, weak, tau=0.05)
                np.testing.assert_allclose(weak_mean, mean, atol=1e-10)
                np.testing.assert_allclose(weak_pred, predictive, atol=1e-10)

    def test_exact_view_sets_expected_spread_not_realized_return_risk(self):
        omega = pd.DataFrame([[0.]], index=self.P.index, columns=self.P.index)
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                mean, predictive = pok.black_litterman(self.weights, self.sigma, self.P, self.Q, omega, tau=0.05)
                self.assertAlmostEqual(float((self.P @ mean).iloc[0]), 0.08)
                self.assertAlmostEqual(float((self.P @ (predictive - self.sigma) @ self.P.T).iloc[0, 0]), 0)
                self.assertAlmostEqual(float((self.P @ predictive @ self.P.T).iloc[0, 0]), 0.038)

    def test_redundant_exact_views_are_rejected_but_noisy_views_are_supported(self):
        P = pd.DataFrame([[1., -1.], [2., -2.]], index=["First", "Duplicate"], columns=self.assets)
        Q = pd.Series([0.08, 0.16], index=P.index)
        zero = pd.DataFrame(0., index=P.index, columns=P.index)
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                with self.assertRaisesRegex(ValueError, "Singular view system"):
                    pok.black_litterman(self.weights, self.sigma, P, Q, zero)
                mean, covariance = pok.black_litterman(self.weights, self.sigma, P, Q)
                self.assertTrue(np.isfinite(mean).all())
                self.assertGreaterEqual(np.linalg.eigvalsh(covariance).min(), 0)

    def test_consistent_signal_preserves_mean_but_reduces_uncertainty(self):
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                pi = pok.implied_returns(self.sigma, self.weights)
                mean, predictive = pok.black_litterman(self.weights, self.sigma, self.P, self.P @ pi, tau=0.05)
                np.testing.assert_allclose(mean, pi, atol=1e-14)
                self.assertLess(np.trace(predictive - self.sigma), np.trace(0.05 * self.sigma))

    def test_tau_cancellation_requires_proportional_view_uncertainty(self):
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                mean1, pred1 = pok.black_litterman(self.weights, self.sigma, self.P, self.Q, tau=0.05)
                mean2, pred2 = pok.black_litterman(self.weights, self.sigma, self.P, self.Q, tau=0.20)
                np.testing.assert_allclose(mean1, mean2)
                np.testing.assert_allclose(pred2 - self.sigma, 4 * (pred1 - self.sigma), atol=1e-14)
                fixed = pok.omega_uncertain_prior(self.sigma, 0.05, self.P)
                mean_fixed, _ = pok.black_litterman(self.weights, self.sigma, self.P, self.Q, fixed, tau=0.20)
                self.assertAlmostEqual(float((self.P @ mean_fixed).iloc[0]), 0.0734)

    def test_rescaling_the_view_equation_does_not_change_the_model(self):
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                omega = pok.omega_uncertain_prior(self.sigma, 0.05, self.P)
                expected = pok.black_litterman(self.weights, self.sigma, self.P, self.Q, omega, tau=0.05)
                actual = pok.black_litterman(self.weights, self.sigma, 10 * self.P, 10 * self.Q, 100 * omega, tau=0.05)
                np.testing.assert_allclose(actual[0], expected[0])
                np.testing.assert_allclose(actual[1], expected[1])

    def test_invalid_labels_shapes_covariances_and_parameters_are_rejected(self):
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                for covariance in (self.sigma.rename(columns={"Equity": "Wrong"}), self.sigma.assign(Equity=np.nan),
                                   pd.DataFrame([[1., 2.], [2., 1.]], index=self.assets, columns=self.assets),
                                   pd.DataFrame([[1., 0.2], [0.1, 1.]], index=self.assets, columns=self.assets)):
                    with self.assertRaises(ValueError):
                        pok.black_litterman(self.weights, covariance, self.P, self.Q)
                for P, Q in ((self.P * 0, self.Q), (self.P, self.Q.rename(index={"Spread": "Wrong"})),
                             (self.P.rename(columns={"Bonds": "Wrong"}), self.Q)):
                    with self.assertRaises(ValueError):
                        pok.black_litterman(self.weights, self.sigma, P, Q)
                with self.assertRaises(ValueError):
                    pok.black_litterman(self.weights, self.sigma, self.P, self.Q,
                                        pd.DataFrame([[-0.01]], index=self.P.index, columns=self.P.index))
                with self.assertRaises(ValueError):
                    pok.implied_returns(self.sigma, self.weights * 0.9)
                for parameter in ("delta", "tau"):
                    for value in (0, -1, np.nan, np.inf):
                        with self.assertRaises(ValueError):
                            pok.black_litterman(self.weights, self.sigma, self.P, self.Q, **{parameter: value})

    def test_allocation_matches_two_asset_closed_form_and_constraints(self):
        for path, pok in self.modules.items():
            for spread in (-0.10, 0.047, 0.0635, 0.30):
                means = pd.Series([0.02 + spread, 0.02], index=self.assets)
                expected_equity = np.clip((spread + 2.5 * (0.01 - 0.006)) / (2.5 * 0.038), 0, 1)
                with self.subTest(copy=path, spread=spread):
                    actual = pok.bl_portfolio_weights(means, self.sigma)
                    np.testing.assert_allclose(actual, [expected_equity, 1 - expected_equity], atol=1e-7)
            with self.subTest(copy=path):
                pi = pok.implied_returns(self.sigma, self.weights)
                np.testing.assert_allclose(pok.bl_portfolio_weights(pi, self.sigma), self.weights, atol=1e-7)
                bad = SimpleNamespace(success=False, message="forced failure")
                with patch.object(pok, "minimize", return_value=bad), self.assertRaises(RuntimeError):
                    pok.bl_portfolio_weights(pi, self.sigma)

    def test_interactive_endpoints_and_risk_matrix_selection_preserve_units(self):
        for path, pok in self.modules.items():
            captures = []
            with self.subTest(copy=path), patch.object(pok, "_publish_echarts", side_effect=lambda plots, text: captures.append((plots, text))):
                pok.show_black_litterman_echart(confidence=0)
                np.testing.assert_allclose(captures[-1][0]["blMeans"]["series"]["Posterior"], [6.6, 1.9])
                np.testing.assert_allclose(captures[-1][0]["blWeights"]["series"]["Updated"], [60, 40])
                pok.show_black_litterman_echart(confidence=1)
                means = captures[-1][0]["blMeans"]["series"]["Posterior"]
                self.assertAlmostEqual(means[0] - means[1], 8)
                self.assertIn("predictive spread volatility: 19.494%", captures[-1][1])
                pok.show_black_litterman_echart()
                conditional = captures[-1][0]
                pok.show_black_litterman_echart(risk_model="predictive")
                predictive = captures[-1][0]
                self.assertEqual(conditional["blMeans"], predictive["blMeans"])
                self.assertNotEqual(conditional["blWeights"], predictive["blWeights"])


if __name__ == "__main__":
    unittest.main()
