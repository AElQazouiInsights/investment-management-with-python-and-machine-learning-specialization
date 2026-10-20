"""Independent financial identities and timing checks for factor/style helpers."""

import ast
import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from test_return_annualization import MODULE_PATHS, ROOT


class FactorCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules = {}
        for i, path in enumerate(MODULE_PATHS):
            spec = importlib.util.spec_from_file_location(f"factor_copy_{i}", ROOT / path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cls.modules[path] = module

    def test_reviewed_helpers_are_identical_across_published_sources(self):
        names = {"get_brka_rets", "get_fff_returns", "_factor_inputs", "linear_regression",
                 "tracking_error", "style_analysis", "_capitalization_weights", "weight_ew",
                 "weight_cw", "backtest_weight_scheme"}
        reference = None
        for path in MODULE_PATHS:
            definitions = {node.name: ast.dump(node) for node in ast.parse((ROOT / path).read_text()).body
                           if isinstance(node, ast.FunctionDef) and node.name in names}
            self.assertEqual(set(definitions), names)
            if reference is None:
                reference = definitions
            with self.subTest(copy=path):
                self.assertEqual(definitions, reference)

    def test_monthly_aggregation_compounds_decimal_returns_without_an_extra_period(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "brka_d_ret.csv").write_text(
                "DATE,BRKA\n2024-01-02,0.10\n2024-01-03,-0.10\n2024-02-01,0.05\n")
            for path, pok in self.modules.items():
                for suffix in ("", "/"):
                    with self.subTest(copy=path, suffix=suffix), patch.object(pok, "path_to_data_folder", return_value=folder + suffix):
                        monthly = pok.get_brka_rets(monthly=True)
                        np.testing.assert_allclose(monthly["BRKA"], [-0.01, 0.05])
                        self.assertEqual(monthly.index.astype(str).tolist(), ["2024-01", "2024-02"])

    def test_berkshire_loader_rejects_missing_observations_dates_and_empty_months(self):
        fixtures = [
            "2024-01-02,0.1\n2024-03-01,0.1\n",
            "2024-01-02,0.1\n2024-01-02,0.2\n",
            "2024-01-02,0.1\n2024-01-03,\n",
            "2024-01-02,-1.1\n",
        ]
        with tempfile.TemporaryDirectory() as folder:
            for fixture in fixtures:
                (Path(folder) / "brka_d_ret.csv").write_text("DATE,BRKA\n" + fixture)
                for path, pok in self.modules.items():
                    with self.subTest(copy=path, fixture=fixture), patch.object(pok, "path_to_data_folder", return_value=folder):
                        with self.assertRaises(ValueError):
                            pok.get_brka_rets(monthly=True)

    def test_factor_loader_preserves_months_and_converts_percent_and_missing_sentinels(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "F-F_Research_Data_Factors_m.csv").write_text(
                ",Mkt-RF,SMB,HML,RF\n202401,2,-1,-99.99,0.2\n202402,3,-999,1,0.3\n")
            for path, pok in self.modules.items():
                with self.subTest(copy=path), patch.object(pok, "path_to_data_folder", return_value=folder):
                    frame = pok.get_fff_returns()
                    np.testing.assert_allclose(frame.iloc[0], [0.02, -0.01, np.nan, 0.002])
                    self.assertTrue(np.isnan(frame.iloc[1]["SMB"]))
                    self.assertEqual(frame.index.astype(str).tolist(), ["2024-01", "2024-02"])

    def test_native_and_browser_datasets_are_the_same_snapshot(self):
        for filename in ("brka_d_ret.csv", "F-F_Research_Data_Factors_m.csv", "ind49_m_vw_rets.csv",
                         "ind49_m_nfirms.csv", "ind49_m_size.csv"):
            expected = (ROOT / "data" / filename).read_bytes()
            for directory in ("assets/data", "public/assets/data", "docs/public/assets/data"):
                with self.subTest(directory=directory, filename=filename):
                    self.assertEqual((ROOT / directory / filename).read_bytes(), expected)

    def test_ols_recovers_known_exposure_and_intercept_without_mutating_inputs(self):
        x = pd.DataFrame({"Market": [-0.03, -0.01, 0.01, 0.03]})
        y = 0.001 + 1.2 * x["Market"] + np.array([0.002, -0.002, -0.002, 0.002])
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                fit = pok.linear_regression(y, x)
                np.testing.assert_allclose(fit.params, [1.2, 0.001], atol=1e-12)
                self.assertAlmostEqual(fit.resid.sum(), 0.0)
                self.assertAlmostEqual(x["Market"] @ fit.resid, 0.0)
                # SSE=4*(.002)^2, df=2: intercept SE=sqrt(.000008/4).
                self.assertAlmostEqual(fit.bse["Alpha"], np.sqrt(0.000002))
                self.assertEqual(x.columns.tolist(), ["Market"])
                np.testing.assert_allclose(pok.linear_regression(y.to_numpy(), x.to_numpy()).params, fit.params)

    def test_regression_and_style_reject_misalignment_missing_and_ambiguous_response(self):
        x = pd.DataFrame({"A": [0.01, -0.02, 0.03, 0.04], "B": [0.02, 0.01, -0.01, 0.02]})
        y = x["A"] * 0.5 + x["B"] * 0.5
        cases = [(y.iloc[::-1], x), (y, x.set_axis([1, 2, 3, 4])), (y.to_frame().assign(other=y), x),
                 (y.mask(y.index == 2), x), (y, x.assign(A=np.inf)), (y, x.set_axis(["A", "A"], axis=1))]
        for path, pok in self.modules.items():
            for target, design in cases:
                for function in (pok.linear_regression, pok.style_analysis):
                    with self.subTest(copy=path, helper=function.__name__), self.assertRaises(ValueError):
                        function(target, design)

    def test_ols_rejects_unidentified_or_saturated_design_and_duplicate_intercept(self):
        x = pd.DataFrame({"Market": [-0.03, -0.01, 0.01, 0.03]})
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                for design in (x.assign(duplicate=x["Market"]), x.assign(Alpha=1), x.assign(constant=1)):
                    with self.assertRaises(ValueError):
                        pok.linear_regression(x["Market"], design)
                with self.assertRaises(ValueError):
                    pok.linear_regression(x["Market"].iloc[:2], x.iloc[:2])
                self.assertAlmostEqual(pok.linear_regression(x["Market"], x, alpha=False).params.iloc[0], 1)

    def test_style_matches_closed_form_two_asset_projection_and_boundary(self):
        x = pd.DataFrame({"A": [0.03, -0.02, 0.01, 0.04], "B": [-0.01, 0.01, 0.02, 0.00]})
        for path, pok in self.modules.items():
            for exposure in (0.3, -0.4, 1.4):
                y = exposure * x["A"] + (1 - exposure) * x["B"] + 0.001
                difference = x["A"] - x["B"]
                w = np.clip(difference @ (y - x["B"]) / (difference @ difference), 0, 1)
                with self.subTest(copy=path, exposure=exposure):
                    np.testing.assert_allclose(pok.style_analysis(y, x), [w, 1 - w], atol=1e-7)
                    np.testing.assert_allclose(pok.style_analysis(y.to_frame(), x), [w, 1 - w], atol=1e-7)

    def test_style_fit_is_scale_invariant_and_allows_nonunique_identical_benchmarks(self):
        x = pd.DataFrame({"A": [0.03, -0.02, 0.01, 0.04], "B": [-0.01, 0.01, 0.02, 0.00]})
        y = x @ np.array([0.3, 0.7])
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                for scale in (1e-3, 1, 100):
                    np.testing.assert_allclose(pok.style_analysis(y * scale, x * scale), [0.3, 0.7], atol=1e-7)
                duplicated = pd.DataFrame({"A": y, "B": y})
                weights = pok.style_analysis(y, duplicated)
                np.testing.assert_allclose(duplicated @ weights, y)
                self.assertAlmostEqual(weights.sum(), 1)

    def test_style_does_not_return_failed_or_invalid_solver_allocations(self):
        x = pd.DataFrame({"A": [0.01, 0.02, -0.03], "B": [0.02, -0.01, 0.03]})
        outcomes = [SimpleNamespace(success=False, message="forced failure"),
                    SimpleNamespace(success=True, x=np.array([0.7, 0.7]), fun=0.1),
                    SimpleNamespace(success=True, x=np.array([np.nan, 1.0]), fun=0.1)]
        for path, pok in self.modules.items():
            for outcome in outcomes:
                with self.subTest(copy=path), patch.object(pok, "minimize", return_value=outcome):
                    with self.assertRaises(RuntimeError):
                        pok.style_analysis(x["A"], x)

    def test_legacy_fit_distance_includes_bias_and_rejects_silent_pandas_alignment(self):
        x = pd.Series([0.01] * 4)
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                self.assertAlmostEqual(pok.tracking_error(x, x * 0), 0.02)
                self.assertAlmostEqual(x.std(ddof=1), 0)
                for y in (x.iloc[::-1], x.mask(x.index == 1)):
                    with self.assertRaises(ValueError):
                        pok.tracking_error(x, y)

    def test_capped_equal_weights_respect_budget_caps_and_exclusions(self):
        r = pd.DataFrame([[0, 0, 0]], columns=["A", "B", "C"])
        cap = pd.DataFrame([[0.05, 0.15, 0.8]], columns=r.columns)
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                weights = pok.weight_ew(r, cap_ws=cap, max_cw_mult=2)
                np.testing.assert_allclose(weights, [0.1, 0.3, 0.6], atol=1e-12)
                self.assertTrue((weights <= 2 * cap.iloc[0] + 1e-12).all())
                np.testing.assert_allclose(pok.weight_ew(r, cap_ws=cap, max_cw_mult=2, microcap_thr=0.1), [0, 0.3, 0.7])
                np.testing.assert_allclose(pok.weight_ew(r, cap_ws=cap, max_cw_mult=1), cap.iloc[0])
                with self.assertRaisesRegex(ValueError, "infeasible"):
                    pok.weight_ew(r, cap_ws=cap, max_cw_mult=1, microcap_thr=0.1)
                with self.assertRaisesRegex(ValueError, "No assets"):
                    pok.weight_ew(r, cap_ws=cap, microcap_thr=0.9)

    def test_cap_weights_use_last_training_date_and_next_return_not_stale_or_future_weights(self):
        r = pd.DataFrame({"A": [0.0, 0.0, 0.1, -0.1], "B": [0.0, 0.0, 0.0, 0.2]},
                         index=pd.period_range("2024-01", periods=4, freq="M"))
        cap = pd.DataFrame([[0.9, 0.1], [0.2, 0.8], [0.7, 0.3], [0.4, 0.6]], index=r.index, columns=r.columns)
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                result = pok.backtest_weight_scheme(r, window=2, weight_scheme=pok.weight_cw, cap_ws=cap)
                np.testing.assert_allclose(result, [np.nan, np.nan, 0.02, -0.01], atol=1e-12)
                changed_future = cap.copy()
                changed_future.iloc[-1] = [1, 0]
                pd.testing.assert_series_equal(result, pok.backtest_weight_scheme(r, window=2, weight_scheme=pok.weight_cw, cap_ws=changed_future))
                pd.testing.assert_series_equal(pok.weight_cw(r.iloc[:2], cap[["B", "A"]]), cap.iloc[1])

    def test_backtest_rejects_incomplete_data_and_invalid_weight_schemes(self):
        r = pd.DataFrame({"A": [0.01, 0.02, 0.03], "B": [0.02, -0.01, 0.0]})
        for path, pok in self.modules.items():
            with self.subTest(copy=path):
                with self.assertRaises(ValueError):
                    pok.backtest_weight_scheme(r.mask(r == 0.02), window=1)
                for window in (0, 3, 1.5, True):
                    with self.assertRaises(ValueError):
                        pok.backtest_weight_scheme(r, window=window)
                for w in (pd.Series([0.5, 0.5], index=["A", "wrong"]), pd.Series([0.7, 0.7], index=r.columns)):
                    with self.assertRaises(ValueError):
                        pok.backtest_weight_scheme(r, window=1, weight_scheme=lambda _: w)


if __name__ == "__main__":
    unittest.main()
