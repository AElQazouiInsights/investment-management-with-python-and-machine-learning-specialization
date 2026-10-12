"""Historical proxy timing, complete windows, cash benchmarks, and reset behavior."""

import __main__
import ast
import importlib.util
import json
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from test_return_annualization import MODULE_PATHS, ROOT


class HistoricalAlmTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules = {}
        for i, path in enumerate(MODULE_PATHS):
            spec = importlib.util.spec_from_file_location(f"historical_copy_{i}", ROOT / path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cls.modules[path] = module

    def inputs(self):
        dates = pd.period_range("2000-01", periods=4, freq="M")
        returns = pd.DataFrame({"A": [0, 0.5, 0.1, 0.1], "B": [0, -0.5, 0.2, 0.2]}, index=dates)
        sizes = pd.DataFrame({"A": [90, 10, 80, 50], "B": [10, 90, 20, 50]}, index=dates)
        return {"rets": returns, "size": sizes, "nfirms": sizes * 0 + 1}

    def test_proxy_uses_previous_month_capitalization_not_current_month(self):
        for path, module in self.modules.items():
            frames = self.inputs()
            with self.subTest(module=path), patch.object(module, "get_ind_file", side_effect=lambda filetype, nind: frames[filetype]):
                proxy = module.get_total_market_index_returns()
                np.testing.assert_allclose(proxy, [0.4, 0.19, 0.12])
                self.assertEqual(proxy.index.tolist(), frames["rets"].index[1:].tolist())
                frames["size"].loc["2000-03"] = [20, 80]
                changed = module.get_total_market_index_returns()
                self.assertAlmostEqual(changed.loc["2000-03"], proxy.loc["2000-03"])
                self.assertAlmostEqual(changed.loc["2000-04"], 0.18)

    def test_metadata_missing_returns_and_calendar_gaps_are_rejected(self):
        for path, module in self.modules.items():
            for fault in ("missing_size", "negative_count", "zero_total", "wrong_labels", "missing_return", "gap"):
                frames = self.inputs()
                if fault == "missing_size":
                    frames["size"] = frames["size"].astype(float)
                    frames["size"].iloc[1, 0] = np.nan
                elif fault == "negative_count":
                    frames["nfirms"].iloc[1, 0] = -1
                elif fault == "zero_total":
                    frames["size"].iloc[1] = 0
                elif fault == "wrong_labels":
                    frames["size"] = frames["size"].rename(columns={"A": "C"})
                elif fault == "missing_return":
                    frames["rets"].iloc[1, 0] = np.nan
                else:
                    frames = {name: frame.iloc[[0, 2, 3]] for name, frame in frames.items()}
                with self.subTest(module=path, fault=fault), patch.object(module, "get_ind_file", side_effect=lambda filetype, nind: frames[filetype]):
                    with self.assertRaises(ValueError):
                        module.get_total_market_index_returns()

    def test_real_snapshot_matches_manual_lagged_proxy_and_full_window(self):
        raw_returns = pd.read_csv(ROOT / "data/ind30_m_vw_rets.csv", index_col=0) / 100
        caps = pd.read_csv(ROOT / "data/ind30_m_nfirms.csv", index_col=0) * pd.read_csv(ROOT / "data/ind30_m_size.csv", index_col=0)
        expected = (caps.div(caps.sum(axis=1), axis=0).shift(1) * raw_returns).sum(axis=1, min_count=30).iloc[1:]
        for path, module in self.modules.items():
            with self.subTest(module=path), patch.object(module, "path_to_data_folder", return_value=str(ROOT / "data") + "/"):
                proxy = module.get_total_market_index_returns()
                np.testing.assert_allclose(proxy, expected, rtol=1e-13)
                self.assertEqual(len(proxy), 1109)
                self.assertEqual(str(proxy.index[0]), "1926-08")
                result = module.historical_drawdown()
                self.assertEqual(len(result["Returns"]), 348)
                self.assertEqual(str(result["Wealth"].index[0]), "1989-12")
                self.assertAlmostEqual(result["Market returns"].iloc[0, 0], -0.07241043202903033)
                np.testing.assert_allclose(result["Wealth"].iloc[0], 1)
                self.assertAlmostEqual(result["Wealth"].iloc[1]["Drawdown policy"], 1 + result["Market returns"].iloc[0, 0])

    def test_window_change_restarts_policy_instead_of_truncating_old_allocations(self):
        module = self.modules["PortfolioOptimizationKit.py"]
        with patch.object(module, "path_to_data_folder", return_value=str(ROOT / "data") + "/"):
            full = module.historical_drawdown()
            restarted = module.historical_drawdown(start_year=2009)
        self.assertEqual(str(restarted["Wealth"].index[0]), "2008-12")
        np.testing.assert_allclose(restarted["Wealth"].iloc[0], 1)
        self.assertAlmostEqual(restarted["Policy"]["Risky allocation"].iloc[0, 0], 1)
        self.assertLess(full["Policy"]["Risky allocation"].loc["2009-01"].iloc[0], 0.99)
        pd.testing.assert_frame_equal(restarted["Market returns"], full["Market returns"].loc["2009":])

    def test_cash_compounding_and_sharpe_use_the_same_assumption(self):
        module = self.modules["PortfolioOptimizationKit.py"]
        with patch.object(module, "path_to_data_folder", return_value=str(ROOT / "data") + "/"):
            result = module.historical_drawdown()
            zero_cash = module.historical_drawdown(cash_rate=0)
        self.assertAlmostEqual(result["Wealth"]["Assumed cash"].iloc[-1], 1.03 ** 29)
        stats = result["Statistics"]
        self.assertAlmostEqual(stats.loc["Assumed cash", "CAGR (%)"], 3)
        self.assertTrue(np.isnan(stats.loc["Assumed cash", "Sharpe vs assumed cash"]))
        excess = result["Returns"]["Market proxy"] - ((1.03) ** (1 / 12) - 1)
        self.assertAlmostEqual(stats.loc["Market proxy", "Sharpe vs assumed cash"], excess.mean() / excess.std(ddof=1) * np.sqrt(12))
        self.assertAlmostEqual(stats.loc["Market proxy", "Sharpe vs assumed cash"], stats.loc["Fixed 70/30", "Sharpe vs assumed cash"])
        pd.testing.assert_series_equal(result["Returns"]["Market proxy"], zero_cash["Returns"]["Market proxy"])
        np.testing.assert_allclose(zero_cash["Wealth"]["Assumed cash"], 1)

    def test_tight_requested_limit_can_fail_on_the_first_historical_month(self):
        module = self.modules["PortfolioOptimizationKit.py"]
        with patch.object(module, "path_to_data_folder", return_value=str(ROOT / "data") + "/"):
            result = module.historical_drawdown(maxdd=0.05)
        self.assertLess(result["Drawdown"].loc["1990-01", "Drawdown policy"], -0.05)
        self.assertGreater(result["Statistics"].loc["Drawdown policy", "Months beyond limit"], 0)

    def test_incomplete_and_invalid_windows_are_not_silently_clamped(self):
        for path, module in self.modules.items():
            with self.subTest(module=path), patch.object(module, "path_to_data_folder", return_value=str(ROOT / "data") + "/"):
                for kwargs in ({"start_year": 1926}, {"end_year": 2019}, {"start_year": 2019},
                               {"start_year": 2000, "end_year": 1990}, {"start_year": 1990.5}, {"cash_rate": -1}):
                    with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                        module.historical_drawdown(**kwargs)

    def test_published_chart_dates_units_and_initial_marker_match_results(self):
        module = self.modules["PortfolioOptimizationKit.py"]
        messages = []
        with patch.object(module, "path_to_data_folder", return_value=str(ROOT / "data") + "/"), patch.object(__main__, "_emit_echarts", messages.append, create=True):
            module.show_historical_drawdown_echart(start_year=2018)
            result = module.historical_drawdown(start_year=2018)
        text, encoded = messages[0].split("<ECHARTS_DATA>")
        plots = json.loads(encoded)
        self.assertEqual(plots["dates"][0], "2017-12")
        self.assertEqual(plots["dates"][-1], "2018-12")
        self.assertEqual(len(plots["dates"]), 13)
        self.assertEqual(plots["historicalWealth"]["yAxis"]["type"], "log")
        np.testing.assert_allclose(plots["historicalWealth"]["series"]["Drawdown policy"], result["Wealth"]["Drawdown policy"])
        np.testing.assert_allclose(plots["historicalDrawdowns"]["series"]["Drawdown policy"], result["Drawdown"]["Drawdown policy"] * 100)
        self.assertIn("Cash is hypothetical", text)

    def test_historical_helpers_match_across_all_toolkit_copies(self):
        names = {"get_ind_market_caps", "get_total_market_index_returns", "historical_drawdown", "show_historical_drawdown_echart"}
        definitions = []
        for path in MODULE_PATHS:
            definitions.append({node.name: ast.dump(node) for node in ast.parse((ROOT / path).read_text()).body
                                if isinstance(node, ast.FunctionDef) and node.name in names})
        self.assertEqual(set(definitions[0]), names)
        for candidate in definitions[1:]:
            self.assertEqual(candidate, definitions[0])


if __name__ == "__main__":
    unittest.main()
