"""Execute the factor chapter and check independent financial interpretations."""

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


class FactorExampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.markdown = (ROOT / "docs/2.1-style-factors.md").read_text()
        cls.examples = dict((editor, code) for code, editor in re.findall(
            r'```python:line-numbers\n(.*?)\n```\s*<Editor id="([^"]+)"\s*/>', cls.markdown, re.S))
        cls.values, cls.output = {}, io.StringIO()
        with patch.object(pok, "path_to_data_folder", return_value=str(ROOT / "data")), contextlib.redirect_stdout(cls.output):
            for editor, code in cls.examples.items():
                exec(compile(code, editor, "exec"), cls.values)
        cls.payloads = [json.loads(line[len("<ECHARTS_DATA>"):]) for line in cls.output.getvalue().splitlines()
                        if line.startswith("<ECHARTS_DATA>")]

    def test_all_cells_execute_in_order_and_every_python_fence_has_a_unique_editor(self):
        ids = re.findall(r'<Editor id="([^"]+)"', self.markdown)
        self.assertEqual(ids, list(self.examples))
        self.assertEqual(len(ids), 18)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(self.markdown.count("```python"), len(ids))
        self.assertEqual(len(self.payloads), 7)

    def test_worked_capm_factor_spreads_and_style_answers(self):
        v = self.values
        np.testing.assert_allclose(v["betas"], [1.2, 1.2])
        np.testing.assert_allclose(v["capm_expected_returns"], [0.092, 0.092])
        self.assertAlmostEqual(v["beta_by_hand"], 1.2)
        self.assertAlmostEqual(v["alpha_by_hand"], 0.001)
        self.assertAlmostEqual(v["smb"], 0.01)
        self.assertAlmostEqual(v["hml"], 0.03)
        self.assertAlmostEqual(v["factor_benchmark"], 0.027)
        self.assertAlmostEqual(v["fit_distance"], 0.02)
        self.assertAlmostEqual(v["rmse"], 0.01)
        self.assertAlmostEqual(v["tracking_volatility"], 0)
        self.assertAlmostEqual(v["toy_manager"].iloc[0], 0.004)
        np.testing.assert_allclose(v["recovered_weights"], [0.3, 0.5, 0.2], atol=1e-7)
        np.testing.assert_allclose(v["capped_example"], [0.1, 0.3, 0.6])

    def test_monthly_snapshot_alignment_and_capm_identity(self):
        v = self.values
        self.assertEqual(len(v["brka_monthly"]), 348)
        self.assertEqual(len(v["factors_monthly"]), 1110)
        self.assertEqual(len(v["factor_sample"]), 305)
        np.testing.assert_allclose(v["factors_monthly"].iloc[0], [0.0296, -0.023, -0.0287, 0.0022])
        x = v["factor_sample"]["Mkt-RF"]
        y = v["factor_sample"]["BRKA"] - v["factor_sample"]["RF"]
        beta = np.cov(x, y)[0, 1] / np.var(x, ddof=1)
        self.assertAlmostEqual(v["capm_fit"].params["Mkt-RF"], beta)
        self.assertAlmostEqual(v["capm_fit"].params["Alpha"], y.mean() - beta * x.mean())
        np.testing.assert_allclose(v["capm_fit"].params, [0.55543, 0.006340], atol=5e-6)

    def test_three_factor_ols_and_hac_covariance_match_independent_matrix_calculation(self):
        v = self.values
        x = np.column_stack([v["factor_sample"][["Mkt-RF", "SMB", "HML"]], np.ones(305)])
        y = v["brka_excess"].to_numpy()
        beta = np.linalg.lstsq(x, y, rcond=None)[0]
        np.testing.assert_allclose(v["ff_fit"].params, beta, atol=1e-12)
        residual = y - x @ beta
        scores = x * residual[:, None]
        meat = scores.T @ scores
        for lag in range(1, 7):
            lag_product = scores[lag:].T @ scores[:-lag]
            meat += (1 - lag / 7) * (lag_product + lag_product.T)
        bread = np.linalg.inv(x.T @ x)
        covariance = bread @ meat @ bread * len(y) / (len(y) - x.shape[1])
        np.testing.assert_allclose(v["ff_hac"].cov_params(), covariance, atol=1e-12)
        np.testing.assert_allclose(beta, [0.68771, -0.48888, 0.39212, 0.005419], atol=5e-6)
        self.assertLess(v["ff_intervals"].loc["Alpha", "Lower 95%"], 0)
        self.assertGreater(v["ff_fit"].rsquared, v["capm_fit"].rsquared)

    def test_benchmark_excludes_intercept_and_mean_attribution_reconciles(self):
        v = self.values
        expected = v["factor_sample"]["RF"] + v["factor_sample"][v["factor_names"]] @ v["ff_fit"].params[v["factor_names"]]
        np.testing.assert_allclose(v["factor_benchmark_returns"], expected)
        self.assertAlmostEqual(v["active_returns"].mean(), v["ff_fit"].params["Alpha"])
        self.assertAlmostEqual(v["mean_attribution"].sum(), v["factor_sample"]["BRKA"].mean())
        self.assertEqual(v["factor_wealth"].index[0], pd.Period("1989-12", freq="M"))
        np.testing.assert_allclose(v["factor_wealth"].iloc[0], [100, 100])
        self.assertEqual(len(v["factor_wealth"]), 306)

    def test_historical_style_optimizer_satisfies_convex_first_order_condition(self):
        v = self.values
        x, y, w = v["industry_sample"].to_numpy(), v["synthetic_manager"].to_numpy(), v["style_weights"].to_numpy()
        gradient = 2 * x.T @ (x @ w - y) / len(y)
        # At a simplex optimum, no vertex is a descent direction.
        self.assertTrue((gradient - gradient @ w >= -1e-8).all())
        self.assertAlmostEqual(w.sum(), 1)
        self.assertTrue((w >= -1e-10).all())
        self.assertLess(np.linalg.norm(y - v["unconstrained_fit"].fittedvalues), np.linalg.norm(y - x @ w))

    def test_holdout_weights_use_only_training_sample_and_refitting_is_hindsight(self):
        v = self.values
        self.assertEqual(len(v["training"]), 108)
        self.assertEqual(len(v["held_out"]), 120)
        self.assertLess(v["training"].index[-1], v["held_out"].index[0])
        expected = v["held_out"][v["industry_names"]] @ v["training_weights"]
        np.testing.assert_allclose(v["holdout_returns"]["Frozen training mix"], expected)
        self.assertLessEqual(v["style_diagnostics"]["Held-out hindsight refit"][1], v["style_diagnostics"]["Held-out frozen weights"][1])
        np.testing.assert_allclose(v["holdout_wealth"].iloc[0], [100, 100])

    def test_rolling_style_respects_the_regime_change_information_boundary(self):
        v = self.values
        styles = v["rolling_styles"]
        self.assertEqual(len(styles), 168)
        self.assertEqual(str(styles.index[0]), "2005-01")
        # January's NEW return has not been observed when its estimate is set.
        self.assertAlmostEqual(styles.loc["2009-01", "Beer"], 0.8, places=6)
        self.assertAlmostEqual(v["actual_beer_weight"].loc["2009-01"], 0.2)
        self.assertAlmostEqual(styles.loc["2014-01", "Beer"], 0.2, places=6)
        np.testing.assert_allclose(styles.sum(axis=1), 1)

    def test_weighting_sharpes_use_realized_cash_and_count_industries(self):
        v = self.values
        self.assertEqual(len(v["comparison_dates"]), 888)
        self.assertEqual(v["industry_sharpes"].shape, (30, 2))
        self.assertAlmostEqual(v["fraction_ew_higher"], 0.7)
        for scheme in ("vw", "ew"):
            returns = v[f"industry_{scheme}"].loc[v["comparison_dates"], "Food"]
            excess = returns - v["cash_history"]
            expected = np.mean(excess) / np.std(excess, ddof=1) * np.sqrt(12)
            self.assertAlmostEqual(v["industry_sharpes"].loc["Food", scheme.upper()], expected)

    def test_allocation_backtest_reconciles_to_lagged_capitalization(self):
        v = self.values
        self.assertEqual(len(v["allocation_returns"]), 540)
        for frame in (v["firm_counts49"], v["firm_sizes49"]):
            self.assertTrue(np.isfinite(frame.to_numpy()).all())
            self.assertTrue((frame >= 0).all().all())
        manual = (v["cap49"].shift(1) * v["industry49"]).sum(axis=1, min_count=49).iloc[1:]
        np.testing.assert_allclose(v["allocation_returns"]["Lagged capitalization"], manual)
        np.testing.assert_allclose(v["allocation_returns"]["Equal industry weights"], v["industry49"].iloc[1:].mean(axis=1))
        np.testing.assert_allclose(v["allocation_wealth"].iloc[0], [100] * 3)
        self.assertEqual(str(v["allocation_wealth"].index[0]), "1973-12")


if __name__ == "__main__":
    unittest.main()
