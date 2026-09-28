"""Validate Monte Carlo event definitions, chart units, and widget output delivery."""

import __main__
import contextlib
import importlib.util
import io
import json
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from test_return_annualization import MODULE_PATHS, ROOT


class SimulationChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules = {}
        for i, path in enumerate(MODULE_PATHS):
            spec = importlib.util.spec_from_file_location(f"simulation_chart_copy_{i}", ROOT / path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cls.modules[path] = module

    def capture(self, function, **kwargs):
        messages = []
        output = io.StringIO()
        with patch.object(__main__, "_emit_echarts", messages.append, create=True), contextlib.redirect_stdout(output):
            result = function(**kwargs)
        self.assertIsNone(result)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(len(messages), 1)
        text, payload = messages[0].split("<ECHARTS_DATA>")
        return text, json.loads(payload)

    def test_gbm_chart_is_exact_seeded_and_includes_time_zero(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                inputs = dict(n_years=1, n_scenarios=3, mu=0.07, sigma=0.15, periods_per_year=12, seed=0)
                text, chart = self.capture(module.show_gbm_echart, **inputs)
                prices, _ = module.simulate_gbm_from_prices(**inputs)
                self.assertIn("seed=0", text)
                self.assertEqual(chart["dates"], [str(i) for i in range(13)])
                self.assertEqual(chart["gbmPrices"]["xAxis"]["name"], "Months")
                for column, points in enumerate(chart["gbmPrices"]["series"].values()):
                    np.testing.assert_allclose(points, prices.iloc[:, column])
                    self.assertEqual(points[0], 100)
                _, repeated = self.capture(module.show_gbm_echart, **inputs)
                self.assertEqual(repeated, chart)

    def test_stdout_fallback_keeps_summary_and_json_in_one_payload(self):
        for path, module in self.modules.items():
            output = io.StringIO()
            with self.subTest(module=path), patch.object(__main__, "_emit_echarts", None, create=True), contextlib.redirect_stdout(output):
                module.show_cppi_echart(n_years=1, n_scenarios=1, sigma=0, floor=0.8)
            text, payload = output.getvalue().split("<ECHARTS_DATA>")
            self.assertIn("Observed-path breaches: 0/1", text)
            self.assertIn("n/a (no terminal breaches)", text)
            chart = json.loads(payload)
            self.assertIsNone(chart["summary"]["conditional_terminal_shortfall"])
            self.assertGreater(chart["summary"]["terminal_breach_wilson_95"][1], 0.7)

    def test_observed_path_breach_can_recover_before_terminal_date(self):
        # A breaches early and recovers through 10% cash interest; B breaches last.
        returns = pd.DataFrame({"A": [-0.90, 0, 0, 0, 0], "B": [0, 0, 0, 0, -0.90], "C": [0] * 5},
                               index=pd.RangeIndex(1, 6))
        prices = pd.concat([pd.DataFrame([[100] * 3], columns=returns.columns), 100 * (1 + returns).cumprod()])
        logs = np.log1p(returns)
        for path, module in self.modules.items():
            with self.subTest(module=path), patch.object(module, "simulate_gbm_from_prices", return_value=(prices, logs)):
                text, payload = self.capture(module.show_cppi_echart, n_years=5, n_scenarios=3,
                                             periods_per_year=1, floor=0.9, m=4, risk_free_rate=0.10)
            summary = payload["summary"]
            self.assertEqual(summary["path_breach_count"], 2)
            self.assertEqual(summary["terminal_breach_count"], 1)
            self.assertAlmostEqual(summary["observed_path_breach_probability"], 2 / 3)
            self.assertAlmostEqual(summary["terminal_breach_probability"], 1 / 3)
            # B's pre-loss wealth is 115.198; risky investment 100.792, cash 14.406.
            terminal_b = 100.792 * 0.10 + 14.406 * 1.10
            self.assertAlmostEqual(summary["conditional_terminal_shortfall"], 90 - terminal_b)
            self.assertAlmostEqual(summary["mean_terminal_shortfall"], (90 - terminal_b) / 3)
            self.assertIn("Observed-path breaches: 2/3", text)
            self.assertIn("Terminal breaches: 1/3", text)
            self.assertEqual(payload["dates"], [str(i) for i in range(6)])

    def test_cppiquantiles_and_allocations_match_the_underlying_paths(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                inputs = dict(n_years=1, n_scenarios=5, mu=0.07, sigma=0.30, periods_per_year=12, start=100, seed=42)
                _, payload = self.capture(module.show_cppi_echart, **inputs, floor=0.8, m=3)
                prices, logs = module.simulate_gbm_from_prices(**inputs)
                result = module.cppi(np.expm1(logs), start_value=100, floor=0.8, m=3)
                wealth = np.vstack([np.full(5, 100), result["CPPI wealth"].to_numpy()])
                series = payload["cppiWealth"]["series"]
                for name, percentile in (("CPPI P05", 5), ("CPPI Median", 50), ("CPPI P95", 95)):
                    np.testing.assert_allclose(series[name], np.percentile(wealth, percentile, axis=1))
                    self.assertEqual(series[name][0], 100)
                np.testing.assert_allclose(series["Risky Median"], np.median(prices, axis=1))
                allocation = payload["riskyAllocation"]["series"]["Risky Weight Mean"]
                self.assertIsNone(allocation[0])
                self.assertAlmostEqual(allocation[1], 60)
                np.testing.assert_allclose(allocation[1:], result["Risky allocation"].mean(axis=1) * 100)
                self.assertEqual(payload["riskyAllocation"]["yAxis"]["max"], 100)
                for name, chart in payload.items():
                    if name in ("dates", "summary"):
                        continue
                    for points in chart["series"].values():
                        self.assertEqual(len(points), len(payload["dates"]))

    def test_wilson_interval_handles_zero_all_and_partial_failures(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                np.testing.assert_allclose(module._binomial_interval(0, 300), [0, 0.012642971224546], atol=1e-12)
                np.testing.assert_allclose(module._binomial_interval(300, 300), [0.987357028775454, 1], atol=1e-12)
                lower, upper = module._binomial_interval(50, 100)
                self.assertAlmostEqual(lower + upper, 1)
                self.assertLess(lower, 0.5)
                self.assertGreater(upper, 0.5)

    def test_policy_changes_keep_risky_paths_and_zoom_only_changes_axis(self):
        module = self.modules["PortfolioOptimizationKit.py"]
        inputs = dict(n_years=1, n_scenarios=20, floor=0.8, sigma=0.50, seed=42)
        _, baseline = self.capture(module.show_cppi_echart, **inputs, m=3)
        _, different_policy = self.capture(module.show_cppi_echart, **inputs, m=6)
        _, zoomed = self.capture(module.show_cppi_echart, **inputs, m=3, ymax=150)
        self.assertEqual(baseline["cppiWealth"]["series"]["Risky Median"], different_policy["cppiWealth"]["series"]["Risky Median"])
        self.assertEqual(baseline["summary"], zoomed["summary"])
        self.assertEqual(baseline["cppiWealth"]["series"], zoomed["cppiWealth"]["series"])
        self.assertAlmostEqual(zoomed["cppiWealth"]["yAxis"]["max"], 1.5 * baseline["cppiWealth"]["yAxis"]["max"])


if __name__ == "__main__":
    unittest.main()
