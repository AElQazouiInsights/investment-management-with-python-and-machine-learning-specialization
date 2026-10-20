"""Execute every covariance lesson cell and verify financial/timing identities."""

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


class CovarianceExampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.markdown = (ROOT / "docs/2.2-covariance.md").read_text()
        cls.examples = {editor: code for code, editor in re.findall(
            r'```python:line-numbers\n(.*?)\n```\s*<Editor id="([^"]+)"\s*/>', cls.markdown, re.S)}
        cls.values, cls.output = {}, io.StringIO()
        with patch.object(pok, "path_to_data_folder", return_value=str(ROOT / "data")), contextlib.redirect_stdout(cls.output):
            for editor, code in cls.examples.items():
                exec(compile(code, editor, "exec"), cls.values)
        cls.payloads = [json.loads(line[len("<ECHARTS_DATA>"):]) for line in cls.output.getvalue().splitlines()
                        if line.startswith("<ECHARTS_DATA>")]

    def test_all_examples_run_in_order_with_unique_editor_and_chart_outputs(self):
        ids = re.findall(r'<Editor id="([^"]+)"', self.markdown)
        self.assertEqual(ids, list(self.examples))
        self.assertEqual(len(ids), 23)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(self.markdown.count("```python"), len(ids))
        self.assertEqual(len(self.payloads), 9)

    def test_worked_covariance_shrinkage_and_factor_model_answers(self):
        v = self.values
        np.testing.assert_allclose(v["worked_covariance"], [[0.0004, -0.0001], [-0.0001, 0.0001]])
        self.assertAlmostEqual(v["worked_variance"], 0.000112)
        self.assertAlmostEqual(v["mean_correlation"], 0.5)
        self.assertAlmostEqual(v["sample_matrix"][0, 1], 0.045)
        self.assertAlmostEqual(v["target_matrix"][0, 1], 0.030)
        self.assertAlmostEqual(v["shrunk_matrix"][0, 1], 0.0375)
        np.testing.assert_allclose(np.diag(v["shrunk_matrix"]), [0.04, 0.09, 0.0625])
        self.assertAlmostEqual(v["factor_model_covariance"][0, 0], 0.0504)
        self.assertAlmostEqual(v["factor_model_covariance"][0, 1], 0.0314)
        self.assertGreater(np.linalg.eigvalsh(v["factor_model_covariance"]).min(), 0)

    def test_rank_deficiency_and_shrinkage_diagnostics(self):
        v = self.values
        self.assertEqual(np.linalg.matrix_rank(v["short_covariance"]), 5)
        self.assertGreater(np.linalg.eigvalsh(v["short_shrinkage"]).min(), 0)
        self.assertEqual(np.linalg.matrix_rank(v["initial_covariances"]["Sample"]), 47)
        for name in ("Constant correlation", "50% shrinkage"):
            self.assertEqual(np.linalg.matrix_rank(v["initial_covariances"][name]), 49)
            np.testing.assert_allclose(np.diag(v["initial_covariances"][name]), np.diag(v["initial_covariances"]["Sample"]))

    def test_rolling_volatility_frequency_does_not_change_with_window_length(self):
        v = self.values
        self.assertEqual(len(v["market_returns"]), 1109)
        for window in (12, 60):
            actual = v["rolling_volatility"][f"{window}-month window"]
            self.assertEqual(actual.isna().sum(), window - 1)
            self.assertAlmostEqual(actual.iloc[window-1], np.std(v["market_returns"].iloc[:window], ddof=1) * np.sqrt(12))
            self.assertAlmostEqual(actual.iloc[-1], np.std(v["market_returns"].iloc[-window:], ddof=1) * np.sqrt(12))
        chart = self.payloads[1]["rollingVolatility"]
        self.assertEqual(chart["series"]["60-month window"][:59], [None] * 59)

    def test_cone_window_counts_and_ordered_quantiles(self):
        v = self.values
        cone = v["volatility_cone"]
        np.testing.assert_array_equal(cone["Windows"], 1109 - 12 * np.array(v["window_years"]) + 1)
        self.assertTrue((np.diff(cone.iloc[:, :5], axis=1) >= 0).all())
        self.assertAlmostEqual(cone.loc[1, "Maximum"], v["rolling_volatility"]["12-month window"].max())

    def test_exponential_weights_and_worked_dispersion(self):
        v = self.values
        weights = v["exponential_weights"]
        np.testing.assert_allclose(weights.sum(), 1)
        np.testing.assert_allclose(weights["Decay 1"], 1 / 24)
        self.assertGreater(weights["Decay 0.8"].iloc[-1], weights["Decay 0.8"].iloc[0])
        self.assertAlmostEqual(v["worked_ewa"] ** 2, 12 * (5 / 7) * 0.02 ** 2)
        self.assertAlmostEqual(v["equal_weight_volatility"] ** 2, 12 * 2 / 3 * 0.02 ** 2)
        self.assertAlmostEqual(v["endpoint_ewa"].loc[1], np.std(v["market_returns"], ddof=0) * np.sqrt(12) * 100)

    def test_conditional_variance_recursion_respects_forecast_timing(self):
        v = self.values
        self.assertAlmostEqual(v["omega"], 0.00002)
        self.assertAlmostEqual(v["next_variance"], 0.001)
        self.assertEqual(len(v["garch_variances"]), len(v["shocks"]) + 1)
        np.testing.assert_allclose(v["garch_variances"][:5], 0.0004)
        self.assertAlmostEqual(v["garch_variances"][5], 0.001)
        self.assertAlmostEqual(v["garch_variances"][6], 0.00091)
        self.assertAlmostEqual(v["ewma_variances"][5], 0.001)
        self.assertAlmostEqual(v["ewma_variances"][6], 0.00094)

    def test_every_strategy_has_the_same_evaluation_dates_and_initial_wealth(self):
        v = self.values
        actual = v["evaluation_returns"]
        self.assertEqual(actual.shape, (492, 5))
        self.assertTrue(np.isfinite(actual.to_numpy()).all())
        self.assertEqual(str(actual.index[0]), "1978-01")
        self.assertEqual(str(actual.index[-1]), "2018-12")
        self.assertTrue(v["portfolio_returns"].iloc[:48].isna().all().all())
        self.assertEqual(str(v["portfolio_wealth"].index[0]), "1977-12")
        np.testing.assert_allclose(v["portfolio_wealth"].iloc[0], [100] * 5)
        np.testing.assert_allclose(v["portfolio_wealth"].iloc[1], 100 * (1 + actual.iloc[0]))
        self.assertEqual(len(v["portfolio_wealth"]), 493)
        manual_cw = (v["industry_cap_weights"].shift(1) * v["industry_returns"]).sum(axis=1, min_count=49).iloc[48:]
        np.testing.assert_allclose(actual["CW"], manual_cw)
        np.testing.assert_allclose(actual["EW"], v["industry_returns"].iloc[48:].mean(axis=1))

    def test_gmv_decisions_satisfy_convex_optimality_and_match_the_realized_month(self):
        v = self.values
        self.assertEqual(str(v["decision_window"].index[0]), "2005-01")
        self.assertEqual(str(v["decision_window"].index[-1]), "2008-12")
        for name, estimator in (("GMV sample", pok.sample_cov), ("GMV constant correlation", pok.cc_cov),
                                ("GMV shrinkage", pok.shrinkage_cov)):
            covariance = estimator(v["decision_window"]).to_numpy()
            weights = v["decision_weights"][name].to_numpy()
            self.assertAlmostEqual(weights.sum(), 1)
            self.assertTrue((weights >= -1e-8).all())
            gradient = 2 * covariance @ weights
            self.assertTrue((gradient - gradient @ weights >= -1e-8).all())
            self.assertAlmostEqual(v["evaluation_returns"].loc["2009-01", name],
                                   v["industry_returns"].loc["2009-01"].to_numpy() @ weights)
        pd.testing.assert_series_equal(v["decision_weights"]["CW"],
                                       v["industry_cap_weights"].loc["2008-12"], check_names=False)

    def test_shrinkage_endpoint_allocations_reproduce_sample_and_target(self):
        v = self.values
        for delta, name in ((0, "GMV sample"), (1, "GMV constant correlation")):
            weights = pok.weight_minvar(v["decision_window"], cov_estimator=pok.shrinkage_cov, delta=delta)
            np.testing.assert_allclose(weights, v["decision_weights"][name], atol=1e-7)

    def test_performance_metrics_use_observed_cash_and_reconcile_to_snapshot(self):
        v = self.values
        actual = v["evaluation_returns"]
        excess = actual.sub(v["cash_returns"].loc[actual.index], axis=0)
        np.testing.assert_allclose(v["portfolio_statistics"]["Sharpe"], excess.mean() / excess.std(ddof=1) * np.sqrt(12))
        np.testing.assert_allclose(v["portfolio_statistics"]["Annualized volatility (%)"],
                                   [16.216, 15.180, 11.594, 11.898, 11.662], atol=0.002)
        self.assertTrue((v["portfolio_statistics"]["Maximum drawdown (%)"] > 0).all())

    def test_lagged_tail_estimates_exclude_the_return_being_evaluated(self):
        v = self.values
        returns = v["market_returns"]
        for month in ("1990-01", "2008-10", "2018-12"):
            location = returns.index.get_loc(month)
            history = returns.iloc[location-36:location].to_numpy()
            row = v["tail_diagnostics"].loc[month]
            self.assertAlmostEqual(row["Observed loss"], -returns.loc[month])
            self.assertAlmostEqual(row["Prior-window VaR"], -np.quantile(history, 0.01, method="linear"))
            self.assertAlmostEqual(row["Prior-window ES"], -np.min(history))
        self.assertEqual(len(v["tail_diagnostics"]), 348)
        self.assertEqual(v["exceedances"].sum(), 13)
        self.assertEqual(self.payloads[-1]["laggedTailRisk"]["yAxisName"], "Monthly loss (% of starting value)")


if __name__ == "__main__":
    unittest.main()
