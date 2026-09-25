"""Numerical and execution checks for the reviewed optimization examples."""

import contextlib
import io
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch

import numpy as np
import PortfolioOptimizationKit as pok


ROOT = Path(__file__).resolve().parents[1]


class OptimizationExamplesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        markdown = (ROOT / "docs/1.2-optimization.md").read_text()
        cls.examples = {}
        for match in re.finditer(r'^```python[^\n]*\n(.*?)^```[ \t]*$', markdown, re.MULTILINE | re.DOTALL):
            editor = re.match(r'\s*<Editor id="([^"]+)"\s*/>', markdown[match.end():])
            if editor:
                cls.examples[editor.group(1)] = match.group(1)

    def execute_cml(self, last_cell="capital-market-line-msr", quoted_rate=0.06):
        namespace = self.execute_stock_case("equal-weighted-portfolio-features")
        cells = ["capital-market-line", "capital-market-line-ew-gvm-msr", "capital-market-line-msr"]
        output = io.StringIO()
        with patch.object(pok, "get_stock_dynamic", side_effect=AssertionError("Reuse the stock sample")):
            with patch.object(pok, "efficient_frontier", side_effect=AssertionError("Reuse the risky frontier")):
                with contextlib.redirect_stdout(output):
                    for editor_id in cells[:cells.index(last_cell) + 1]:
                        code = self.examples[editor_id].replace("quoted_cash_rate = 0.06", f"quoted_cash_rate = {quoted_rate!r}")
                        exec(compile(code, f"1.2:{editor_id}", "exec"), namespace)
        namespace["_payloads"] = [json.loads(line.split("<ECHARTS_DATA>", 1)[1])
                                  for line in output.getvalue().splitlines() if line.startswith("<ECHARTS_DATA>")]
        self.assertEqual(len(namespace["_payloads"]), cells.index(last_cell) + 1)
        return namespace

    def execute_opening(self, last_cell):
        cells = ["portfolio-optimization-python-modules", "setup-scenario-1",
                 "setup-scenario-2", "setup-scenario-3"]
        namespace = {"__name__": "__main__"}
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            for cell in cells[:cells.index(last_cell) + 1]:
                exec(compile(self.examples[cell], f"1.2:{cell}", "exec"), namespace)
        namespace["_output"] = output.getvalue()
        return namespace

    def execute_stock_case(self, last_cell):
        cells = ["stock-selection-retrieval", "returns-vol-portfolio-metrics",
                 "real-world-efficient-frontier", "msr-gmv", "equal-weighted-portfolio-features",
                 "seeking-minimum-volatility", "target-return",
                 "minimum-volatility-portfolio-for-target-return", "maximum-sharpe-ratio",
                 "target-volatility", "maximum-sharpe-ratio-with-set-volatility"]
        namespace = {"__name__": "__main__"}
        output = io.StringIO()
        with patch.object(pok, "path_to_data_folder", return_value=str(ROOT / "data")):
            with contextlib.redirect_stdout(output):
                for cell in cells[:cells.index(last_cell) + 1]:
                    exec(compile(self.examples[cell], f"1.2:{cell}", "exec"), namespace)
        namespace["_output"] = output.getvalue()
        return namespace

    def test_worked_allocation_matches_expected_return_and_variance(self):
        values = self.execute_opening("setup-scenario-2")
        self.assertAlmostEqual(values["portfolio_mean"], 0.096)
        self.assertAlmostEqual(values["portfolio_variance"], 0.0124)
        self.assertAlmostEqual(values["portfolio_vol"], 0.11135528725660045)

    def test_correlation_experiment_changes_risk_but_not_expected_return(self):
        values = self.execute_opening("setup-scenario-3")
        payload = json.loads(values["_output"].split("<ECHARTS_DATA>")[1])
        self.assertEqual(len(payload), 6)
        risks = []
        for chart in payload.values():
            points = np.asarray(chart["series"]["Portfolios"])
            self.assertEqual(points.shape, (101, 3))
            self.assertTrue(np.isfinite(points).all())
            np.testing.assert_allclose(points[:, 1], np.linspace(12.0, 8.0, 101))
            np.testing.assert_allclose(points[0], [20.0, 12.0, 1.0])
            np.testing.assert_allclose(points[-1], [10.0, 8.0, 0.0])
            self.assertEqual(chart["visualMap"]["seriesIndex"], 0)
            self.assertEqual(chart["yAxis"]["name"], "Expected annual return (%)")
            self.assertLessEqual(chart["series"]["GMV"][0][0], points[:, 0].min() + 1e-8)
            risks.append(points[:, 0])
        # The correlation list runs from +1 to -1, with fixed asset moments.
        self.assertTrue((np.diff(np.asarray(risks), axis=0) <= 1e-10).all())
        self.assertAlmostEqual(payload["ef_2"]["series"]["Portfolios"][60][0], 11.135528725660045)
        self.assertAlmostEqual(payload["ef_2"]["series"]["Portfolios"][60][1], 9.6)

    def test_analytical_gmv_weights_and_dominance_match_the_lesson(self):
        values = self.execute_opening("setup-scenario-3")
        table = values["gmv_comparison"]
        np.testing.assert_allclose(table.loc[0.25], [87.5, 12.5, 8.5, 9.682458365518543])
        np.testing.assert_allclose(table.loc[1.0], [100.0, 0.0, 8.0, 10.0], atol=1e-12)
        np.testing.assert_allclose(table.loc[-1.0], [200 / 3, 100 / 3, 28 / 3, 0.0], atol=1e-8)
        np.testing.assert_allclose(table["Asset 1 weight (%)"] + table["Asset 2 weight (%)"], 100.0)
        self.assertTrue(table["Asset 1 weight (%)"].between(0.0, 100.0).all())
        self.assertLess(table.loc[0.25, "Volatility (%)"], 10.0)
        self.assertGreater(table.loc[0.25, "Expected return (%)"], 8.0)

    def test_equal_volatility_perfect_correlation_has_a_finite_representative_gmv(self):
        values = self.execute_opening("setup-scenario-1")
        values["volatilities"] = np.array([0.10, 0.10])
        with contextlib.redirect_stdout(io.StringIO()):
            exec(compile(self.examples["setup-scenario-3"], "equal-volatility-scenario", "exec"), values)
        np.testing.assert_allclose(values["gmv_comparison"].loc[1.0], [50.0, 50.0, 10.0, 10.0])
        points = np.asarray(values["plot_data"]["ef_0"]["series"]["Portfolios"])
        np.testing.assert_allclose(points[:, 0], 10.0)

    def test_stock_case_preserves_prices_and_uses_arithmetic_expected_returns(self):
        values = self.execute_stock_case("returns-vol-portfolio-metrics")
        np.testing.assert_allclose(values["stocks"].iloc[0], [9.23, 20.62, 21.73])
        self.assertEqual(values["daily_returns"].shape, (3518, 3))
        np.testing.assert_allclose(values["annual_returns"], values["daily_returns"].mean() * 252)
        self.assertFalse(np.allclose(values["annual_returns"], pok.annualize_rets(values["daily_returns"], 252)))
        weights = values["weight_samples"]
        self.assertEqual(weights.shape, (4000, 3))
        self.assertTrue((weights >= 0).all())
        np.testing.assert_allclose(weights.sum(axis=1), 1.0)
        expected_weights = np.random.default_rng(42).dirichlet(np.ones(3), size=4000)
        np.testing.assert_allclose(weights, expected_weights)
        np.testing.assert_allclose(values["portfolios_df"]["return"], weights @ values["annual_returns"].to_numpy())

    def test_optimized_stock_portfolios_beat_the_sample_and_match_analytical_weights(self):
        values = self.execute_stock_case("equal-weighted-portfolio-features")
        metrics = values["key_portfolios"]
        sample = values["portfolios_df"]
        self.assertLessEqual(metrics.loc["GMV", "volatility"], sample["volatility"].min() + 1e-8)
        self.assertGreaterEqual(metrics.loc["MSR", "sharpe"], sample["sharpe"].max() - 1e-8)
        covariance = values["cov_matrix"].to_numpy()
        closed_gmv = np.linalg.solve(covariance, np.ones(3))
        closed_gmv /= closed_gmv.sum()
        closed_msr = np.linalg.solve(covariance, values["annual_returns"].to_numpy())
        closed_msr /= closed_msr.sum()
        np.testing.assert_allclose(values["key_weights"]["GMV"], closed_gmv, atol=1e-5)
        np.testing.assert_allclose(values["key_weights"]["MSR"], closed_msr, atol=1e-5)
        ew_return, ew_vol, ew_sharpe = values["equal_weight_metrics"]
        self.assertAlmostEqual(ew_return, values["annual_returns"].mean())
        self.assertAlmostEqual(ew_vol ** 2, covariance.sum() * 252 / 9)
        self.assertAlmostEqual(ew_sharpe, ew_return / ew_vol)

    def test_stock_case_chart_uses_percent_axes_and_one_consistent_set_of_estimates(self):
        values = self.execute_stock_case("msr-gmv")
        chart = values["plot_data"]["stockFrontier"]
        scatter = np.asarray(chart["series"]["Portfolios"])
        self.assertEqual(scatter.shape, (4000, 3))
        np.testing.assert_allclose(scatter[:, :2], values["portfolios_df"][["volatility", "return"]] * 100)
        np.testing.assert_allclose(scatter[:, 2], values["portfolios_df"]["sharpe"])
        np.testing.assert_allclose(chart["series"]["Frontier"], values["df_frontier"][["volatility", "return"]] * 100)
        for name in ("GMV", "MSR"):
            np.testing.assert_allclose(chart["series"][name][0], values["key_portfolios"].loc[name, ["volatility", "return"]] * 100)
        self.assertEqual(chart["visualMap"]["seriesIndex"], 0)
        self.assertEqual(chart["xAxis"]["name"], "Annualized volatility (%)")
        self.assertNotIn("max", chart["xAxis"])
        self.assertNotIn("max", chart["yAxis"])

    def test_cml_cash_conversion_and_mixture_match_daily_return_calculations(self):
        values = self.execute_cml("capital-market-line")
        self.assertAlmostEqual((1 + values["cash_period_rate"]) ** 252 - 1, 0.06)
        self.assertAlmostEqual(values["cml_rate"], 0.05827564528143634)
        daily_risky = values["daily_returns"] @ values["tangent_weights"]
        daily_combined = 0.5 * daily_risky + 0.5 * values["cash_period_rate"]
        self.assertAlmostEqual(values["combined_return"], daily_combined.mean() * 252)
        self.assertAlmostEqual(values["combined_vol"], daily_combined.std(ddof=1) * np.sqrt(252))
        self.assertAlmostEqual(values["tangent_sharpe"], pok.sharpe_ratio(daily_risky, 0.06, 252))
        self.assertAlmostEqual(values["combined_return"], 0.15908282038529628, places=7)
        self.assertAlmostEqual(values["combined_weights"].sum() + values["combined_cash"], 1.0)

    def test_long_only_tangency_matches_its_active_asset_solution(self):
        values = self.execute_cml("capital-market-line")
        covariance = values["cov_matrix"].to_numpy() * 252
        excess = values["annual_returns"].to_numpy() - values["cml_rate"]
        active = [0, 2]  # AMZN and MSFT; KO's nonnegative bound is active.
        face_weights = np.linalg.solve(covariance[np.ix_(active, active)], excess[active])
        face_weights /= face_weights.sum()
        weights = values["tangent_weights"]
        np.testing.assert_allclose(weights[active], face_weights, atol=1e-5)
        self.assertAlmostEqual(weights[1], 0.0, places=7)
        volatility = np.sqrt(weights @ covariance @ weights)
        gradient = excess / volatility - (weights @ excess) * (covariance @ weights) / volatility ** 3
        np.testing.assert_allclose(gradient[active], 0.0, atol=1e-5)
        self.assertLess(gradient[1], 0.0)

    def test_strategy_solutions_match_closed_form_and_actual_sample_comparison(self):
        values = self.execute_stock_case("maximum-sharpe-ratio-with-set-volatility")
        means = values["annual_returns"].to_numpy()
        covariance = values["cov_matrix"].to_numpy() * 252
        inv_one = np.linalg.solve(covariance, np.ones(3))
        inv_mean = np.linalg.solve(covariance, means)
        a, b = inv_one.sum(), inv_mean.sum()
        c = means @ inv_mean
        gmv = inv_one / a
        np.testing.assert_allclose(values["gmv_weights"], gmv, atol=1e-5)
        target = values["target_return"]
        closed_target = ((c - b * target) * inv_one + (a * target - b) * inv_mean) / (a * c - b * b)
        np.testing.assert_allclose(values["target_weights"], closed_target, atol=1e-5)
        self.assertAlmostEqual(values["target_ret"], 0.16, places=8)
        # Unrestricted fixed-risk upper bound; positive weights make it long-only feasible.
        direction = inv_mean - b / a * inv_one
        closed_at_vol = gmv + np.sqrt((0.20 ** 2 - 1 / a) / (c - b * b / a)) * direction
        self.assertTrue((closed_at_vol > 0).all())
        np.testing.assert_allclose(values["weights_at_vol"], closed_at_vol, atol=1e-5)
        self.assertAlmostEqual(values["vol_at_vol"], 0.20, places=8)
        self.assertAlmostEqual(values["ret_at_vol"], 0.207882143554, places=7)
        self.assertLessEqual(values["sharpe_at_vol"], values["shp_msr"] + 1e-8)
        sampled = values["portfolios_df"]
        best = sampled.loc[sampled["sharpe"].idxmax()]
        np.testing.assert_allclose(values["msr_comparison"].loc["Best sampled"],
                                   [best["return"] * 100, best["volatility"] * 100, best["sharpe"]])
        self.assertGreaterEqual(values["shp_msr"], best["sharpe"] - 1e-8)

    def test_strategy_charts_share_estimates_and_percent_units(self):
        values = self.execute_stock_case("maximum-sharpe-ratio-with-set-volatility")
        charts = [json.loads(line.split("<ECHARTS_DATA>", 1)[1])["portfolioStrategy"]
                  for line in values["_output"].splitlines()
                  if line.startswith("<ECHARTS_DATA>") and "portfolioStrategy" in line]
        self.assertEqual(len(charts), 4)
        for chart, (marker, vol, ret) in zip(charts, [
            ("GMV", "gmv_vol", "gmv_ret"), ("MinVolForTarget", "target_vol", "target_ret"),
            ("MSR", "vol_msr", "ret_msr"), ("MaxSharpePort", "vol_at_vol", "ret_at_vol"),
        ]):
            np.testing.assert_allclose(chart["series"]["Frontier"], values["df_frontier"][["volatility", "return"]] * 100)
            np.testing.assert_allclose(chart["series"][marker][0], [values[vol] * 100, values[ret] * 100])
            self.assertEqual(chart["xAxis"]["name"], "Annualized volatility (%)")
            self.assertEqual(chart["yAxis"]["name"], "Estimated annual return (%)")
            self.assertNotIn("max", chart["xAxis"])
            self.assertNotIn("max", chart["yAxis"])

    def test_strategy_exercises_reject_infeasible_targets_and_show_dominance(self):
        values = self.execute_stock_case("maximum-sharpe-ratio-with-set-volatility")
        with contextlib.redirect_stdout(io.StringIO()):
            values["target_return"] = 0.10
            exec(self.examples["minimum-volatility-portfolio-for-target-return"], values)
            self.assertAlmostEqual(values["target_ret"], 0.10, places=8)
            self.assertGreater(values["gmv_ret"], values["target_ret"])
            self.assertLess(values["gmv_vol"], values["target_vol"])
            values["target_return"] = 0.40
            with self.assertRaisesRegex(ValueError, "feasible long-only range"):
                exec(self.examples["minimum-volatility-portfolio-for-target-return"], values)
            values["target_volatility"] = 0.15
            with self.assertRaisesRegex(ValueError, "feasible long-only range"):
                exec(self.examples["maximum-sharpe-ratio-with-set-volatility"], values)
            values["target_volatility"] = 0.25
            exec(self.examples["maximum-sharpe-ratio-with-set-volatility"], values)
        self.assertAlmostEqual(values["vol_at_vol"], 0.25, places=8)
        self.assertLess(values["sharpe_at_vol"], values["shp_msr"])

    def test_nonzero_benchmark_exercise_recomputes_the_sample_and_optimizer(self):
        values = self.execute_stock_case("maximum-sharpe-ratio")
        exercise = self.examples["maximum-sharpe-ratio"].replace("risk_free_rate = 0.0", "risk_free_rate = 0.02")
        with contextlib.redirect_stdout(io.StringIO()):
            exec(exercise, values)
        expected = np.linalg.solve(values["cov_matrix"], values["annual_returns"] - 0.02)
        expected /= expected.sum()
        np.testing.assert_allclose(values["msr_weights"], expected, atol=1e-5)
        sample_sharpes = (values["portfolios_df"]["return"] - 0.02) / values["portfolios_df"]["volatility"]
        self.assertAlmostEqual(values["msr_comparison"].loc["Best sampled", "Sharpe"], sample_sharpes.max())
        self.assertGreaterEqual(values["shp_msr"], sample_sharpes.max() - 1e-8)

    def test_all_reviewed_cells_execute_in_document_order(self):
        namespace = {"__name__": "__main__"}
        count = 0
        with patch.object(pok, "path_to_data_folder", return_value=str(ROOT / "data")):
            with contextlib.redirect_stdout(io.StringIO()):
                for editor_id, code in self.examples.items():
                    exec(compile(code, f"1.2:{editor_id}", "exec"), namespace)
                    count += 1
        self.assertEqual(count, 20)
        self.assertAlmostEqual(namespace["vol_at_vol"], 0.20, places=8)
        np.testing.assert_allclose(namespace["budget_weights"], [0.5, 0.5], atol=1e-12)
        self.assertAlmostEqual(namespace["signed_return"], 0.13)

    def execute_constraint_examples(self, target=0.10):
        namespace = {"__name__": "__main__"}
        output = io.StringIO()
        first = self.examples["short-selling-flexible-weights"].replace(
            "constraint_target = 0.10", f"constraint_target = {target!r}"
        )
        with contextlib.redirect_stdout(output):
            exec(self.examples["portfolio-optimization-python-modules"], namespace)
            exec(compile(first, "1.2:short-selling-flexible-weights", "exec"), namespace)
            exec(compile(self.examples["short-selling-fully-invested-weights"],
                         "1.2:short-selling-fully-invested-weights", "exec"), namespace)
        namespace["_output"] = output.getvalue()
        return namespace

    def test_flexible_risky_budget_includes_borrowing_and_minimizes_variance(self):
        values = self.execute_constraint_examples()
        weights = values["flex_weights"]
        np.testing.assert_allclose(weights, [65 / 76, 20 / 76], atol=1e-12)
        self.assertAlmostEqual(values["cash_weight"], -9 / 76)
        self.assertAlmostEqual(weights.sum() + values["cash_weight"], 1.0)
        self.assertAlmostEqual(values["flex_return"], 0.10)
        self.assertAlmostEqual(values["flex_vol"] ** 2, 3.75 / 304)
        # These changes preserve the 10% mean but move away from the optimum.
        for step in (-0.25, 0.25):
            alternative = weights + step * np.array([3.0, -2.0])
            self.assertAlmostEqual(alternative @ values["constraint_means"], 0.10)
            variance = alternative @ values["constraint_covariance"] @ alternative
            self.assertGreater(variance, values["flex_vol"] ** 2)

    def test_fully_invested_signed_weights_match_the_hand_calculation(self):
        values = self.execute_constraint_examples()
        np.testing.assert_allclose(values["budget_weights"], [0.5, 0.5], atol=1e-12)
        self.assertAlmostEqual(values["budget_return"], 0.10)
        self.assertAlmostEqual(values["budget_vol"] ** 2, 0.015)
        self.assertGreater(values["budget_vol"], values["flex_vol"])
        means = values["constraint_means"]
        self.assertAlmostEqual(values["f"].sum(), 1.0)
        self.assertAlmostEqual(means @ values["f"], 0.0)
        self.assertAlmostEqual(values["g"].sum(), 0.0)
        self.assertAlmostEqual(means @ values["g"], 1.0)

    def test_constraint_exercises_distinguish_cash_shorting_and_gross_exposure(self):
        lower = self.execute_constraint_examples(0.08)
        self.assertAlmostEqual(lower["cash_weight"], 2 / 19)
        np.testing.assert_allclose(lower["budget_weights"], [1.0, 0.0], atol=1e-12)
        higher = self.execute_constraint_examples(0.14)
        np.testing.assert_allclose(higher["budget_weights"], [-0.5, 1.5], atol=1e-12)
        self.assertAlmostEqual(higher["budget_return"], 0.14)
        self.assertAlmostEqual(higher["budget_weights"].sum(), 1.0)
        self.assertAlmostEqual(np.abs(higher["budget_weights"]).sum(), 2.0)
        self.assertAlmostEqual(higher["budget_vol"] ** 2, 0.085)
        self.assertIn("Gross risky exposure: 200.00%", higher["_output"])
        with self.assertRaisesRegex(ValueError, "feasible long-only range"):
            pok.minimize_volatility(higher["constraint_means"], higher["constraint_covariance"], 0.14)

    def test_signed_boundary_variance_and_dominated_branch(self):
        for target in (0.0, 0.08, 0.085, 0.10, 0.14):
            with self.subTest(target=target):
                values = self.execute_constraint_examples(target)
                a, b, c = values["A"], values["B"], values["C"]
                expected_variance = (c * target ** 2 - 2 * b * target + a) / (a * c - b ** 2)
                self.assertAlmostEqual(values["budget_vol"] ** 2, expected_variance)
                self.assertAlmostEqual(values["budget_return"], target)
                self.assertAlmostEqual(b / c, 0.085)
                if target < 0.085:
                    # Analytical two-asset GMV: 87.5% / 12.5%, variance 0.009375.
                    self.assertGreater(values["budget_vol"] ** 2, 0.009375)

    def test_cml_comparison_uses_one_cash_rate_and_matches_gmv_risk(self):
        values = self.execute_cml("capital-market-line-ew-gvm-msr")
        comparison = values["cml_comparison"]
        np.testing.assert_allclose(comparison["sharpe"],
                                   (comparison["return"] - values["cml_rate"]) / comparison["volatility"])
        self.assertAlmostEqual(comparison.loc["GMV", "return"], values["key_portfolios"].loc["GMV", "return"])
        self.assertAlmostEqual(comparison.loc["EWP", "return"], values["annual_returns"].mean())
        self.assertAlmostEqual(values["gmv_risk_fraction"] * values["tangent_vol"], comparison.loc["GMV", "volatility"])
        self.assertTrue(0 < values["gmv_risk_fraction"] < 1)
        self.assertGreater(values["cal_return_at_gmv_risk"], comparison.loc["GMV", "return"])

    def test_signed_cash_allocation_matches_kkt_solution_and_daily_moments(self):
        values = self.execute_cml()
        covariance = values["annual_covariance"]
        excess = values["excess_means"]
        kkt = np.block([[covariance, -excess[:, None]], [excess[None, :], np.zeros((1, 1))]])
        expected = np.linalg.solve(kkt, np.append(np.zeros(3), 0.13 - values["cml_rate"]))[:3]
        np.testing.assert_allclose(values["signed_weights"], expected, atol=1e-12)
        self.assertAlmostEqual(expected.sum() + values["signed_cash"], 1.0)
        daily = values["daily_returns"] @ expected + values["signed_cash"] * values["cash_period_rate"]
        self.assertAlmostEqual(values["signed_return"], daily.mean() * 252)
        self.assertAlmostEqual(values["signed_vol"], daily.std(ddof=1) * np.sqrt(252))
        self.assertAlmostEqual(values["signed_vol"], 0.08943042699700957)
        self.assertLess(values["signed_tangent_weights"][1], 0)
        self.assertGreater(values["signed_tangent_sharpe"], values["tangent_sharpe"])
        self.assertAlmostEqual(values["signed_tangent_sharpe"], np.sqrt(values["excess_quadratic"]))

    def test_cash_and_borrowing_exercises_preserve_budget_and_volatility_sign(self):
        values = self.execute_cml("capital-market-line")
        for fraction in (0.0, 1.0, 1.25, -0.5):
            with self.subTest(fraction=fraction), contextlib.redirect_stdout(io.StringIO()):
                code = self.examples["capital-market-line"].replace("risky_fraction = 0.5", f"risky_fraction = {fraction!r}")
                exec(code, values)
                self.assertAlmostEqual(values["combined_weights"].sum() + values["combined_cash"], 1.0)
                daily = values["daily_returns"] @ values["combined_weights"] + values["combined_cash"] * values["cash_period_rate"]
                self.assertAlmostEqual(values["combined_vol"], daily.std(ddof=1) * np.sqrt(252))
                self.assertAlmostEqual(values["combined_return"], daily.mean() * 252)
                if fraction > 1:
                    self.assertLess(values["combined_cash"], 0)
                    np.testing.assert_allclose(values["capital_line"][-1],
                                               [values["combined_vol"] * 100, values["combined_return"] * 100])
                elif fraction < 0:
                    self.assertLess(values["combined_return"], values["cml_rate"])
                    self.assertGreater(values["combined_vol"], 0)
                elif fraction == 0:
                    self.assertEqual(values["combined_vol"], 0)

    def test_signed_target_exercises_cover_cash_and_both_return_branches(self):
        values = self.execute_cml()
        for target in ("cml_rate", "0.04", "0.35"):
            with self.subTest(target=target), contextlib.redirect_stdout(io.StringIO()):
                exec(self.examples["capital-market-line-msr"].replace("signed_target = 0.13", f"signed_target = {target}"), values)
                self.assertAlmostEqual(values["signed_return"], values["signed_target"])
                self.assertAlmostEqual(values["signed_vol"], abs(values["signed_target"] - values["cml_rate"]) / np.sqrt(values["excess_quadratic"]))
                if target == "cml_rate":
                    np.testing.assert_allclose(values["signed_weights"], 0.0)
                    self.assertEqual(values["signed_cash"], 1.0)
                    self.assertEqual(values["signed_vol"], 0.0)
                elif target == "0.04":
                    self.assertLess(values["signed_return"], values["cml_rate"])
                    self.assertGreater(values["signed_vol"], 0.0)
                else:
                    self.assertLess(values["signed_cash"], 0.0)

    def test_lower_cash_rate_makes_signed_tangency_long_only_feasible(self):
        values = self.execute_cml(quoted_rate=0.02)
        self.assertTrue((values["signed_tangent_weights"] > 0).all())
        np.testing.assert_allclose(values["tangent_weights"], values["signed_tangent_weights"], atol=1e-5)
        self.assertAlmostEqual(values["signed_tangent_sharpe"], values["tangent_sharpe"], places=8)
        np.testing.assert_allclose(values["_payloads"][0]["cml_plot"]["series"]["Frontier"],
                                   values["df_frontier"][["volatility", "return"]] * 100)

    def test_cml_charts_use_percent_units_and_include_the_cash_intercept(self):
        values = self.execute_cml()
        first, comparison, signed = [next(iter(payload.values())) for payload in values["_payloads"]]
        for chart in (first, comparison, signed):
            self.assertEqual(chart["type"], "line")
            self.assertEqual(chart["xAxis"]["min"], 0)
            self.assertEqual(chart["xAxis"]["name"], "Annualized volatility (%)")
            self.assertEqual(chart["yAxis"]["name"], "Estimated annual return (%)")
            self.assertNotIn("max", chart["xAxis"])
            self.assertNotIn("min", chart["yAxis"])
            self.assertNotIn("max", chart["yAxis"])
            for name, points in chart["series"].items():
                self.assertTrue(np.isfinite(np.asarray(points)).all())
                if "CAL" in name:
                    np.testing.assert_allclose(points[0], [0, values["cml_rate"] * 100])
        np.testing.assert_allclose(first["series"]["CAL"][-1], first["series"]["MSR"][0])
        np.testing.assert_allclose(first["series"]["Portfolios"][0], [values["combined_vol"] * 100, values["combined_return"] * 100])
        self.assertEqual(set(comparison["series"]), {"Frontier", "CAL", "MSR", "GMV", "EWP"})
        for name, row in values["cml_comparison"].iterrows():
            np.testing.assert_allclose(comparison["series"][name][0], row[["volatility", "return"]] * 100)
        np.testing.assert_allclose(signed["series"]["MSR"][0], [values["signed_tangent_vol"] * 100, values["signed_tangent_return"] * 100])
        np.testing.assert_allclose(signed["series"]["MinVolForTarget"][0], [values["signed_vol"] * 100, values["signed_return"] * 100])
        for name, slope in (("Long-only CAL", values["tangent_sharpe"]), ("Signed CAL", values["signed_tangent_sharpe"])):
            points = np.asarray(signed["series"][name])
            self.assertAlmostEqual((points[-1, 1] - points[0, 1]) / points[-1, 0], slope)


if __name__ == "__main__":
    unittest.main()
