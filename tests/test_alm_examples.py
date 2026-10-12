"""Execute the complete ALM chapter against independent financial identities."""

import contextlib
import __main__
import io
import json
import re
import unittest
from unittest.mock import patch

import numpy as np
from test_return_annualization import ROOT


class AlmExamplesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        markdown = (ROOT / "docs/1.4-alm.md").read_text()
        cls.examples = dict((editor, code) for code, editor in re.findall(
            r'```python:line-numbers\n(.*?)\n```\s*<Editor id="([^"]+)"\s*/>', markdown, re.DOTALL
        ))
        ids = re.findall(r'<Editor id="([^"]+)"', markdown)
        if len(ids) != len(cls.examples) or markdown.count('```python') != len(cls.examples):
            raise AssertionError("Every ALM Python example must have a unique runnable Editor")

    def setUp(self):
        data_patch = patch("PortfolioOptimizationKit.path_to_data_folder", return_value=str(ROOT / "data") + "/")
        data_patch.start()
        self.addCleanup(data_patch.stop)

    def execute_until(self, last="alm-funding-sensitivity"):
        values = {"__name__": "__main__"}
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            for editor, code in self.examples.items():
                exec(compile(code, f"1.4:{editor}", "exec"), values)
                if editor == last:
                    break
        values["_output"] = output.getvalue()
        return values

    def test_future_and_present_values_use_a_consistent_three_year_comparison(self):
        values = self.execute_until("alm-discount-options")
        self.assertAlmostEqual(values["future_value"], 1092.727)
        np.testing.assert_allclose(values["payment_choices"], [1000, 915.1416593531595, 1006.6558252884755])
        self.assertAlmostEqual(values["future_value"] * values["discount_factor"], 1000)

    def test_scheduled_liabilities_and_funding_table_match_the_worked_amounts(self):
        values = self.execute_until("alm-funding-ratios")
        np.testing.assert_allclose(values["discounted_cashflows"]["Plan A"], [8000 / 1.05, 11000 / 1.05 ** 2, 6000 / 1.05 ** 3])
        np.testing.assert_allclose(values["liability_pv"], [
            8000 / 1.05 + 11000 / 1.05 ** 2 + 6000 / 1.05 ** 3,
            11000 / 1.05 + 2000 / 1.05 ** 2 + 15000 / 1.05 ** 3,
        ])
        self.assertLess(values["funding_ratios"]["Plan A"], 1)
        self.assertGreater(values["funding_ratios"]["Plan B"], 1)
        np.testing.assert_allclose(values["funding_summary"]["Surplus / deficit"], values["current_assets"] - values["liability_pv"])

    def test_reviewed_sequence_and_charts_reconcile_units_and_sensitivity(self):
        values = self.execute_until()
        self.assertEqual(list(self.examples).index("alm-funding-sensitivity") + 1, 8)
        self.assertAlmostEqual(values["selected_pv"], 8000 / 1.02 + 11000 / 1.02 ** 2 + 6000 / 1.02 ** 3)
        self.assertAlmostEqual(values["selected_funding_ratio"], 24000 / values["selected_pv"])
        self.assertTrue((np.diff(values["funding_by_rate"]) > 0).all())
        self.assertTrue((np.diff(values["funding_by_assets"]) > 0).all())
        chart = json.loads(values["_output"].split("<ECHARTS_DATA>")[1])
        rates = np.asarray(chart["rateSensitivity"]["series"]["Funding ratio"])
        assets = np.asarray(chart["assetSensitivity"]["series"]["Funding ratio"])
        np.testing.assert_allclose(rates[:, 0], values["rate_grid"] * 100)
        np.testing.assert_allclose(assets[:, 0], values["asset_grid"])
        np.testing.assert_allclose(assets[:, 1], values["asset_grid"] / values["selected_pv"])
        for panel in chart.values():
            np.testing.assert_allclose(np.asarray(panel["series"]["Target"])[:, 1], 1)
            self.assertEqual(panel["yAxis"]["name"], "Funding ratio")

    def test_zero_negative_rates_and_funding_sensitivity_exercises(self):
        for rate in (0.0, -0.01):
            values = self.execute_until("alm-python-modules")
            with contextlib.redirect_stdout(io.StringIO()):
                exec(self.examples["alm-future-value"].replace("annual_rate = 0.03", f"annual_rate = {rate}"), values)
                exec(self.examples["alm-discount-options"], values)
            self.assertAlmostEqual(values["future_value"] * values["discount_factor"], 1000)
            self.assertGreaterEqual(values["discount_factor"], 1)
        values = self.execute_until()
        with contextlib.redirect_stdout(io.StringIO()):
            exec(self.examples["alm-funding-case"].replace("selected_assets = 24000.0", "selected_assets = 25000.0"), values)
            exec(self.examples["alm-funding-sensitivity"], values)
        zero_rate = np.flatnonzero(np.isclose(values["rate_grid"], 0))[0]
        self.assertAlmostEqual(values["funding_by_rate"].iloc[zero_rate], 1)
        values = self.execute_until()
        baseline_rates = values["funding_by_rate"].copy()
        baseline_assets = values["funding_by_assets"].copy()
        with contextlib.redirect_stdout(io.StringIO()):
            exec(self.examples["alm-funding-case"].replace("selected_rate = 0.02", "selected_rate = 0.05"), values)
            exec(self.examples["alm-funding-sensitivity"], values)
        np.testing.assert_allclose(values["funding_by_rate"], baseline_rates)
        self.assertTrue((values["funding_by_assets"].iloc[1:] > baseline_assets.iloc[1:]).all())

    def test_nominal_and_continuous_examples_match_their_stated_balances(self):
        values = self.execute_until("alm-continuous-compounding")
        self.assertAlmostEqual(values["periodic_rate"], 0.10 / 12)
        self.assertAlmostEqual(values["effective_quote"], 0.10471306744129724)
        self.assertAlmostEqual(values["end_year_balance"], 1104.7130674412972)
        self.assertAlmostEqual(values["continuous_limit"], 0.10517091807564763)
        table = values["frequency_table"]
        self.assertAlmostEqual(table.loc[2, "Effective annual rate (%)"], 10.25)
        self.assertAlmostEqual(table.loc[12, "End-year balance"], 1104.7130674412972)
        self.assertTrue((np.diff(values["curve_rates"]) > 0).all())
        self.assertTrue((values["curve_rates"] < values["continuous_limit"]).all())
        chart = values["plot_data"]["compoundingFrequency"]
        curve = np.asarray(chart["series"]["Discrete"])
        np.testing.assert_array_equal(curve[:, 0], np.arange(1, 53))
        np.testing.assert_allclose(curve[:, 1], values["curve_rates"] * 100)
        np.testing.assert_allclose(np.asarray(chart["series"]["Continuous limit"])[:, 1], values["continuous_limit"] * 100)

    def test_complete_reviewed_sequence_preserves_value_across_rate_conventions(self):
        values = self.execute_until("alm-rate-consistent-valuation")
        self.assertEqual(list(self.examples).index("alm-rate-consistent-valuation") + 1, 12)
        self.assertAlmostEqual(values["equivalent_monthly_quote"], 0.0956896851468449)
        self.assertAlmostEqual(values["equivalent_continuous_quote"], 0.09531017980432487)
        np.testing.assert_allclose(values["quote_comparison"]["Effective annual check (%)"], 10)
        expected_pv = 8000 / 1.10 + 11000 / 1.10 ** 2 + 6000 / 1.10 ** 3
        np.testing.assert_allclose(values["consistent_present_values"], expected_pv, rtol=1e-13)

    def test_equivalent_quote_exercises_cover_cppi_cash_and_negative_rates(self):
        values = self.execute_until("alm-continuous-compounding")
        for rate in (0.03, -0.01):
            with self.subTest(rate=rate), contextlib.redirect_stdout(io.StringIO()):
                exec(self.examples["alm-equivalent-rate-quotes"].replace("effective_annual_quote = 0.10", f"effective_annual_quote = {rate}"), values)
                exec(self.examples["alm-rate-consistent-valuation"], values)
                expected = 8000 / (1 + rate) + 11000 / (1 + rate) ** 2 + 6000 / (1 + rate) ** 3
                np.testing.assert_allclose(values["consistent_present_values"], expected, rtol=1e-13)
                np.testing.assert_allclose(values["quote_comparison"]["Effective annual check (%)"], rate * 100)
                if rate == 0.03:
                    self.assertAlmostEqual(values["quote_comparison"].loc[12, "Periodic rate (%)"], 0.24662697723036864)
                else:
                    self.assertTrue((values["consistent_present_values"] > 25000).all())

    def test_cir_deterministic_example_matches_the_flat_discount_curve(self):
        values = self.execute_until("cir-deterministic-check")
        np.testing.assert_allclose(values["flat_rates"], 0.03)
        self.assertAlmostEqual(values["flat_bond_prices"].iloc[0, 0], 1 / 1.03 ** 3)
        self.assertEqual(values["flat_bond_prices"].iloc[-1, 0], 1)
        np.testing.assert_allclose(values["flat_check"].iloc[::12]["Elapsed years"], [0, 1, 2, 3])

    def test_reviewed_sequence_and_cir_widget_callback_execute(self):
        messages = []
        with patch.object(__main__, "_emit_echarts", messages.append, create=True):
            values = self.execute_until("cir-widget")
            self.assertEqual(list(self.examples).index("cir-widget") + 1, 15)
            self.assertEqual(len(messages), 2)  # Baseline and initial widget calculation.
            widget = values["widget_instance"]
            self.assertEqual(widget.kwargs["seed"], 42)
            controls = {child.description: child for child in widget.children if hasattr(child, "description")}
            with contextlib.redirect_stdout(io.StringIO()):
                controls["sigma"].value = 0
            self.assertEqual(widget.kwargs["sigma"], 0)
            self.assertEqual(len(messages), 3)
            chart = json.loads(messages[-1].split("<ECHARTS_DATA>")[1])
            np.testing.assert_allclose(chart["cirRates"]["series"]["Scenario 1"], chart["cirRates"]["series"]["Scenario 5"])
            widget.close()

    def test_hedging_examples_reconcile_the_budget_and_fixed_liability(self):
        values = self.execute_until("hedging-terminal-summary")
        self.assertAlmostEqual(values["full_matching_cost"], 0.7591534992842391)
        self.assertAlmostEqual(values["bond_face"], 0.9879424921404308)
        for strategy in ("cash_wealth", "bond_wealth"):
            np.testing.assert_allclose(values[strategy].iloc[0], 0.75, atol=1e-14)
        np.testing.assert_allclose(values["liability_values"].iloc[-1], 1)
        np.testing.assert_allclose(values["bond_funding"], values["initial_funding_ratio"], atol=1e-14)
        np.testing.assert_allclose(values["hedge_times"][[0, -1]], [0, 10])
        expected_cash = values["pok"].cir_cash_wealth(values["hedge_rates"], 0.75, **values["hedge_model"])
        np.testing.assert_allclose(values["cash_wealth"], expected_cash, rtol=1e-13)
        summary = values["terminal_summary"]
        self.assertEqual(summary.loc["Cash", "Shortfall share (%)"], 58.8)
        self.assertEqual(summary.loc["Matching bond", "Shortfall share (%)"], 100)
        np.testing.assert_allclose(summary.loc["Cash"].iloc[:3], [0.79600529, 0.95892377, 1.47724187], atol=1e-8)

    def test_hedging_widget_matches_the_worked_example_and_increased_capital(self):
        messages = []
        with patch.object(__main__, "_emit_echarts", messages.append, create=True):
            values = self.execute_until("hedging-widget")
            self.assertEqual(list(self.examples).index("hedging-widget") + 1, 22)
            self.assertIn("294/500 (58.8%)", messages[-1])
            before = json.loads(messages[-1].split("<ECHARTS_DATA>")[1])
            np.testing.assert_allclose(before["hedgingFunding"]["series"]["Cash 1"], values["funding_paths"]["Cash 1"])
            widget = values["widget_instance"]
            controls = {child.description: child for child in widget.children if hasattr(child, "description")}
            with contextlib.redirect_stdout(io.StringIO()):
                controls["initial_assets"].value = 0.80
            self.assertIn("fully funded or in surplus", messages[-1])
            after = json.loads(messages[-1].split("<ECHARTS_DATA>")[1])
            for name in ("Cash 1", "Matching bond"):
                old = np.asarray(before["hedgingFunding"]["series"][name])
                new = np.asarray(after["hedgingFunding"]["series"][name])
                np.testing.assert_allclose(new[:, 1], old[:, 1] * 0.80 / 0.75)
            widget.close()


    def test_coupon_schedule_price_and_reinvestment_match_hand_calculations(self):
        values = self.execute_until("coupon-yield-comparison")
        np.testing.assert_allclose(values["coupon_flows"][0], [1.5] * 5 + [101.5])
        np.testing.assert_allclose(values["coupon_times"], np.arange(1, 7) / 2)
        self.assertAlmostEqual(values["coupon_purchase_price"], 94.49187463842017)
        np.testing.assert_allclose(values["coupon_terminal_wealth"], [109, 109.58160509277343])
        np.testing.assert_allclose(values["coupon_realized_returns"], [0.04876296881450726, 0.050625])
        np.testing.assert_allclose(values["coupon_price_cases"]["Price"], [102.89773823728966, 100, 94.49187463842017])

    def test_coupon_paths_pay_once_and_include_the_correct_final_return(self):
        values = self.execute_until("coupon-constant-yield")
        prices, returns = values["coupon_price_paths"], values["coupon_total_returns"]
        self.assertEqual(prices.shape, (37, 5))
        self.assertAlmostEqual(prices.iloc[0, 0], 97.259015884847, places=5)
        np.testing.assert_array_equal(prices.iloc[-1], 0)
        self.assertEqual(values["coupon_payments"].sum(), 109)
        self.assertEqual(values["coupon_payments"].iloc[-1], 101.5)
        np.testing.assert_allclose(returns.iloc[-1], 101.5 / prices.iloc[-2] - 1)
        expected = values["pok"].bond_returns(bond_prices=prices, periods_per_year=12, **values["coupon_terms"])
        np.testing.assert_allclose(returns, expected, rtol=1e-12)
        np.testing.assert_allclose(values["coupon_flat_returns"], 1.025 ** (1 / 6) - 1, atol=1e-14)
        np.testing.assert_allclose(values["coupon_return_index"][0], 100)
        self.assertTrue((values["coupon_return_index"][-1] > 100).all())

    def test_coupon_widget_executes_and_frequency_changes_keep_par_identity(self):
        messages = []
        with patch.object(__main__, "_emit_echarts", messages.append, create=True):
            values = self.execute_until("coupon-widget")
            self.assertEqual(list(self.examples).index("coupon-widget") + 1, 30)
            widget = values["widget_instance"]
            controls = {child.description: child for child in widget.children if hasattr(child, "description")}
            with contextlib.redirect_stdout(io.StringIO()):
                controls["ytm"].value = 0.03
                controls["coupons_per_year"].value = 4
            plot = json.loads(messages[-1].split("<ECHARTS_DATA>")[1])
            np.testing.assert_allclose(plot["couponYield"]["series"]["Selected bond"], [[3, 100]])
            self.assertIn("coupon 0.75", messages[-1])
            widget.close()


    def test_duration_example_reuses_bond_values_and_reconciles_time_units(self):
        values = self.execute_until("duration-time-units")
        self.assertAlmostEqual(values["duration_table"]["PV weight"].sum(), 1)
        self.assertAlmostEqual(values["duration_table"]["PV weight"].iloc[-1], 101.5 / 1.025 ** 6 / 94.49187463842017)
        self.assertAlmostEqual(values["duration_years"], 2.887554933457737)
        self.assertAlmostEqual(values["duration_periods"] / 2, values["duration_years"])
        self.assertAlmostEqual(values["duration_from_years"], values["duration_years"])
        self.assertAlmostEqual(values["duration_effective_rate"], 0.050625)
        self.assertEqual(values["duration_year_flows"].columns.tolist(), ["Bond"])

    def test_zero_coupon_duration_is_fixed_while_price_changes(self):
        values = self.execute_until("duration-zero-coupon")
        table = values["duration_zero_check"]
        np.testing.assert_allclose(table["Macaulay duration (years)"], 3)
        self.assertTrue((np.diff(table["Price"]) < 0).all())

    def test_modified_duration_matches_the_stated_yield_shift_example(self):
        values = self.execute_until("duration-sensitivity")
        self.assertAlmostEqual(values["duration_modified"], 2.817126764349012)
        table = values["duration_sensitivity"].set_index("Yield change (bp)")
        self.assertAlmostEqual(table.loc[50, "Exact price change (%)"], -1.3967688922610133)
        self.assertAlmostEqual(table.loc[50, "Duration approximation (%)"], -1.408563382174506)
        np.testing.assert_allclose(table.loc[0], 0, atol=1e-12)

    def test_duration_widget_executes_and_updates_yield_shifts(self):
        messages = []
        with patch.object(__main__, "_emit_echarts", messages.append, create=True):
            values = self.execute_until("duration-widget")
            self.assertEqual(list(self.examples).index("duration-widget") + 1, 35)
            widget = values["widget_instance"]
            controls = {child.description: child for child in widget.children if hasattr(child, "description")}
            with contextlib.redirect_stdout(io.StringIO()):
                controls["shift_bps"].value = -50
            plots = json.loads(messages[-1].split("<ECHARTS_DATA>")[1])
            point = plots["durationSensitivity"]["series"]["Selected approximation"][0]
            np.testing.assert_allclose(point, [-50, values["duration_modified"] * 0.5])
            self.assertIn("not a payback date", messages[-1])
            widget.close()


    def test_ldi_portfolio_reconciles_market_value_weights_and_initial_deficit(self):
        values = self.execute_until("ldi-portfolio")
        self.assertAlmostEqual(values["ldi_liability_pv"], 130016.12184058645)
        self.assertAlmostEqual(values["ldi_liability_duration"], 10.960799385088393)
        np.testing.assert_allclose(values["ldi_prices"], [1081.1089577935502, 1135.903263449677])
        np.testing.assert_allclose(values["ldi_weights"], [0.48263092069478974, 0.5173690793052103])
        np.testing.assert_allclose(values["ldi_units"], [58.03487172872353, 59.21101072059471])
        self.assertAlmostEqual((values["ldi_units"] * values["ldi_prices"]).sum(), 130000)
        self.assertAlmostEqual(values["ldi_portfolio_pv"], 130000)
        self.assertAlmostEqual(values["ldi_portfolio_duration"], values["ldi_liability_duration"])
        self.assertLess(values["ldi_portfolio_pv"], values["ldi_liability_pv"])

    def test_ldi_sensitivity_keeps_holdings_fixed_and_curve_twist_breaks_full_funding(self):
        values = self.execute_until("ldi-curve-risk")
        ratios = values["ldi_ratios"]
        base_row = np.argmin(abs(ratios.index.to_numpy() - 0.04))
        np.testing.assert_allclose(ratios.iloc[base_row], 130000 / 130016.12184058645)
        self.assertAlmostEqual(values["ldi_stressed_values"]["Liability"], values["ldi_liability_pv"])
        self.assertLess(values["ldi_twist_ratio"], 0.96)
        full_pv = values["pok"].present_value(values["ldi_fully_funded"], values["ldi_rate"]).iloc[0]
        self.assertAlmostEqual(full_pv, values["ldi_liability_pv"])
        self.assertNotIn("funding_ratio", values)  # The public helper is not shadowed.

    def test_mixed_frequency_match_is_exact_on_the_common_effective_curve(self):
        values = self.execute_until("ldi-mixed-match")
        self.assertEqual(list(self.examples).index("ldi-mixed-match") + 1, 44)
        np.testing.assert_allclose(values["mixed_prices"], [1006.4081612573185, 1048.1159216388478])
        np.testing.assert_allclose(values["mixed_durations"], [10.742333260961377, 4.374877036571143])
        np.testing.assert_allclose(values["mixed_weights"], [0.37315385178027566, 0.6268461482197243])
        self.assertAlmostEqual(values["mixed_assets"], 427262.96920906723)
        self.assertAlmostEqual(values["mixed_portfolio_pv"], values["mixed_liability_pv"])
        self.assertAlmostEqual(values["mixed_portfolio_duration"], values["mixed_liability_duration"])
        self.assertAlmostEqual(values["mixed_liability_duration"], 6.75091785274465)

    def test_matching_widget_reports_infeasibility_and_recovers_with_named_controls(self):
        messages = []
        with patch.object(__main__, "_emit_echarts", messages.append, create=True):
            values = self.execute_until("ldi-matching-widget")
            widget = values["widget_instance"]
            controls = {child._kwarg: child for child in widget.children if hasattr(child, "_kwarg")}
            self.assertEqual(controls["asset_value"].description, "Assets ($)")
            self.assertIn("Initial funding ratio: 0.999876", messages[-1])
            with contextlib.redirect_stdout(io.StringIO()):
                controls["liability_delay"].value = 10
            text, encoded = messages[-1].split("<ECHARTS_DATA>")
            self.assertIn("No unique long-only duration match", text)
            self.assertEqual(json.loads(encoded), {})
            with contextlib.redirect_stdout(io.StringIO()):
                controls["liability_delay"].value = 0
                controls["asset_value"].value = 131000
            plot = json.loads(messages[-1].split("<ECHARTS_DATA>")[1])
            self.assertGreater(plot["matchingFunding"]["series"]["Initial matched"][0][1], 1)
            widget.close()


    def test_fixed_mix_lesson_aligns_simple_returns_and_actual_bond_maturities(self):
        values = self.execute_until("psp-lhp-fixed-mix")
        self.assertEqual(values["stock_rets"].shape, (20, 1000))
        np.testing.assert_allclose(values["stock_rets"], np.expm1(values["stock_log_rets"]))
        np.testing.assert_array_equal(values["bond_pr_short"].iloc[-1], 0)
        self.assertTrue((values["bond_pr_long"].iloc[-1] > 0).all())
        np.testing.assert_allclose(values["bond_rets_short"].iloc[-1], 101.4 / values["bond_pr_short"].iloc[-2] - 1)
        np.testing.assert_allclose(values["bond_rets_long"].iloc[-1],
                                   (values["bond_pr_long"].iloc[-1] + 1.75) / values["bond_pr_long"].iloc[-2] - 1)
        expected = 0.7 * values["stock_rets"] + 0.18 * values["bond_rets_short"] + 0.12 * values["bond_rets_long"]
        np.testing.assert_allclose(values["stock_bond_rets"], expected, atol=1e-15)
        bundled = values["pok"].simulate_psp_lhp()
        for name, returns in values["mix_returns"].items():
            np.testing.assert_allclose(returns, bundled[name])

    def test_fixed_mix_rebalance_is_self_financing_and_wealth_includes_time_zero(self):
        values = self.execute_until("psp-lhp-wealth")
        self.assertAlmostEqual(values["mix_first_wealth"], 109.43698055706683)
        self.assertAlmostEqual(values["mix_stock_transfer"], -2.4141455684591904)
        restored_stock = values["mix_first_stock"] + values["mix_stock_transfer"]
        restored_bond = values["mix_first_bond"] - values["mix_stock_transfer"]
        self.assertAlmostEqual(restored_stock + restored_bond, values["mix_first_wealth"])
        self.assertAlmostEqual(restored_stock / values["mix_first_wealth"], 0.7)
        for wealth in values["mix_wealth"].values():
            np.testing.assert_allclose(wealth.iloc[0], 1)
        self.assertFalse(np.allclose(values["mix_buy_hold"].iloc[-1], values["mix_wealth"]["Fixed mix"].iloc[-1]))

    def test_fixed_mix_terminal_units_and_widget_endpoints(self):
        messages = []
        with patch.object(__main__, "_emit_echarts", messages.append, create=True):
            values = self.execute_until("psp-lhp-widget")
            self.assertEqual(list(self.examples).index("psp-lhp-widget") + 1, 52)
            stats = values["mix_terminal_stats"]
            np.testing.assert_allclose(stats.loc["Mean wealth"], [2.010856, 1.341793, 1.783945], atol=1e-6)
            np.testing.assert_allclose(stats.loc["Terminal shortfalls (%)"], [0.1, 0, 0])
            widget = values["widget_instance"]
            controls = {child._kwarg: child for child in widget.children if hasattr(child, "_kwarg")}
            with contextlib.redirect_stdout(io.StringIO()):
                controls["psp_weight"].value = 0
            plots = json.loads(messages[-1].split("<ECHARTS_DATA>")[1])
            self.assertEqual(plots["pspLhpWealth"]["series"]["Fixed mix median"], plots["pspLhpWealth"]["series"]["Bonds median"])
            widget.close()


    def test_glide_schedule_applies_end_target_before_the_last_return(self):
        values = self.execute_until("glide-schedule")
        schedule = values["glide_schedule"]
        np.testing.assert_allclose(schedule.iloc[0], [0, 0.5, 80])
        np.testing.assert_allclose(schedule.iloc[-1], [9.5, 10, 20])
        self.assertEqual(len(schedule), 20)
        np.testing.assert_allclose(values["glide_weights"].iloc[:, 0], values["glide_weights"].iloc[:, -1])

    def test_glide_comparison_preserves_paired_scenarios_and_summary_units(self):
        values = self.execute_until("glide-terminal-stats")
        expected = values["glide_weights"] * values["stock_rets"] + (1 - values["glide_weights"]) * values["bond_rets"]
        np.testing.assert_allclose(values["stock_bond_rets_glide"], expected)
        self.assertAlmostEqual(values["glide_mean_target"], 0.5)
        self.assertAlmostEqual(values["glide_difference"].mean(), -0.0019846929698129063)
        self.assertAlmostEqual((values["glide_difference"] > 1e-10).mean(), 0.504)
        np.testing.assert_allclose(values["glide_stats"].loc["Mean wealth"], [1.643873, 1.645857, 1.783945], atol=1e-6)
        self.assertGreater(values["glide_stats"].loc["Terminal wealth std", "Glide path"],
                           values["glide_stats"].loc["Terminal wealth std", "Constant mean target"])

    def test_glide_widget_equal_endpoints_recover_a_constant_allocation(self):
        messages = []
        with patch.object(__main__, "_emit_echarts", messages.append, create=True):
            values = self.execute_until("glide-widget")
            self.assertEqual(list(self.examples).index("glide-widget") + 1, 56)
            widget = values["widget_instance"]
            controls = {child._kwarg: child for child in widget.children if hasattr(child, "_kwarg")}
            with contextlib.redirect_stdout(io.StringIO()):
                controls["start"].value = 0
                controls["end"].value = 0
            plots = json.loads(messages[-1].split("<ECHARTS_DATA>")[1])
            self.assertEqual(plots["glideWealth"]["series"]["Glide path"], plots["glideWealth"]["series"]["Constant mean target"])
            np.testing.assert_array_equal(np.asarray(plots["glideTargets"]["series"]["Glide path"])[:, 1], 0)
            widget.close()


    def test_floor_lesson_uses_beginning_prices_and_m1_matches_the_reserved_bond_identity(self):
        values = self.execute_until("floor-policy")
        prices = values["zcb_price"]
        self.assertEqual(prices.shape, (121, 1000))
        self.assertAlmostEqual(prices.iloc[0, 0], 0.7451130625496102)
        np.testing.assert_allclose(values["floor_runs"][1]["Risky allocation"].iloc[0], 1 - 0.8 * prices.iloc[0])
        expected = 0.8 * prices + (values["stock_price"] / values["stock_price"].iloc[0]).mul(1 - 0.8 * prices.iloc[0], axis=1)
        np.testing.assert_allclose(values["floor_runs"][1]["Wealth"], expected, rtol=1e-13)
        np.testing.assert_allclose(values["floor_trace"]["Decision year"].iloc[[0, -1]], [0, 119 / 12])

    def test_floor_stress_and_sample_statistics_do_not_turn_zero_observations_into_a_guarantee(self):
        values = self.execute_until("floor-comparison")
        table = values["floor_shock_table"]
        np.testing.assert_allclose(table["Initial stock weight (%)"], [24, 72, 100])
        np.testing.assert_allclose(table["Terminal wealth"], [0.92, 0.6547368421052632, 0.5])
        self.assertEqual(table.loc[1, "Terminal shortfall"], 0)
        self.assertGreater(table.loc[3, "Terminal shortfall"], 0)
        np.testing.assert_allclose(values["ldi_stats"].loc["Mean wealth", ["Floor m=1", "Floor m=3", "Floor m=5"]],
                                   [1.621178, 1.996878, 2.015875], atol=1e-6)
        for result in values["floor_runs"].values():
            self.assertFalse(result["Floor breaches"].to_numpy().any())

    def test_floor_widget_zero_multiplier_and_underfunded_promise(self):
        messages = []
        with patch.object(__main__, "_emit_echarts", messages.append, create=True):
            values = self.execute_until("floor-widget")
            self.assertEqual(list(self.examples).index("floor-widget") + 1, 62)
            widget = values["widget_instance"]
            controls = {child._kwarg: child for child in widget.children if hasattr(child, "_kwarg")}
            with contextlib.redirect_stdout(io.StringIO()):
                controls["m"].value = 0
            plots = json.loads(messages[-1].split("<ECHARTS_DATA>")[1])
            np.testing.assert_allclose(plots["floorWealth"]["series"]["Floor allocator"], plots["floorWealth"]["series"]["ZCB only"])
            with contextlib.redirect_stdout(io.StringIO()):
                controls["floor"].value = 1.6
            self.assertIn("initially underfunded", messages[-1])
            self.assertIn("1000/1000", messages[-1])
            widget.close()


    def test_drawdown_stress_distinguishes_peak_loss_from_terminal_shortfall(self):
        values = self.execute_until("drawdown-gap-check")
        cash, bond = values["drawdown_shock_runs"]["Cash"], values["drawdown_shock_runs"]["Bond-like"]
        np.testing.assert_allclose(cash["Wealth"].iloc[:, 0], [1.5, 1.05, 1.05])
        np.testing.assert_allclose(bond["Wealth"].iloc[:, 0], [1.5, 1.05, 0.945])
        np.testing.assert_allclose(cash["Floor value"].iloc[:, 0], [0.8, 1.2, 1.2])
        self.assertAlmostEqual(cash["Drawdown"].min().iloc[0], -0.3)
        self.assertAlmostEqual(bond["Drawdown"].min().iloc[0], -0.37)
        self.assertTrue((cash["Wealth"].iloc[-1] > 0.8).all())

    def test_drawdown_comparison_uses_common_curve_cash_and_actual_path_drawdowns(self):
        values = self.execute_until("drawdown-comparison")
        self.assertTrue((values["cash_rets"] >= 0).to_numpy().all())
        self.assertTrue((values["zcb_rets"] < 0).to_numpy().any())
        self.assertEqual(values["drawdown_zcb"]["m"], 5)
        np.testing.assert_allclose(values["drawdown_zcb"]["Risky allocation"].iloc[0], 1)
        stats = values["drawdown_summary"]
        self.assertAlmostEqual(stats.loc["Drawdown + ZCB", "Paths beyond limit (%)"], 0.6)
        self.assertEqual(stats.loc["Drawdown + ZCB", "Terminal below 0.8 (%)"], 0)
        self.assertEqual(stats.loc["Drawdown + cash", "Paths beyond limit (%)"], 0)
        np.testing.assert_allclose(stats.loc[["Drawdown + cash", "Drawdown + ZCB"], "Mean terminal wealth"],
                                   [1.789337, 1.788393], atol=1e-6)

    def test_drawdown_widget_switching_hedge_preserves_the_paired_comparison(self):
        messages = []
        with patch.object(__main__, "_emit_echarts", messages.append, create=True):
            values = self.execute_until("drawdown-widget")
            self.assertEqual(list(self.examples).index("drawdown-widget") + 1, 67)
            before = json.loads(messages[-1].split("<ECHARTS_DATA>")[1])
            widget = values["widget_instance"]
            controls = {child._kwarg: child for child in widget.children if hasattr(child, "_kwarg")}
            with contextlib.redirect_stdout(io.StringIO()):
                controls["hedge"].value = "zcb"
            after = json.loads(messages[-1].split("<ECHARTS_DATA>")[1])
            self.assertEqual(before["drawdownLoss"], after["drawdownLoss"])
            self.assertNotEqual(before["drawdownWealth"]["series"]["Policy wealth"], after["drawdownWealth"]["series"]["Policy wealth"])
            widget.close()


    def test_historical_proxy_lags_before_slicing_and_includes_the_first_return(self):
        values = self.execute_until("historical-policy")
        market = values["historical_market"]
        self.assertEqual(len(market), 348)
        self.assertEqual(str(market.index[0]), "1990-01")
        self.assertEqual(str(market.index[-1]), "2018-12")
        self.assertAlmostEqual(market.iloc[0, 0], -0.07241043202903033)
        np.testing.assert_allclose(values["hist_begin_weights"].loc["1990-01"],
                                   values["hist_capitalizations"].loc["1989-12"] / values["hist_capitalizations"].loc["1989-12"].sum())
        np.testing.assert_allclose(values["historical_proxy"], values["pok"].get_total_market_index_returns())
        wealth = values["historical_wealth"]
        self.assertEqual(str(wealth.index[0]), "1989-12")
        self.assertEqual(len(wealth), 349)
        np.testing.assert_allclose(wealth.iloc[0], 1)
        self.assertAlmostEqual(wealth.loc["1990-01", "Drawdown policy"], 1 + market.iloc[0, 0])

    def test_historical_metrics_and_drawdown_episode_match_the_worked_results(self):
        values = self.execute_until("historical-drawdown-episode")
        metrics = values["historical_metrics"]
        np.testing.assert_allclose(metrics["CAGR (%)"], [9.627380, 8.305769, 7.843334, 3], atol=1e-6)
        np.testing.assert_allclose(metrics["Worst drawdown (%)"], [-50.044883, -19.435695, -37.143685, 0], atol=1e-6)
        self.assertTrue(np.isnan(metrics.loc["Assumed cash", "Sharpe vs assumed cash"]))
        self.assertAlmostEqual(metrics.loc["Market proxy", "Sharpe vs assumed cash"], metrics.loc["Fixed 70/30", "Sharpe vs assumed cash"])
        self.assertEqual(str(values["historical_peak"]), "2007-10")
        self.assertEqual(str(values["historical_trough"]), "2009-02")
        self.assertAlmostEqual(values["historical_trough_value"] / values["historical_peak_value"] - 1, -0.19435695165966782)

    def test_historical_widget_restarts_window_and_preserves_assumptions(self):
        messages = []
        with patch.object(__main__, "_emit_echarts", messages.append, create=True):
            values = self.execute_until("historical-widget")
            self.assertEqual(list(self.examples).index("historical-widget") + 1, 72)
            widget = values["widget_instance"]
            controls = {child._kwarg: child for child in widget.children if hasattr(child, "_kwarg")}
            with contextlib.redirect_stdout(io.StringIO()):
                controls["start_year"].value = 2000
            plots = json.loads(messages[-1].split("<ECHARTS_DATA>")[1])
            self.assertEqual(plots["dates"][0], "1999-12")
            self.assertEqual(len(plots["dates"]), 229)
            self.assertEqual(plots["historicalWealth"]["series"]["Drawdown policy"][0], 1)
            self.assertIn("Cash is hypothetical", messages[-1])
            widget.close()


    def test_continuous_duration_worked_values_and_finite_repricing_error(self):
        values = self.execute_until("modified-duration-repricing")
        np.testing.assert_allclose(values["modified_flows"][0], [5] * 5 + [105])
        self.assertAlmostEqual(values["modified_price"], 94.213020554763)
        self.assertAlmostEqual(values["modified_mac"], 2.653010037390808)
        self.assertAlmostEqual(values["modified_slope"], -249.94808918469275)
        self.assertAlmostEqual(values["modified_dv01"], 0.024994808918469277)
        row = values["modified_repricing"].loc[10]
        np.testing.assert_allclose(row, [93.96342871603265, 93.9630724655783, 0.000356250454345286], atol=1e-12)
        self.assertTrue((values["modified_repricing"]["Exact minus estimate"] >= -1e-12).all())

    def test_equivalent_quotes_preserve_price_but_not_the_numeric_duration_derivative(self):
        values = self.execute_until("modified-duration-quotes")
        np.testing.assert_allclose(values["modified_quote_prices"], values["modified_price"], atol=1e-12)
        self.assertAlmostEqual(values["modified_nominal_quote"], 0.12367309309071924)
        self.assertAlmostEqual(values["modified_nominal_measures"]["Macaulay duration"], values["modified_mac"])
        self.assertAlmostEqual(values["modified_nominal_measures"]["Modified duration"], values["modified_mac"] / np.exp(0.06))
        shift = (values["modified_shifted_nominal"] - values["modified_nominal_quote"]) * 10000
        self.assertAlmostEqual(shift, 10.621020499307216)

    def test_complete_alm_sequence_and_continuous_widget_callback(self):
        messages = []
        with patch.object(__main__, "_emit_echarts", messages.append, create=True):
            values = self.execute_until("modified-duration-widget")
            self.assertEqual(len(self.examples), 77)
            self.assertIn("continuous annual yield: 12.0000%", messages[-1])
            self.assertIn("exact minus linear price: +0.000356", messages[-1])
            widget = values["widget_instance"]
            controls = {child._kwarg: child for child in widget.children if hasattr(child, "_kwarg")}
            with contextlib.redirect_stdout(io.StringIO()):
                controls["quote"].value = "nominal"
            plots = json.loads(messages[-1].split("<ECHARTS_DATA>")[1])
            self.assertEqual(plots["durationSensitivity"]["xAxis"]["name"], "Nominal YTM change (bp)")
            self.assertIn("nominal annual YTM compounded 2 times/year", messages[-1])
            widget.close()


if __name__ == "__main__":
    unittest.main()
