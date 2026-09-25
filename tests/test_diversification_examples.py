"""Check industry inputs, allocation timing, and the reviewed rolling analytics."""

import contextlib
import __main__
import importlib.util
import io
import itertools
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
import PortfolioOptimizationKit as pok

from test_return_annualization import MODULE_PATHS, ROOT


class IndustryDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules = {}
        for i, path in enumerate(MODULE_PATHS):
            spec = importlib.util.spec_from_file_location(f"industry_copy_{i}", ROOT / path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cls.modules[path] = module

    def test_industry_loader_preserves_months_counts_sizes_and_decimal_returns(self):
        for path, module in self.modules.items():
            with self.subTest(module=path), patch.object(module, "path_to_data_folder", return_value=str(ROOT / "data")):
                for filetype, expected in (("rets", 0.0056), ("nfirms", 43.0), ("size", 35.98)):
                    frame = module.get_ind_file(filetype=filetype)
                    self.assertEqual(frame.shape, (1110, 30))
                    self.assertTrue(frame.index.equals(pd.period_range("1926-07", "2018-12", freq="M")))
                    self.assertAlmostEqual(frame.loc["1926-07", "Food"], expected)
                    self.assertTrue(np.isfinite(frame.to_numpy()).all())
                ew = module.get_ind_file(ew=True)
                vw = module.get_ind_file(ew=False)
                self.assertFalse(np.allclose(ew, vw))

    def test_industry_loader_maps_sentinels_before_scaling_and_rejects_duplicate_dates(self):
        with tempfile.TemporaryDirectory() as folder:
            filename = Path(folder) / "ind30_m_vw_rets.csv"
            filename.write_text(", Food , Beer \n200001,-99.99,2\n200002,1,-999\n")
            for path, module in self.modules.items():
                with self.subTest(module=path), patch.object(module, "path_to_data_folder", return_value=folder):
                    frame = module.get_ind_file()
                    self.assertEqual(frame.columns.tolist(), ["Food", "Beer"])
                    self.assertTrue(np.isnan(frame.iloc[0, 0]))
                    self.assertTrue(np.isnan(frame.iloc[1, 1]))
                    self.assertAlmostEqual(frame.iloc[0, 1], 0.02)
                    self.assertAlmostEqual(frame.iloc[1, 0], 0.01)
            filename.write_text(",Food\n200001,1\n200001,2\n")
            for path, module in self.modules.items():
                with self.subTest(module=path), patch.object(module, "path_to_data_folder", return_value=folder):
                    with self.assertRaisesRegex(ValueError, "unique, ordered monthly dates"):
                        module.get_ind_file()

    def test_browser_industry_inputs_match_the_tested_snapshot(self):
        for filename in ("ind30_m_vw_rets.csv", "ind30_m_nfirms.csv", "ind30_m_size.csv"):
            expected = pd.read_csv(ROOT / "data" / filename, index_col=0)
            for directory in ("assets/data", "public/assets/data", "docs/public/assets/data"):
                with self.subTest(filename=filename, directory=directory):
                    pd.testing.assert_frame_equal(pd.read_csv(ROOT / directory / filename, index_col=0), expected)


class DiversificationExamplesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        markdown = (ROOT / "docs/1.3-diversification.md").read_text()
        cls.examples = dict((editor, code) for code, editor in re.findall(
            r'```python:line-numbers\n(.*?)\n```\s*<Editor id="([^"]+)"\s*/>', markdown, re.DOTALL
        ))
        ids = re.findall(r'<Editor id="([^"]+)"', markdown)
        if len(ids) != len(cls.examples):
            raise AssertionError("Reviewed examples must have unique IDs and runnable Python fences")

    def execute_until(self, last_cell="calculating-indexes-10"):
        values = {"__name__": "__main__"}
        output = io.StringIO()
        with patch.object(pok, "path_to_data_folder", return_value=str(ROOT / "data")):
            with contextlib.redirect_stdout(output):
                for editor, code in self.examples.items():
                    exec(compile(code, f"1.3:{editor}", "exec"), values)
                    if editor == last_cell:
                        break
        values["_output"] = output.getvalue()
        return values

    def execute_cell(self, editor, values):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exec(compile(self.examples[editor], f"1.3:{editor}", "exec"), values)
        return output.getvalue()

    def test_equal_weight_diversification_matches_the_worked_limits(self):
        values = self.execute_until("diversification-correlation-floor")
        risks = values["diversification_risk"]
        np.testing.assert_allclose(risks.loc[1], 20.0)
        np.testing.assert_allclose(risks["Correlation 1.00"], 20.0)
        self.assertAlmostEqual(risks.loc[25, "Correlation 0.25"], 10.583005244258363)
        self.assertAlmostEqual(risks.loc[25, "Correlation 0.80"], 17.977764043395385)
        self.assertAlmostEqual(risks.loc[100, "Correlation 0.00"], 2.0)

    def test_capitalization_weights_and_chart_percentage_units(self):
        values = self.execute_until("calculating-indexes-4")
        self.assertAlmostEqual(values["ind_mkt_cap"].loc["1926-07", "Food"], 1547.14)
        self.assertAlmostEqual(values["total_mkt_cap"].loc["1926-07"], 26657.94)
        weights = values["ind_cap_weights"]
        np.testing.assert_allclose(weights.sum(axis=1), 1.0)
        self.assertAlmostEqual(weights.loc["1926-07", "Food"], 0.058036742523990985)
        self.assertEqual(values["plot_data"]["dates"][0], "1926-07")
        self.assertEqual(values["plot_data"]["dates"][-1], "2018-12")
        for name, points in values["plot_data"]["sectorWeights"]["series"].items():
            np.testing.assert_allclose(points, weights[name] * 100)

    def proxy_fixture(self):
        values = self.execute_until("utility-helpers")
        dates = pd.period_range("2000-01", periods=3, freq="M")
        values.update({
            "nind": 2,
            "ind_cap_weights": pd.DataFrame([[0.6, 0.4], [0.2, 0.8], [0.9, 0.1]], index=dates),
            "ind_rets": pd.DataFrame([[0.0, 0.0], [0.10, -0.05], [-0.10, 0.10]], index=dates),
        })
        return values

    def test_proxy_uses_prior_weights_and_includes_starting_capital(self):
        values = self.proxy_fixture()
        self.execute_cell("calculating-indexes-5", values)
        np.testing.assert_allclose(values["total_market_return"], [0.04, 0.06])
        np.testing.assert_allclose(values["total_market_index"], [1040.0, 1102.4])
        self.assertEqual(values["total_market_return_values"][0], None)
        np.testing.assert_allclose(values["total_market_return_values"][1:], [4.0, 6.0])
        self.assertEqual(values["total_market_index_values"][0], 1000)
        self.assertEqual(values["x_data"], ["2000-01", "2000-02", "2000-03"])
        values["ind_cap_weights"].iloc[1] = [1.0, 0.0]
        self.execute_cell("calculating-indexes-5", values)
        self.assertAlmostEqual(values["total_market_return"].iloc[0], 0.04)
        self.assertAlmostEqual(values["total_market_return"].iloc[1], -0.10)

    def test_missing_industry_return_is_not_replaced_by_zero(self):
        values = self.proxy_fixture()
        values["ind_rets"].iloc[1, 0] = np.nan
        output = self.execute_cell("calculating-indexes-5", values)
        self.assertTrue(np.isnan(values["total_market_return"].iloc[0]))
        self.assertAlmostEqual(values["total_market_return"].iloc[1], 0.06)
        self.assertTrue(values["total_market_index"].isna().all())
        chart = json.loads(output.split("<ECHARTS_DATA>")[1])
        self.assertEqual(chart["totalMarketIndex"]["series"]["Lagged industry proxy"], [1000, None, None])

    def test_moving_averages_keep_history_before_the_display_start(self):
        values = self.execute_until("calculating-indexes-6")
        display = values["display_averages"]
        self.assertEqual(str(display.index[0]), "1990-01")
        self.assertFalse(display.iloc[0].isna().any())
        for months in (60, 36, 12):
            history = values["total_market_index"].loc[:"1990-01"].iloc[-months:]
            self.assertAlmostEqual(display.iloc[0][f"{months}-month average"], history.mean())

    def test_rolling_growth_distinguishes_cumulative_and_annualized_returns(self):
        values = self.execute_until("utility-helpers")
        values["total_market_return"] = pd.Series(0.01, index=pd.period_range("2000-01", periods=38, freq="M"))
        self.execute_cell("calculating-indexes-7", values)
        self.assertTrue(values["tmi_trail_36_rets"].iloc[:35].isna().all())
        np.testing.assert_allclose(values["tmi_trail_36_rets"].iloc[35:], 1.01 ** 12 - 1)
        np.testing.assert_allclose(values["trailing_cumulative"].iloc[35:], 1.01 ** 36 - 1)
        chart = values["plot_data"]["rollingGrowth"]["series"]["Industry proxy"]
        self.assertEqual(chart[:35], [None] * 35)
        np.testing.assert_allclose(chart[35:], (1.01 ** 12 - 1) * 100)

    def test_average_correlation_excludes_diagonal_and_unavailable_pairs(self):
        values = self.execute_until("utility-helpers")
        dates = pd.period_range("2000-01", periods=3, freq="M")
        matrices = [np.array([[1, 0.2, 0.4], [0.2, 1, 0.6], [0.4, 0.6, 1]]),
                    np.full((3, 3), -0.4) + np.eye(3) * 1.4,
                    np.array([[1, np.nan, 0.4], [np.nan, np.nan, np.nan], [0.4, np.nan, 1]])]
        values.update({
            "nind": 3, "rolling_months": 36,
            "rets_trail_36_corr": pd.concat(dict(zip(dates, map(pd.DataFrame, matrices))), names=["date", "industry"]),
            "tmi_trail_36_rets": pd.Series([0.1, -0.1, 0.2], index=dates),
        })
        self.execute_cell("calculating-indexes-9", values)
        np.testing.assert_allclose(values["ind_trail_36_corr"], [0.4, -0.4, np.nan])
        self.assertEqual(len(values["rolling_comparison"]), 2)
        self.assertEqual(values["plot_data"]["rollingCorrelation"]["yAxis"]["min"], -1)
        np.testing.assert_allclose(values["plot_data"]["rollingReturn"]["series"]["Industry proxy"], [10.0, -10.0])

    def test_reviewed_sequence_matches_snapshot_and_independent_correlation_windows(self):
        values = self.execute_until()
        self.assertEqual(list(self.examples).index("calculating-indexes-10") + 1, 16)
        self.assertAlmostEqual(values["total_market_return"].iloc[0], 0.029000039237840586)
        self.assertEqual(len(values["total_market_return"]), 1109)
        self.assertEqual(values["rolling_comparison"].shape, (1074, 2))
        self.assertEqual(str(values["rolling_comparison"].index[0]), "1929-07")
        self.assertAlmostEqual(values["growth_correlation_relationship"], -0.28599574289605273)
        self.assertAlmostEqual(values["trailing_cumulative"].iloc[-1], 0.3139226226667797)
        self.assertAlmostEqual(values["tmi_trail_36_rets"].iloc[-1], 0.09527522328953797)
        for endpoint in ("1929-07", "2008-12", "2018-12"):
            date = pd.Period(endpoint, freq="M")
            observations = values["ind_rets"].loc[date - 35:date].to_numpy()
            correlation = np.corrcoef(observations, rowvar=False)
            expected = np.mean([correlation[i, j] for i, j in itertools.combinations(range(30), 2)])
            self.assertAlmostEqual(values["ind_trail_36_corr"].loc[date], expected)
        for line in values["_output"].splitlines():
            if line.startswith("<ECHARTS_DATA>"):
                payload = json.loads(line.split("<ECHARTS_DATA>")[1])
                for key, chart in payload.items():
                    if key != "dates":
                        for points in chart["series"].values():
                            self.assertEqual(len(points), len(payload["dates"]))

    def test_window_length_exercise_changes_both_return_and_correlation_windows(self):
        values = self.execute_until("calculating-indexes-6")
        for months in (12, 60):
            with self.subTest(months=months), contextlib.redirect_stdout(io.StringIO()):
                exec(self.examples["calculating-indexes-7"].replace("rolling_months = 36", f"rolling_months = {months}"), values)
                for cell in ("calculating-indexes-8", "calculating-indexes-9", "calculating-indexes-10"):
                    exec(self.examples[cell], values)
                self.assertEqual(len(values["rolling_comparison"]), 1110 - months)
                end_returns = values["total_market_return"].iloc[-months:]
                self.assertAlmostEqual(values["tmi_trail_36_rets"].iloc[-1], pok.annualize_rets(end_returns, 12))
                matrix = values["ind_rets"].iloc[-months:].corr()
                expected = np.mean([matrix.iloc[i, j] for i, j in itertools.combinations(range(30), 2)])
                self.assertAlmostEqual(values["ind_trail_36_corr"].iloc[-1], expected)

    def test_cppi_worked_path_and_gap_loss_exercise(self):
        values = self.execute_until("utility-helpers")
        self.execute_cell("cppi-worked-example", values)
        np.testing.assert_allclose(values["worked_path"]["Ending wealth"], [920, 940])
        np.testing.assert_allclose(values["worked_path"]["CPPI return (%)"], [-8, 100 * 20 / 920])
        with contextlib.redirect_stdout(io.StringIO()):
            exec(self.examples["cppi-worked-example"].replace("[-0.20, 0.25]", "[-0.30, 0.25]"), values)
        np.testing.assert_allclose(values["worked_path"]["Ending wealth"], [880, 880])
        self.assertTrue(values["worked_path"]["Floor breached"].all())

    def test_entire_reviewed_sequence_includes_fixed_floor_cppi_and_unique_ids(self):
        values = self.execute_until("cppi-floor-diagnostics")
        self.assertEqual(list(self.examples).index("cppi-floor-diagnostics") + 1, 27)
        self.assertEqual(values["risky_rets"].shape, (228, 3))
        self.assertTrue(values["cppi_rets"].index.equals(values["risky_rets"].index))
        self.assertEqual(str(values["cppi_rets"].index[0]), "2000-01")
        expected_first = 0.6 * values["risky_rets"].iloc[0] + 0.4 * values["safe_monthly_rate"]
        np.testing.assert_allclose(values["cppi_rets"].iloc[0], expected_first)
        np.testing.assert_allclose(1000 * (1 + values["cppi_rets"]).cumprod(), values["account_history"])
        self.assertEqual(values["comparison_display"].index.names, ["Strategy", "Industry"])
        self.assertAlmostEqual(values["comparison_display"].loc[("100% risky", "Beer"), "CAGR (%)"], 8.06, places=2)
        self.assertAlmostEqual(values["comparison_display"].loc[("Fixed-floor CPPI", "Beer"), "CAGR (%)"], 7.44, places=2)
        np.testing.assert_allclose(values["comparison_display"].loc["Fixed-floor CPPI", "CAGR (%)"],
                                   ((values["account_history"].iloc[-1] / 1000) ** (12 / 228) - 1) * 100)
        self.assertTrue((values["floor_diagnostics"]["Month-ends below floor"] == 0).all())
        self.assertAlmostEqual(values["floor_diagnostics"].loc["Steel", "Minimum wealth"], 807.691267, places=5)
        self.assertAlmostEqual(values["floor_diagnostics"].loc["Steel", "Maximum drawdown (%)"], 65.41, places=2)

    def test_cppi_charts_show_starting_capital_and_beginning_weights_in_percent(self):
        values = self.execute_until("cppi-5")
        charts = values["charts"]
        self.assertEqual(len(charts["dates"]), 229)
        self.assertEqual(charts["dates"][0], "1999-12")
        self.assertEqual(charts["dates"][-1], "2018-12")
        for sector in values["risky_rets"]:
            wealth = charts[f"{sector}_Cppi"]["series"]
            self.assertEqual(wealth["CPPI"][0], 1000)
            self.assertEqual(wealth["100% risky"][0], 1000)
            np.testing.assert_allclose(wealth["Fixed floor"], 800)
            np.testing.assert_allclose(wealth["CPPI"][1:], values["account_history"][sector])
            weights = charts[f"{sector}_Weight"]["series"]["Risky weight"]
            self.assertIsNone(weights[0])
            self.assertAlmostEqual(weights[1], 60.0)
            np.testing.assert_allclose(weights[1:], values["risky_w_history"][sector] * 100)
            self.assertEqual(charts[f"{sector}_Weight"]["yAxis"]["name"], "Risky allocation (%)")

    def test_cppi_reruns_restart_the_account_and_multiplier_exercises_change_initial_risk(self):
        values = self.execute_until("cppi-3")
        original = values["account_history"].copy()
        with patch.object(pok, "get_ind_file", side_effect=AssertionError("Reuse loaded industry returns")):
            self.execute_cell("cppi-3", values)
            pd.testing.assert_frame_equal(values["account_history"], original)
            for multiplier, expected in ((2, 0.4), (5, 1.0)):
                values["m"] = multiplier
                self.execute_cell("cppi-3", values)
                np.testing.assert_allclose(values["risky_w_history"].iloc[0], expected)
                np.testing.assert_allclose(1000 * (1 + values["cppi_rets"]).cumprod(), values["account_history"])

    def test_dynamic_worked_example_distinguishes_applied_and_next_floors(self):
        values = self.execute_until("utility-helpers")
        self.execute_cell("cppi-dynamic-worked-example", values)
        table = values["ratchet_path"]
        np.testing.assert_allclose(table["Floor used"], [800, 880, 880])
        np.testing.assert_allclose(table["Next floor"], [880, 880, 880])
        np.testing.assert_allclose(table["Ending wealth"], [1100, 990, 1045])
        np.testing.assert_allclose(table["Drawdown (%)"], [0, 10, 5], atol=1e-12)
        np.testing.assert_allclose(table["Risky weight (%)"], [100, 100, 100 * 5 / 9])
        with contextlib.redirect_stdout(io.StringIO()):
            exec(self.examples["cppi-dynamic-worked-example"].replace("[0.10, -0.10, 0.10]", "[0.10, -0.25, 0.10]"), values)
        np.testing.assert_allclose(values["ratchet_path"]["Ending wealth"], [1100, 825, 825])
        np.testing.assert_allclose(values["ratchet_path"]["Drawdown (%)"], [0, 25, 25], atol=1e-12)
        self.assertTrue(values["ratchet_example"]["Floor breaches"].iloc[1, 0])
        self.assertEqual(values["ratchet_path"]["Risky weight (%)"].iloc[-1], 0)

    def test_entire_reviewed_sequence_includes_dynamic_policy_and_matched_comparison(self):
        values = self.execute_until("cppi-8")
        self.assertEqual(list(self.examples).index("cppi-8") + 1, 31)
        self.assertEqual(values["sector"], "Fin")
        self.assertEqual(values["res"]["m"], 5)
        self.assertEqual(values["matched_fixed"]["m"], 5)
        self.assertEqual(values["comparison_returns"].shape, (228, 3))
        self.assertTrue(values["comparison_returns"].index.equals(values["risky_rets"].index))
        np.testing.assert_allclose(values["comparison_returns"].iloc[0], values["risky_rets"]["Fin"].iloc[0])
        self.assertAlmostEqual(values["dynamic_summary"].loc["High-water floor", "CAGR (%)"], 5.789755600649293)
        self.assertAlmostEqual(values["dynamic_summary"].loc["High-water floor", "Maximum drawdown (%)"], 19.828365634473608)
        self.assertAlmostEqual(values["dynamic_summary"].loc["Fixed floor", "CAGR (%)"], 3.5385400207160966)
        self.assertAlmostEqual(values["dynamic_summary"].loc["Fixed floor", "Maximum drawdown (%)"], 55.69939625473894)
        self.assertAlmostEqual(values["summary_df"].loc[40, "Maximum drawdown (%)"], 38.651226354108675)
        self.assertAlmostEqual(values["summary_df"].loc[60, "Maximum drawdown (%)"], 53.39930366010652)
        for target, result in values["drawdown_results"].items():
            self.assertEqual(result["m"], 1 / target)
            self.assertAlmostEqual(result["Risky allocation"].iloc[0, 0], 1)
            self.assertFalse(result["Floor breaches"].to_numpy().any())
        # The final 60% scenario must not overwrite the 20% baseline.
        pd.testing.assert_frame_equal(values["res"]["CPPI wealth"], values["drawdown_results"][0.20]["CPPI wealth"])

    def test_dynamic_charts_preserve_timing_dates_and_percent_units(self):
        values = self.execute_until("cppi-8")
        chart = values["dynamic_plot"]
        self.assertEqual(chart["dates"][0], "1999-12")
        self.assertEqual(len(chart["dates"]), 229)
        series = chart["wealthComparison"]["series"]
        self.assertEqual(series["CPPI"][0], 1000)
        self.assertEqual(series["High-water mark"][0], 1000)
        self.assertEqual(series["Floor for next allocation"][0], 800)
        np.testing.assert_allclose(series["Floor for next allocation"][1:], values["ending_peaks"] * 0.80)
        np.testing.assert_allclose(values["ending_floor"].iloc[:-1], values["res"]["Floor value"]["Fin"].iloc[1:])
        observed = chart["drawdownHistory"]["series"]["Observed drawdown"]
        self.assertEqual(observed[0], 0)
        np.testing.assert_allclose(observed[1:], -pok.drawdown(values["res"]["CPPI returns"]["Fin"])["Drawdown"] * 100, atol=1e-10)
        np.testing.assert_allclose(chart["drawdownHistory"]["series"]["Target"], 20)
        self.assertIsNone(chart["riskyAllocation"]["series"]["Risky weight"][0])
        np.testing.assert_allclose(chart["riskyAllocation"]["series"]["Risky weight"][1:], values["res"]["Risky allocation"]["Fin"] * 100)
        for payload in (chart, values["sensitivity_plot"]):
            for key, panel in payload.items():
                if key != "dates":
                    for points in panel["series"].values():
                        self.assertEqual(len(points), len(payload["dates"]))

    def test_dynamic_sector_and_tighter_target_exercises_keep_the_baseline(self):
        values = self.execute_until("cppi-floor-diagnostics")
        code = self.examples["cppi-6"].replace('sector = "Fin"', 'sector = "Steel"').replace("drawdown_limit = 0.20", "drawdown_limit = 0.10")
        with contextlib.redirect_stdout(io.StringIO()):
            exec(code, values)
        baseline = values["res"]["CPPI wealth"].copy()
        self.execute_cell("cppi-7", values)
        self.execute_cell("cppi-8", values)
        self.assertEqual(values["res"]["m"], 10)
        self.assertEqual(values["matched_fixed"]["m"], 10)
        self.assertEqual(values["res"]["CPPI wealth"].columns.tolist(), ["Steel"])
        pd.testing.assert_frame_equal(values["res"]["CPPI wealth"], baseline)
        actual_drawdown = values["observed_drawdown"]
        np.testing.assert_array_equal(values["res"]["Floor breaches"]["Steel"], actual_drawdown > 0.10 + 1e-10)
        self.assertGreater(values["res"]["Floor breaches"]["Steel"].sum(), 0)

    def test_gbm_one_period_matches_worked_prices_and_negative_euler_exercise(self):
        values = self.execute_until("utility-helpers")
        self.execute_cell("gbm-one-period", values)
        self.assertAlmostEqual(values["euler_step_return"], 0.04913460352255526)
        self.assertAlmostEqual(values["exact_step_log_return"], 0.04819710352255526)
        self.assertAlmostEqual(values["exact_step_return"], 0.049377470937769966)
        exercise = self.examples["gbm-one-period"].replace("gbm_frequency = 12", "gbm_frequency = 1").replace(
            "gbm_sigma = 0.15", "gbm_sigma = 0.50").replace("standardized_shock = 1.0", "standardized_shock = -3.0")
        with contextlib.redirect_stdout(io.StringIO()):
            exec(exercise, values)
        self.assertAlmostEqual(100 * (1 + values["euler_step_return"]), -43)
        self.assertAlmostEqual(100 * (1 + values["exact_step_return"]), 21.118938264097117)

    def test_entire_reviewed_sequence_includes_paired_gbm_simulation(self):
        values = self.execute_until("gbm-1")
        self.assertEqual(list(self.examples).index("gbm-1") + 1, 33)
        self.assertEqual(values["prices_1"].shape, (121, 10))
        self.assertEqual(values["prices_2"].shape, (121, 10))
        self.assertEqual(values["rets_1"].shape, (120, 10))
        self.assertAlmostEqual(values["model_terminal_mean"], 201.37527074704767)
        self.assertAlmostEqual(values["model_terminal_median"], 179.94840771282088)
        np.testing.assert_allclose(values["rets_1"].to_numpy() - values["log_rets_2"].to_numpy(), 0.15 ** 2 / 24, atol=1e-15)
        np.testing.assert_allclose(values["exact_simple_returns"], values["prices_2"].pct_change().iloc[1:], atol=1e-14)
        for key, prices in (("pricesCompounding", "prices_1"), ("pricesEquation", "prices_2")):
            chart = values["plot_data"][key]
            self.assertEqual(chart["xAxis"]["type"], "value")
            self.assertEqual(chart["xAxis"]["name"], "Elapsed years")
            for column, points in enumerate(chart["series"].values()):
                points = np.asarray(points)
                self.assertEqual(points.shape, (121, 2))
                np.testing.assert_allclose(points[:, 0], np.arange(121) / 12)
                np.testing.assert_allclose(points[:, 1], values[prices].iloc[:, column])
                np.testing.assert_allclose(points[0], [0, 100])

    def test_gbm_zero_volatility_exercise_and_repeated_seed(self):
        values = self.execute_until("utility-helpers")
        self.execute_cell("gbm-one-period", values)
        self.execute_cell("gbm-1", values)
        first = values["prices_2"].copy()
        self.execute_cell("gbm-1", values)
        pd.testing.assert_frame_equal(values["prices_2"], first)
        values["gbm_sigma"] = 0.0
        self.execute_cell("gbm-1", values)
        np.testing.assert_allclose(values["prices_2"].iloc[-1], 100 * np.exp(0.7))
        np.testing.assert_allclose(values["prices_1"].iloc[-1], 100 * (1 + 0.07 / 12) ** 120)

    def test_complete_chapter_executes_with_real_widget_defaults(self):
        import ipywidgets as widgets

        values = self.execute_until("cppi-widget")
        self.assertEqual(len(self.examples), 37)
        widget = values["widget_instance"]
        self.assertIsInstance(widget, widgets.Widget)
        self.assertEqual(widget.kwargs["n_years"], 3)
        self.assertEqual(widget.kwargs["n_scenarios"], 300)
        self.assertEqual(widget.kwargs["floor"], 0.80)
        self.assertEqual(widget.kwargs["seed"], 42)
        payload = json.loads(values["_output"].split("<ECHARTS_DATA>")[-1])
        self.assertEqual(payload["summary"]["floor_value"], 80)
        self.assertEqual(payload["summary"]["n_scenarios"], 300)
        self.assertEqual(payload["dates"], [str(i) for i in range(37)])
        self.assertIn("95% Wilson interval", values["_output"])
        widget.close()

    def test_widget_seed_changes_call_the_helper_and_serialize_named_controls(self):
        from ipywidgets.embed import dependency_state

        for editor in ("gbm-4", "cppi-widget"):
            with self.subTest(editor=editor):
                values = {"__name__": "__main__"}
                messages = []
                with patch.object(__main__, "_emit_echarts", messages.append, create=True):
                    self.execute_cell(editor, values)
                    self.assertEqual(len(messages), 1)
                    widget = values["widget_instance"]
                    controls = {child.description: child for child in widget.children if hasattr(child, "description")}
                    self.assertIn("seed", controls)
                    for child in controls.values():
                        if hasattr(child, "continuous_update"):
                            self.assertFalse(child.continuous_update)
                    with contextlib.redirect_stdout(io.StringIO()):
                        controls["seed"].value = 0
                    self.assertEqual(widget.kwargs["seed"], 0)
                    self.assertEqual(len(messages), 2)
                    self.assertNotEqual(messages[0], messages[1])
                    self.assertIn("seed=0", messages[-1])
                    state = dependency_state([widget])
                    self.assertTrue(any(record["state"].get("description") == "seed" for record in state.values()))
                    json.dumps(state)
                    widget.close()


if __name__ == "__main__":
    unittest.main()
