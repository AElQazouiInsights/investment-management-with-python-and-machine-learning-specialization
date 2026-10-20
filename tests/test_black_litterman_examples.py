"""Run the complete Black–Litterman lesson and independently check its results."""
import contextlib
import io
import json
import re
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
import PortfolioOptimizationKit as pok

from test_return_annualization import ROOT


class BlackLittermanExampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.markdown = (ROOT / "docs/2.3-black-litterman.md").read_text()
        cls.examples = {editor: code for code, editor in re.findall(
            r'```python:line-numbers\n(.*?)\n```\s*<Editor id="([^"]+)"\s*/>', cls.markdown, re.S)}
        cls.values, output = {}, io.StringIO()
        with patch.object(pok, "path_to_data_folder", return_value=str(ROOT / "data")), contextlib.redirect_stdout(output):
            for editor, code in cls.examples.items():
                exec(compile(code, editor, "exec"), cls.values)
        cls.payloads = [json.loads(line[len("<ECHARTS_DATA>"):]) for line in output.getvalue().splitlines()
                        if line.startswith("<ECHARTS_DATA>")]

    @classmethod
    def tearDownClass(cls):
        cls.values["widget_instance"].close()

    def test_every_example_has_a_unique_editor_and_all_cells_execute_in_order(self):
        ids = re.findall(r'<Editor id="([^"]+)"', self.markdown)
        self.assertEqual(ids, list(self.examples))
        self.assertEqual(len(ids), 18)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(self.markdown.count("```python"), 18)
        self.assertEqual(sum(isinstance(value, dict) and "series" in value for payload in self.payloads for value in payload.values()), 8)

    def test_reference_view_conversion_and_posterior_worked_answers(self):
        v = self.values
        np.testing.assert_allclose(v["pi"], [0.066, 0.019])
        np.testing.assert_allclose(v["recovered_reference"], [0.6, 0.4])
        self.assertAlmostEqual(v["reference_excess_mean"], 0.0472)
        self.assertAlmostEqual(v["reference_variance"], 0.01888)
        np.testing.assert_allclose(v["excess_view_returns"], [0.06, 0.08])
        np.testing.assert_allclose(v["hand_mean"], [0.08076315789473684, 0.01726315789473684])
        np.testing.assert_allclose(v["posterior_mean"], v["hand_mean"])
        np.testing.assert_allclose(v["weights_prior_risk"], [0.7736842105263158, 0.2263157894736842])

    def test_confidence_and_tau_examples_respect_their_stated_conventions(self):
        v = self.values
        table = v["confidence_table"]
        np.testing.assert_allclose(table["Posterior spread"], 0.047 + table["Confidence"] * 0.033)
        np.testing.assert_allclose(v["tau_table"]["Spread: scaled Omega"], 0.0635)
        np.testing.assert_allclose(v["tau_table"]["Spread: fixed Omega"], [0.0525, 0.0635, 0.0734])
        self.assertAlmostEqual(v["exact_mean_spread_variance"], 0, places=14)
        self.assertAlmostEqual(float((v["P"] @ v["exact_predictive"] @ v["P"].T).iloc[0, 0]), 0.038)

    def test_historical_training_and_reference_end_before_held_out_returns(self):
        v = self.values
        self.assertEqual(v["training_returns"].shape, (120, 3))
        self.assertEqual(v["held_out_returns"].shape, (108, 3))
        self.assertEqual(str(v["reference_month"]), "2009-12")
        self.assertLess(v["reference_month"], v["held_out_returns"].index[0])
        np.testing.assert_allclose(v["historical_reference"], v["selected_capitalization"] / v["selected_capitalization"].sum())
        np.testing.assert_allclose(v["historical_pi"], 2.5 * v["annual_covariance"].to_numpy() @ v["historical_reference"].to_numpy())
        self.assertFalse(np.allclose(v["historical_pi"], v["sample_excess_means"]))

    def test_historical_posterior_satisfies_precision_equations_and_joint_views_matter(self):
        v = self.values
        C = v["historical_tau"] * v["annual_covariance"].to_numpy()
        P, Q, omega = v["historical_P"].to_numpy(), v["historical_Q"].to_numpy(), v["historical_omega"].to_numpy()
        precision = np.linalg.inv(C) + P.T @ np.linalg.solve(omega, P)
        expected = np.linalg.solve(precision, np.linalg.solve(C, v["historical_pi"]) + P.T @ np.linalg.solve(omega, Q))
        np.testing.assert_allclose(v["historical_mean"], expected)
        self.assertFalse(np.allclose(v["correlated_mean"], expected))
        np.testing.assert_allclose(v["historical_mean"], [0.03461, 0.05125, 0.07687], atol=6e-6)

    def test_allocations_satisfy_convex_optimality_and_holdout_wealth_reconciles(self):
        v = self.values
        for name, means in (("Black–Litterman", v["historical_mean"]), ("Sample mean", v["sample_excess_means"])):
            w = v["historical_weights"][name].to_numpy()
            gradient = 2.5 * v["annual_covariance"].to_numpy() @ w - means.to_numpy()
            self.assertTrue((gradient - gradient @ w >= -1e-8).all())
            self.assertAlmostEqual(w.sum(), 1)
            self.assertTrue((w >= -1e-10).all())
        np.testing.assert_allclose(v["historical_weights"]["Sample mean"], [1, 0, 0], atol=1e-7)
        np.testing.assert_allclose(v["evaluation_returns"], v["held_out_returns"].to_numpy() @ v["historical_weights"].to_numpy())
        self.assertEqual(v["evaluation_wealth"].shape, (109, 3))
        self.assertEqual(str(v["evaluation_wealth"].index[0]), "2009-12")
        np.testing.assert_allclose(v["evaluation_wealth"].iloc[0], [100] * 3)
        np.testing.assert_allclose(v["evaluation_wealth"].iloc[-1], 100 * (1 + v["evaluation_returns"]).prod())


if __name__ == "__main__":
    unittest.main()
