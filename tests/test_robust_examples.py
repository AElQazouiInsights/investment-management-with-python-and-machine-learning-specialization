"""Worked answers, allocation dates, drift, and self-financed trading costs."""
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


class RobustExampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.markdown = (ROOT / "docs/2.4-robust-portfolios.md").read_text()
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

    def test_all_examples_and_chart_payloads_are_present_and_runnable(self):
        ids = re.findall(r'<Editor id="([^"]+)"', self.markdown)
        self.assertEqual(ids, list(self.examples))
        self.assertEqual(len(ids), 18)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(self.markdown.count("```python"), 18)
        self.assertEqual(sum(isinstance(value, dict) and "series" in value for payload in self.payloads for value in payload.values()), 8)

    def test_worked_attribution_and_risk_budget_results(self):
        v = self.values
        np.testing.assert_allclose(v["equal_report"]["Relative risk"], [0.75, 0.25])
        self.assertAlmostEqual(v["equal_volatility"], np.sqrt(0.015))
        np.testing.assert_allclose(v["one_factor_shares"], [0.25] * 4)
        np.testing.assert_allclose(v["erc_weights"], [1/3, 2/3], atol=1e-8)
        np.testing.assert_allclose(v["achieved_budgets"], [0.2, 0.3, 0.5], atol=1e-8)
        np.testing.assert_allclose(pok.portfolio_risk_contributions(v["three_inverse"], v["three_covariance"]),
                                   [1.7/4.8, 1.8/4.8, 1.3/4.8])
        np.testing.assert_allclose(pok.portfolio_risk_contributions(v["three_erc"], v["three_covariance"]), [1/3] * 3, atol=1e-8)

    def test_every_strategy_has_common_complete_evaluation_dates(self):
        v = self.values
        self.assertEqual(v["gross_returns"].shape, (288, 5))
        self.assertEqual(str(v["evaluation_dates"][0]), "1995-01")
        self.assertEqual(str(v["evaluation_dates"][-1]), "2018-12")
        self.assertTrue(np.isfinite(v["gross_returns"].to_numpy()).all())
        for name, weights in v["weight_history"].items():
            pd.testing.assert_index_equal(weights.index, v["evaluation_dates"])
            np.testing.assert_allclose(weights.sum(axis=1), 1, atol=1e-8)
            self.assertTrue((weights >= -1e-9).all().all())
            np.testing.assert_allclose(v["gross_returns"][name], np.einsum('ij,ij->i', weights, v["evaluation_assets"]))
        manual_cw = (v["industry_cap_weights"].shift(1).loc[v["evaluation_dates"]] * v["evaluation_assets"]).sum(axis=1)
        np.testing.assert_allclose(v["gross_returns"]["CW"], manual_cw)

    def test_selected_erc_allocations_meet_their_prior_window_risk_model(self):
        v = self.values
        for month in ("1995-01", "2009-01", "2018-12"):
            t = v["industry_returns"].index.get_loc(month)
            history = v["industry_returns"].iloc[t-60:t]
            for name, estimator in (("ERC", pok.sample_cov), ("ERC shrinkage", pok.shrinkage_cov)):
                w = v["weight_history"][name].loc[month].to_numpy()
                covariance = estimator(history).to_numpy()
                shares = w * (covariance @ w) / (w @ covariance @ w)
                np.testing.assert_allclose(shares, np.repeat(1/30, 30), atol=1e-7)
        self.assertEqual(str(v["decision_training"].index[0]), "2004-01")
        self.assertEqual(str(v["decision_training"].index[-1]), "2008-12")
        np.testing.assert_allclose(v["decision_shares"]["ERC"], np.repeat(1/30, 30), atol=1e-7)
        self.assertFalse(np.allclose(v["decision_shares"]["ERC shrinkage"], 1/30))

    def test_bootstrap_uses_paired_resamples_and_both_strategies_use_shrinkage(self):
        v = self.values
        self.assertEqual(v["allocation_sensitivity"].shape, (30, 2))
        for name in ("GMV", "ERC"):
            weights = pd.DataFrame(v["bootstrap_allocations"][name])
            self.assertEqual(weights.shape, (40, 30))
            np.testing.assert_allclose(weights.sum(axis=1), 1)
            np.testing.assert_allclose(weights.std(ddof=1) * 100, v["allocation_sensitivity"][name])
        rows = np.random.default_rng(42).integers(0, 60, size=60)
        covariance = pok.shrinkage_cov(v["first_training"].iloc[rows].reset_index(drop=True))
        first_erc = v["bootstrap_allocations"]["ERC"][0]
        np.testing.assert_allclose(pok.portfolio_risk_contributions(first_erc, covariance), 1/30, atol=1e-7)

    def test_drifted_weights_and_turnover_match_hand_calculation(self):
        v = self.values
        np.testing.assert_allclose(v["drifted_weights"], [0.55, 0.45])
        self.assertAlmostEqual(v["worked_turnover"], 0.05)
        self.assertTrue((v["turnover"].iloc[0] == 0).all())
        targets = v["weight_history"]["EW"]
        self.assertTrue((targets.diff().iloc[1:].abs().sum(axis=1) == 0).all())
        self.assertGreater(v["turnover"]["EW"].iloc[1:].sum(), 0)
        for name, drift in v["pretrade_weights"].items():
            np.testing.assert_allclose(drift.sum(axis=1), 1, atol=1e-8)
            expected = v["weight_history"][name].iloc[0] * (1 + v["evaluation_assets"].iloc[0]) / (1 + v["gross_returns"][name].iloc[0])
            np.testing.assert_allclose(drift.iloc[1], expected)

    def test_fees_are_self_financed_and_net_returns_reconcile_to_asset_positions(self):
        v = self.values
        for name, weights in v["weight_history"].items():
            remaining = v["after_cost_fractions"][name]
            traded = weights.mul(remaining, axis=0).sub(v["pretrade_weights"][name]).abs().sum(axis=1)
            np.testing.assert_allclose(1 - remaining, v["fee_rate"] * traded, atol=1e-12)
            end_positions = weights.mul(remaining, axis=0) * (1 + v["evaluation_assets"])
            np.testing.assert_allclose(v["net_returns"][name], end_positions.sum(axis=1) - 1, atol=1e-12)
            self.assertEqual(remaining.iloc[0], 1)
            self.assertTrue((remaining <= 1).all() and (remaining > 0).all())
        self.assertTrue((v["net_wealth"].iloc[-1] < v["gross_wealth"].iloc[-1]).all())

    def run_cost_cell(self, cost_bps, overrides=None):
        namespace = {**self.values, **(overrides or {})}
        code = self.examples["robust-transaction-costs"].replace("cost_bps = 10.0", f"cost_bps = {cost_bps!r}")
        with contextlib.redirect_stdout(io.StringIO()):
            exec(code, namespace)
        return namespace

    def test_cost_experiment_zero_and_higher_costs_hold_strategies_fixed(self):
        zero, high = self.run_cost_cell(0.0), self.run_cost_cell(50.0)
        np.testing.assert_allclose(zero["net_returns"], self.values["gross_returns"], atol=1e-15)
        self.assertTrue((high["net_wealth"].iloc[-1] < self.values["net_wealth"].iloc[-1]).all())

    def test_fee_financing_matches_closed_form_for_a_two_asset_rebalance(self):
        dates = pd.period_range("2024-01", periods=2, freq="M")
        targets = pd.DataFrame([[0.5, 0.5], [0.8, 0.2]], index=dates, columns=["A", "B"])
        drift = pd.DataFrame([[0.5, 0.5], [0.5, 0.5]], index=dates, columns=targets.columns)
        result = self.run_cost_cell(10.0, {
            "evaluation_dates": dates, "weight_history": {"Case": targets}, "pretrade_weights": {"Case": drift},
            "gross_returns": pd.DataFrame({"Case": [0, 0.01]}, index=dates),
            "turnover": pd.DataFrame({"Case": [0, 0.3]}, index=dates),
        })
        # Buys+sales = .6*a, so a = 1/(1+.001*.6), not simply 1-.0006.
        remaining = 1 / 1.0006
        self.assertAlmostEqual(result["after_cost_fractions"]["Case"].iloc[1], remaining)
        self.assertAlmostEqual(result["net_returns"]["Case"].iloc[1], remaining * 1.01 - 1)

    def test_risk_scaling_preserves_relative_shares_but_requires_borrowing(self):
        v = self.values
        self.assertAlmostEqual(v["erc_volatility"], np.sqrt(1/90))
        self.assertAlmostEqual(v["risky_fraction"], 0.20 / np.sqrt(1/90))
        self.assertLess(v["cash_weight"], 0)
        self.assertAlmostEqual(v["scaled_exposures"].sum() + v["cash_weight"], 1)
        np.testing.assert_allclose(pok.portfolio_risk_contributions(v["scaled_exposures"], v["annual_covariance"]), [0.5, 0.5])


if __name__ == "__main__":
    unittest.main()
