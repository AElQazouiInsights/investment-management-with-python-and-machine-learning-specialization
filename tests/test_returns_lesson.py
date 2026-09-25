"""Execute the reviewed Markdown examples against their worked answers."""

import contextlib
import io
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch
import warnings

import numpy as np
import pandas as pd


LESSON = Path(__file__).resolve().parents[1] / "docs" / "1.1-risks.md"


class ReturnsLessonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.markdown = LESSON.read_text()
        cls.examples = {
            editor_id: code
            for code, editor_id in re.findall(
                r'```python(?::line-numbers)?\n(.*?)\n```\s*<Editor id="([^"]+)"\s*/>',
                cls.markdown,
                flags=re.DOTALL,
            )
        }

    def execute_example(self, editor_id, prerequisites=(), initial_namespace=None):
        namespace = dict(initial_namespace or {})
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            for example_id in (*prerequisites, editor_id):
                exec(compile(self.examples[example_id], f"{LESSON.name}:{example_id}", "exec"), namespace)
        namespace["_output"] = output.getvalue()
        return namespace

    def execute_history_example(self, editor_id, prerequisites=()):
        import PortfolioOptimizationKit as pok

        # The browser mounts /assets/data; native tests use the same CSV snapshot.
        with patch.object(pok, "path_to_data_folder", return_value=str(LESSON.parents[1] / "data")):
            return self.execute_example(editor_id, prerequisites=prerequisites)

    def test_each_editor_has_a_unique_persistence_and_routing_id(self):
        ids = re.findall(r'<Editor\s+id="([^"]+)"', self.markdown)
        self.assertEqual(len(ids), len(set(ids)))

    def test_price_and_total_return(self):
        values = self.execute_example("simple-and-total-returns")
        self.assertAlmostEqual(values["price_return"], 0.04)
        self.assertAlmostEqual(values["total_return"], 0.06)

    def test_compounded_wealth(self):
        values = self.execute_example("compounding-returns")
        np.testing.assert_allclose(values["wealth"], [110.0, 99.0])
        self.assertAlmostEqual(values["cumulative_return"], -0.01)

    def test_arithmetic_and_geometric_mean(self):
        values = self.execute_example("arithmetic-and-geometric-returns")
        self.assertAlmostEqual(values["arithmetic_mean"], 0.0)
        self.assertAlmostEqual(values["geometric_mean"], -0.005012562893380035)

    def test_annualization_matches_the_worked_growth_rate(self):
        values = self.execute_example("annualizing-observed-returns")
        self.assertEqual(values["monthly_prices"].size, 13)
        self.assertEqual(values["observed_returns"].size, 12)
        expected = 0.12682503013196977
        self.assertAlmostEqual(values["annualized_return"], expected)
        self.assertAlmostEqual(
            values["pok"].annualize_rets(values["monthly_returns"], 12), expected
        )

    def test_annualized_sample_volatility(self):
        values = self.execute_example("annualizing-period-volatility")
        self.assertAlmostEqual(values["monthly_volatility"], 0.02309401076758503)
        self.assertAlmostEqual(values["annualized_volatility"], 0.08)

    def test_zero_volatility_does_not_imply_capital_preservation(self):
        values = self.execute_example("zero-volatility-concept")
        summary = values["summary"]
        np.testing.assert_allclose(
            summary["Cumulative return (%)"], [-11.36151282838708, 12.682503013196977]
        )
        np.testing.assert_allclose(summary["Annualized volatility (%)"], 0.0, atol=1e-12)

    def test_stock_example_reconciles_prices_returns_and_chart_units(self):
        values = self.execute_example("stock-analysis")
        np.testing.assert_allclose(values["stock_prices"].iloc[0], [100.0, 100.0])
        np.testing.assert_allclose(values["stock_prices"].iloc[-1], [106.00638048, 112.01089536])
        np.testing.assert_allclose(values["stock_returns"], values["scenario_returns"], atol=1e-14)
        np.testing.assert_allclose(
            values["summary"]["Ann. volatility (%)"], [8.197560612767679, 16.395121225535358]
        )

        payload = json.loads(values["_output"].split("<ECHARTS_DATA>")[1])
        self.assertEqual(len(payload["dates"]), 7)
        self.assertEqual(payload["dates"][0], "2023-12")
        for series in payload["stockPrices"]["series"].values():
            self.assertEqual(len(series), 7)
            self.assertEqual(series[0], 100.0)
        for name, series in payload["returns"]["series"].items():
            self.assertEqual(len(series), 7)
            self.assertIsNone(series[0])
            np.testing.assert_allclose(series[1:], values["scenario_returns"][name] * 100, atol=1e-12)

    def test_proportional_return_series_have_equal_return_on_risk(self):
        values = self.execute_example("return-on-risk", prerequisites=("stock-analysis",))
        np.testing.assert_allclose(values["return_on_risk"], [1.463850109422799] * 2)
        self.assertIn("Stock A: 1.464", values["_output"])

    def test_sharpe_example_matches_independent_worked_answers(self):
        values = self.execute_example("sharpe-ratio", prerequisites=("stock-analysis",))
        expected = [1.1028251818175097, 1.2833376456201542]
        self.assertAlmostEqual(values["period_risk_free"], 0.0024662697723036864)
        np.testing.assert_allclose(values["sharpe"], expected)
        np.testing.assert_allclose(values["toolkit_sharpe"], expected)

    def test_zero_benchmark_recovers_the_return_on_risk_ratio(self):
        values = self.execute_example("return-on-risk", prerequisites=("stock-analysis",))
        sharpe = values["pok"].sharpe_ratio(values["stock_returns"], 0.0, 12)
        np.testing.assert_allclose(sharpe, values["return_on_risk"])

    def test_later_risk_adjusted_comparison_uses_the_same_convention(self):
        import PortfolioOptimizationKit as pok

        # Exercise the later lesson cell on a small independently checkable fixture.
        returns = pd.DataFrame({"Lo 10": [0.04, 0.0, 0.04, 0.0]})
        values = self.execute_example("returns-analysis-2", initial_namespace={
            "pok": pok,
            "small_large_caps": returns,
            "annualized_volatility": pd.Series({"Lo 10": 0.08}),
        })
        self.assertAlmostEqual(values["return_on_risk"]["Lo 10"], 3.0)
        self.assertAlmostEqual(values["sharpe_ratio"]["Lo 10"], 2.630059534154447)

    def test_historical_chart_compounds_only_complete_calendar_years(self):
        values = self.execute_history_example("data-analysis")
        self.assertEqual(len(values["small_large_caps"]), 1110)
        yearly = values["yearly_returns"]
        self.assertEqual(yearly.index.tolist(), list(range(1927, 2019)))
        np.testing.assert_allclose(yearly.loc[1927], [0.45818620796552834, 0.2911537952546015])
        payload = json.loads(values["_output"].split("<ECHARTS_DATA>")[1])
        self.assertEqual(payload["dates"][0], "1927")
        self.assertEqual(len(payload["dates"]), 92)
        series = payload["smallLargeCaps"]["series"]
        self.assertAlmostEqual(series["Small caps (Lo 10)"][0], 45.818620796552834)
        self.assertAlmostEqual(series["Large caps (Hi 10)"][0], 29.11537952546015)
        self.assertTrue(all(len(points) == 92 for points in series.values()))

    def test_historical_growth_volatility_and_sharpe_match_the_lesson(self):
        values = self.execute_history_example("returns-analysis-2", prerequisites=(
            "data-analysis", "calculating-volatility", "returns-analysis-1"
        ))
        np.testing.assert_allclose(values["annualized_return"], [0.16746328575056202, 0.09280968108267196])
        np.testing.assert_allclose(values["annualized_volatility"], [0.3681930492499153, 0.18671598774331252])
        np.testing.assert_allclose(values["sharpe_ratio"], [0.493153181226732, 0.4115480495212484])

    def test_drawdown_worked_example_matches_the_hand_calculation(self):
        values = self.execute_example("drawdown-worked-example")
        result = values["example_drawdown"]
        np.testing.assert_allclose(result["Wealth"], [80.0, 100.0, 90.0, 94.5])
        np.testing.assert_allclose(result["Peaks"], [100.0] * 4)
        np.testing.assert_allclose(result["Drawdown"], [-0.20, 0.0, -0.10, -0.055], atol=1e-14)

    def test_historical_drawdown_chart_includes_initial_wealth_and_monthly_dates(self):
        values = self.execute_history_example("max-drawdown", prerequisites=("data-analysis",))
        drawdowns = values["drawdowns"]
        self.assertAlmostEqual(drawdowns["Small Caps"].iloc[0], -0.0145)
        np.testing.assert_allclose(drawdowns.min(), [-0.8330007793945303, -0.8400375277943124])
        self.assertEqual(drawdowns.idxmin().astype(str).tolist(), ["1932-05", "1932-05"])

        payload = values["plot_data"]
        self.assertEqual(len(payload["dates"]), 1111)
        self.assertEqual(len(set(payload["dates"])), 1111)
        self.assertEqual(payload["dates"][0], "1926-06")
        self.assertEqual(payload["dates"][-1], "2018-12")
        self.assertEqual([event["date"] for event in payload["crisis"]], ["1929-10", "2000-03", "2008-09"])
        for name in ("Small Caps", "Large Caps"):
            chart = payload[f"{name} wealth"]
            self.assertEqual(chart["yAxis"]["type"], "log")
            for points in chart["series"].values():
                self.assertEqual(len(points), 1111)
                self.assertEqual(points[0], 100.0)
            self.assertEqual(payload["drawdown"]["series"][name][0], 0.0)
            np.testing.assert_allclose(payload["drawdown"]["series"][name][1:], drawdowns[name] * 100)

    def test_crisis_windows_report_troughs_in_the_correct_episodes(self):
        values = self.execute_history_example("insights-for-historical-crisis", prerequisites=(
            "data-analysis", "max-drawdown"
        ))
        table = values["crisis_summary"].set_index(["Window", "Portfolio"])
        self.assertEqual(len(table), 6)
        dotcom_small = table.loc[("Dot-com decline (2000-2002)", "Small Caps")]
        self.assertEqual(dotcom_small["Trough month"], "2000-12")
        self.assertAlmostEqual(dotcom_small["Worst drawdown (%)"], 36.3423492420607)
        dotcom_large = table.loc[("Dot-com decline (2000-2002)", "Large Caps")]
        self.assertEqual(dotcom_large["Trough month"], "2002-09")
        self.assertAlmostEqual(dotcom_large["Worst drawdown (%)"], 49.52282104689134)
        for name, loss in (("Small Caps", 63.1206807725239), ("Large Caps", 52.80945042309304)):
            row = table.loc[("Global financial crisis (2007-2009)", name)]
            self.assertEqual(row["Trough month"], "2009-02")
            self.assertAlmostEqual(row["Worst drawdown (%)"], loss)

    def test_crisis_windows_keep_prior_peaks_and_skip_unobserved_episodes(self):
        # Peak = 120 in 1999, then wealth = 60 in Jan 2000: retain a 50% drawdown.
        returns = pd.DataFrame({"Lo 10": [0.20, -0.50], "Hi 10": [0.20, -0.50]},
                               index=pd.period_range("1999-12", periods=2, freq="M"))
        values = self.execute_example("insights-for-historical-crisis",
                                      prerequisites=("max-drawdown",),
                                      initial_namespace={"small_large_caps": returns})
        table = values["crisis_summary"]
        self.assertEqual(len(table), 2)
        self.assertEqual(set(table["Window"]), {"Dot-com decline (2000-2002)"})
        np.testing.assert_allclose(table["Worst drawdown (%)"], [50.0, 50.0])
        self.assertEqual(values["plot_data"]["crisis"], [])

    def test_gaussian_probabilities_use_the_specified_mean_and_volatility(self):
        values = self.execute_example("gaussian-probabilities")
        self.assertAlmostEqual(values["standardized_threshold"], -1.5)
        self.assertAlmostEqual(values["loss_probability"], 0.4012936743170763)
        self.assertAlmostEqual(values["tail_probability"], 0.06680720126885807)
        self.assertAlmostEqual(values["within_one_sigma"], 0.6826894921370859)
        self.assertAlmostEqual(values["density_at_mean"], 9.973557010035817)

    def test_standard_normal_quantiles_match_their_cdf_and_reflection(self):
        values = self.execute_example("quantiles")
        self.assertAlmostEqual(values["z_quantile"], 1.2815515655446004)
        self.assertAlmostEqual(values["probability_check"], 0.90)
        self.assertAlmostEqual(values["complementary_quantile"], -1.2815515655446004)

    def test_return_quantiles_distinguish_one_sided_and_central_probabilities(self):
        values = self.execute_example("gaussian-return-quantiles")
        self.assertAlmostEqual(values["left_tail_quantile"], -0.05579414507805889)
        self.assertAlmostEqual(values["tail_probability"], 0.025)
        self.assertAlmostEqual(values["lower"], -0.06839855938160215)
        self.assertAlmostEqual(values["upper"], 0.08839855938160216)
        self.assertAlmostEqual(values["coverage"], 0.95)

    def test_empirical_quantile_conventions_match_the_worked_interpolation(self):
        values = self.execute_example("empirical-return-quantiles")
        self.assertAlmostEqual(values["linear_quantile"], -0.043)
        self.assertAlmostEqual(values["empirical_quantile"], -0.07)
        self.assertIn("Linear-interpolated 10% return quantile: -4.30%", values["_output"])

    def test_moment_example_uses_consistent_denominators(self):
        values = self.execute_example("moment-estimators")
        self.assertAlmostEqual(values["m2"], 0.0004)
        self.assertAlmostEqual(values["sample_skewness"], -1.5)
        self.assertAlmostEqual(values["sample_kurtosis"], 3.25)
        self.assertIn("Excess kurtosis: 0.250", values["_output"])

    def test_shape_comparison_is_reproducible_and_uses_common_normalized_bins(self):
        values = self.execute_history_example("skewness-kurtosis")
        self.assertEqual(len(values["shape_samples"]), 1110)
        self.assertAlmostEqual(values["market_z"].mean(), 0.0)
        self.assertAlmostEqual(values["market_z"].std(ddof=0), 1.0)
        np.testing.assert_allclose(values["shape_comparison"]["Skewness"],
                                   [-0.04133680236845134, 0.23344521725825906])
        np.testing.assert_allclose(values["shape_comparison"]["Pearson kurtosis"],
                                   [3.0966278733086168, 10.694653941150047])
        payload = json.loads(values["_output"].split("<ECHARTS_DATA>")[1])
        chart = payload["distributionComparison"]
        self.assertEqual(chart["xAxis"]["type"], "value")
        self.assertEqual(chart["yAxisName"], "Density")
        for points in chart["series"].values():
            points = np.asarray(points)
            self.assertEqual(points.shape, (40, 2))
            np.testing.assert_allclose(points[:, 0], values["bin_centers"])
            self.assertTrue((points[:, 1] >= 0).all())
            self.assertAlmostEqual(np.dot(points[:, 1], np.diff(values["bin_edges"])), 1.0)

    def test_hedge_fund_normality_results_match_moments_and_stated_decisions(self):
        values = self.execute_history_example("normality-test", prerequisites=(
            "skewness-kurtosis-hedge-funds", "jarque-bera-test"
        ))
        moments = values["hfi_skew_kurt"]
        self.assertTrue((moments["Observations"] == 263).all())
        self.assertAlmostEqual(moments.loc["CTA Global", "Skewness"], 0.173699, places=5)
        self.assertAlmostEqual(moments.loc["CTA Global", "Pearson kurtosis"], 2.952960, places=5)
        self.assertAlmostEqual(moments.loc["Convertible Arbitrage", "Skewness"], -2.639592, places=5)
        self.assertAlmostEqual(moments.loc["Convertible Arbitrage", "Pearson kurtosis"], 23.280834, places=5)
        comparison = values["jb_comparison"]
        np.testing.assert_allclose(comparison["JB (formula)"], comparison["JB (SciPy)"], rtol=1e-12)
        self.assertAlmostEqual(comparison.loc["CTA Global", "JB (formula)"], 1.346753, places=5)
        self.assertAlmostEqual(comparison.loc["CTA Global", "p-value"], 0.5099837, places=6)
        decisions = values["normality_table"]["Decision"]
        self.assertEqual(decisions[decisions == "Do not reject"].index.tolist(), ["CTA Global"])
        self.assertEqual((decisions == "Reject").sum(), 12)

    def test_stricter_significance_threshold_changes_decisions_not_data(self):
        values = self.execute_history_example("normality-test", prerequisites=(
            "skewness-kurtosis-hedge-funds", "jarque-bera-test"
        ))
        result = values["pok"].is_normal(values["hfi"], level=1e-8)
        self.assertEqual(result[result].index.tolist(), ["CTA Global", "Long/Short Equity"])

    def test_unavailable_jarque_bera_result_is_not_reported_as_nonrejection(self):
        import PortfolioOptimizationKit as pok

        constant_returns = pd.DataFrame({"CTA Global": [0.0] * 6, "Convertible Arbitrage": [0.0] * 6})
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            values = self.execute_example("jarque-bera-test", initial_namespace={
                "hfi": constant_returns, "pd": pd, "pok": pok,
            })
        self.assertTrue(values["jb_comparison"]["p-value"].isna().all())
        self.assertEqual(values["jb_comparison"]["Decision"].tolist(), ["Unavailable", "Unavailable"])

    def test_semivolatility_and_target_deviation_answer_different_questions(self):
        values = self.execute_example("semivolatility")
        self.assertAlmostEqual(values["negative_volatility"], 0.01)
        self.assertAlmostEqual(values["downside_deviation"], 0.022360679774997897)

    def test_var_worked_example_matches_return_loss_and_currency_conventions(self):
        values = self.execute_example("historical-var-worked-example")
        for name in ("var_from_returns", "var_from_losses", "historical_var"):
            self.assertAlmostEqual(values[name], 0.043)
        self.assertIn("$4,300.00", values["_output"])

    def test_es_worked_example_includes_fractional_boundary_observation(self):
        values = self.execute_example("historical-es-worked-example")
        self.assertAlmostEqual(values["tail_mass"], 2.5)
        np.testing.assert_allclose(values["weights"], [1, 1, 0.5, 0, 0, 0, 0, 0, 0, 0])
        self.assertAlmostEqual(values["empirical_es"], 0.048)
        self.assertAlmostEqual(values["toolkit_es"], 0.048)

    def test_cta_histogram_uses_percentage_return_coordinates_and_density_units(self):
        values = self.execute_history_example("historical-var-1")
        self.assertEqual(len(values["cta_returns"]), 263)
        payload = json.loads(values["_output"].split("<ECHARTS_DATA>")[1])
        chart = payload["ctaDistribution"]
        self.assertEqual(chart["xAxis"]["type"], "value")
        self.assertEqual(chart["xAxis"]["name"], "Monthly return (%)")
        points = np.asarray(chart["series"]["Density"])
        self.assertEqual(points.shape, (30, 2))
        np.testing.assert_allclose(points[:, 0], values["bin_centers"])
        self.assertAlmostEqual(np.dot(points[:, 1], np.diff(values["bin_edges"])), 1.0)
        self.assertAlmostEqual(values["bin_edges"][0], values["cta_returns"].min() * 100)
        self.assertAlmostEqual(values["bin_edges"][-1], values["cta_returns"].max() * 100)

    def test_historical_tail_table_matches_the_snapshot_and_tail_sample_sizes(self):
        values = self.execute_history_example("historical-var-2", prerequisites=("historical-var-1",))
        table = values["tail_comparison"]
        self.assertEqual(table.index.tolist(), ["90%", "95%", "99%"])
        np.testing.assert_allclose(table["Historical VaR (%)"], [2.406, 3.169, 4.9542])
        np.testing.assert_allclose(table["Historical ES (%)"], [3.5008745247148296, 4.188250950570342, 5.498707224334601])
        np.testing.assert_allclose(table["Tail mass (observations)"], [26.3, 13.15, 2.63])

    def test_gaussian_var_lesson_uses_lower_tail_quantiles(self):
        values = self.execute_history_example("gaussian-var")
        self.assertAlmostEqual(values["model_var"], 0.05579414507805889)
        self.assertAlmostEqual(values["gaussian_var"]["CTA Global"], 0.03423511714224964)

    def test_cornish_fisher_example_matches_the_explicit_expansion(self):
        values = self.execute_history_example("cornish-fisher-var")
        self.assertAlmostEqual(values["modified_var"], 0.033094074646573754)
        self.assertAlmostEqual(values["toolkit_modified_var"], 0.033094074646573754)

    def test_risk_comparison_distinguishes_var_and_es_and_scales_chart_values(self):
        values = self.execute_history_example("var-methods-comparison")
        comparison = values["risk_comparison"]
        self.assertEqual(comparison.shape, (13, 4))
        self.assertEqual(comparison.columns.tolist(), ["Historical VaR", "Gaussian VaR", "Cornish-Fisher VaR", "Historical ES"])
        np.testing.assert_allclose(comparison.loc["CTA Global"],
                                  [0.03169, 0.03423511714224964, 0.033094074646573754, 0.04188250950570342])
        chart = values["plot_data"]["varComparison"]
        self.assertEqual(chart["xAxis"]["data"], comparison.index.tolist())
        for name, points in chart["series"].items():
            np.testing.assert_allclose(points, comparison[name] * 100)

    def test_entire_chapter_executes_in_document_order_in_one_session(self):
        editor_ids = list(self.examples)
        self.assertEqual(len(editor_ids), 33)
        self.assertEqual(editor_ids[-1], "var-methods-comparison")
        values = self.execute_history_example(editor_ids[-1], prerequisites=tuple(editor_ids[:-1]))
        self.assertEqual(values["risk_comparison"].shape, (13, 4))
        self.assertIn("95% monthly loss measures", values["_output"])


if __name__ == "__main__":
    unittest.main()
