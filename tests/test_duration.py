"""PV-weighted timing, label alignment, and nominal-yield sensitivity identities."""

import __main__
import ast
import importlib.util
import json
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from test_return_annualization import MODULE_PATHS, ROOT


class DurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules = {}
        for i, path in enumerate(MODULE_PATHS):
            spec = importlib.util.spec_from_file_location(f"duration_copy_{i}", ROOT / path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cls.modules[path] = module

    def test_hand_computed_duration_uses_price_not_face_value(self):
        periods = np.arange(1, 7)
        flows = pd.DataFrame({"Bond": [1.5] * 5 + [101.5]}, index=periods)
        discounted = flows["Bond"].to_numpy() / 1.025 ** periods
        expected = (periods * discounted).sum() / discounted.sum()
        for path, module in self.modules.items():
            with self.subTest(module=path):
                duration = module.mac_duration(flows, 0.025)
                self.assertIsInstance(duration, float)
                self.assertAlmostEqual(duration, expected)
                self.assertAlmostEqual(duration / 2, 2.887554933457737)
                self.assertNotAlmostEqual(duration, (periods * discounted).sum() / 100)

    def test_equivalent_dates_and_rates_preserve_duration_in_years(self):
        for path, module in self.modules.items():
            for frequency in (1, 2, 4, 12):
                with self.subTest(module=path, frequency=frequency):
                    flows = module.bond_cash_flows(100, 3, 0.03, frequency)
                    original = flows.copy()
                    years = flows.rename(columns={0: "Named stream"})
                    years.index = flows.index / frequency
                    effective = (1 + 0.05 / frequency) ** frequency - 1
                    self.assertAlmostEqual(module.mac_duration(flows, 0.05 / frequency) / frequency,
                                           module.mac_duration(years, effective))
                    pd.testing.assert_frame_equal(flows, original)

    def test_multiple_named_streams_and_rate_labels_follow_valuation_alignment(self):
        flows = pd.DataFrame({"Early": [100, 10, 0], "Late": [0, 10, 100]}, index=[1, 2, 3])
        rates = pd.Series({"Late": 0.06, "Early": 0.02})
        for path, module in self.modules.items():
            with self.subTest(module=path):
                actual = module.mac_duration(flows, rates)
                self.assertEqual(actual.index.tolist(), ["Early", "Late"])
                for name in flows:
                    pv = flows[name].to_numpy() / (1 + rates[name]) ** flows.index.to_numpy()
                    self.assertAlmostEqual(actual[name], (pv * flows.index.to_numpy()).sum() / pv.sum())
                np.testing.assert_allclose(module.mac_duration(flows, [0.02, 0.06]), actual)
                common = module.mac_duration(flows, 0.04)
                self.assertLess(common["Early"], common["Late"])

    def test_single_stream_with_multiple_rate_scenarios_and_zero_coupon_limit(self):
        rates = pd.Series({"Negative": -0.01, "Zero": 0, "Positive": 0.06})
        for path, module in self.modules.items():
            with self.subTest(module=path):
                zero = pd.DataFrame({"Payment": [100]}, index=[3.5])
                result = module.mac_duration(zero, rates)
                self.assertEqual(result.index.tolist(), rates.index.tolist())
                np.testing.assert_allclose(result, 3.5)
                coupons = pd.DataFrame({"Bond": [5, 5, 105]}, index=[1, 2, 3])
                durations = module.mac_duration(coupons, rates)
                self.assertTrue((np.diff(durations) < 0).all())
                self.assertTrue(((durations > 1) & (durations < 3)).all())

    def test_zero_rate_time_zero_and_scaling_properties(self):
        flows = pd.DataFrame({"Payments": [20, 30, 50]}, index=[0, 1, 4])
        for path, module in self.modules.items():
            with self.subTest(module=path):
                self.assertAlmostEqual(module.mac_duration(flows, 0), (0 * 20 + 1 * 30 + 4 * 50) / 100)
                self.assertAlmostEqual(module.mac_duration(flows * 1000, 0.05), module.mac_duration(flows, 0.05))
                self.assertEqual(module.mac_duration(pd.DataFrame({"Now": [100]}, index=[0]), 0.05), 0)

    def test_higher_interim_coupons_move_present_value_to_earlier_dates(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                durations = [module.mac_duration(module.bond_cash_flows(100, 3, coupon, 2), 0.025) / 2
                             for coupon in (0, 0.03, 0.10)]
                self.assertAlmostEqual(durations[0], 3)
                self.assertTrue((np.diff(durations) < 0).all())

    def test_modified_duration_is_the_price_derivative_for_nominal_annual_ytm(self):
        for path, module in self.modules.items():
            for frequency in (1, 2, 12):
                with self.subTest(module=path, frequency=frequency):
                    ytm, h = 0.05, 1e-6
                    flows = module.bond_cash_flows(100, 3, 0.03, frequency)
                    mac = module.mac_duration(flows, ytm / frequency) / frequency
                    price = module.bond_price(100, 3, 0.03, frequency, ytm)
                    slope = (module.bond_price(100, 3, 0.03, frequency, ytm + h)
                             - module.bond_price(100, 3, 0.03, frequency, ytm - h)) / (2 * h)
                    self.assertAlmostEqual(-slope / price, mac / (1 + ytm / frequency), places=7)

    def test_invalid_or_undefined_durations_are_rejected(self):
        valid = pd.DataFrame({"Bond": [5, 105]}, index=[1, 2])
        for path, module in self.modules.items():
            for flows, rate in ((valid * 0, 0.05), (valid * -1, 0.05), (valid * np.nan, 0.05),
                                (valid, -1), (valid, np.inf), (valid.set_axis([-1, 2]), 0.05),
                                (valid.set_axis(["one", "two"]), 0.05),
                                (pd.concat([valid, valid.rename(columns={"Bond": "Other"})], axis=1), pd.Series({"X": 0.03, "Y": 0.04}))):
                with self.subTest(module=path), self.assertRaises(ValueError):
                    module.mac_duration(flows, rate)

    def test_widget_weights_reconcile_duration_and_basis_point_units(self):
        for path, module in self.modules.items():
            messages = []
            with self.subTest(module=path), patch.object(__main__, "_emit_echarts", messages.append, create=True):
                module.show_duration_echart()
                text, encoded = messages[-1].split("<ECHARTS_DATA>")
                plots = json.loads(encoded)
                weights = np.asarray(plots["durationWeights"]["series"]["PV weight"])
                np.testing.assert_allclose(weights[:, 0], np.arange(1, 7) / 2)
                self.assertAlmostEqual(weights[:, 1].sum(), 100)
                self.assertAlmostEqual((weights[:, 0] * weights[:, 1] / 100).sum(), 2.887554933457737)
                series = plots["durationSensitivity"]["series"]
                np.testing.assert_allclose(series["Selected exact"], [[50, -1.3967688922610133]])
                np.testing.assert_allclose(series["Selected approximation"], [[50, -1.408563382174506]])
                exact, approximate = np.asarray(series["Exact"]), np.asarray(series["Duration approximation"])
                np.testing.assert_allclose(exact[:, 0], approximate[:, 0])
                zero = np.flatnonzero(exact[:, 0] == 0)[0]
                self.assertAlmostEqual(exact[zero, 1], 0)
                self.assertAlmostEqual(approximate[zero, 1], 0)
                self.assertIn("not a payback date", text)

    def test_finite_shift_error_grows_and_zero_coupon_duration_remains_maturity(self):
        module = self.modules["PortfolioOptimizationKit.py"]
        errors = []
        for shift in (1, 50, 200):
            messages = []
            with patch.object(__main__, "_emit_echarts", messages.append, create=True):
                module.show_duration_echart(maturity=10, coupon_rate=0, shift_bps=shift)
            text, encoded = messages[-1].split("<ECHARTS_DATA>")
            plots = json.loads(encoded)
            self.assertIn("Macaulay duration: 10.000000 years", text)
            series = plots["durationSensitivity"]["series"]
            errors.append(abs(series["Selected exact"][0][1] - series["Selected approximation"][0][1]))
            self.assertEqual(plots["durationSensitivity"]["xAxis"]["max"], max(100, shift))
        self.assertTrue((np.diff(errors) > 0).all())

    def test_duration_helpers_match_across_all_toolkit_copies(self):
        names = {"mac_duration", "show_duration_echart"}
        definitions = []
        for path in MODULE_PATHS:
            definitions.append({node.name: ast.dump(node) for node in ast.parse((ROOT / path).read_text()).body
                                if isinstance(node, ast.FunctionDef) and node.name in names})
        self.assertEqual(set(definitions[0]), names)
        for candidate in definitions[1:]:
            self.assertEqual(candidate, definitions[0])


if __name__ == "__main__":
    unittest.main()
