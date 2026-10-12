"""Quote-specific derivatives, equivalent valuations, DV01, and finite-change errors."""

import __main__
import ast
import importlib.util
import json
import unittest
from unittest.mock import patch

import numpy as np

from test_return_annualization import MODULE_PATHS, ROOT


class BondSensitivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules = {}
        for i, path in enumerate(MODULE_PATHS):
            spec = importlib.util.spec_from_file_location(f"sensitivity_copy_{i}", ROOT / path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cls.modules[path] = module

    def test_continuous_worked_example_matches_discounted_cashflow_moments(self):
        times = np.arange(1, 7) / 2
        payments = np.array([5] * 5 + [105])
        pv = payments * np.exp(-0.12 * times)
        for path, module in self.modules.items():
            with self.subTest(module=path):
                measures = module.bond_sensitivity(coupon_rate=0.10, ytm=0.12, quote="continuous")
                self.assertAlmostEqual(measures["Price"], pv.sum())
                self.assertAlmostEqual(measures["Macaulay duration"], (times * pv).sum() / pv.sum())
                self.assertAlmostEqual(measures["Modified duration"], 2.653010037390808)
                self.assertAlmostEqual(measures["Convexity"], (times ** 2 * pv).sum() / pv.sum())
                self.assertAlmostEqual(measures["Dollar duration"], 249.94808918469275)
                self.assertAlmostEqual(measures["DV01"], 0.024994808918469277)

    def test_derivatives_agree_with_independent_finite_differences(self):
        for path, module in self.modules.items():
            for quote in ("nominal", "continuous"):
                for yield_quote in (-0.01, 0, 0.12):
                    with self.subTest(module=path, quote=quote, ytm=yield_quote):
                        times = np.arange(1, 7) / 2
                        payments = np.array([5] * 5 + [105])
                        def price(y):
                            factors = np.exp(-y * times) if quote == "continuous" else (1 + y / 2) ** (-2 * times)
                            return float(payments @ factors)
                        h = 1e-4
                        slope = (price(yield_quote + h) - price(yield_quote - h)) / (2 * h)
                        curvature = (price(yield_quote + h) - 2 * price(yield_quote) + price(yield_quote - h)) / h ** 2
                        measures = module.bond_sensitivity(coupon_rate=0.10, ytm=yield_quote, quote=quote)
                        self.assertAlmostEqual(-slope / price(yield_quote), measures["Modified duration"], places=6)
                        self.assertAlmostEqual(curvature / price(yield_quote), measures["Convexity"], delta=3e-6)

    def test_equivalent_quotes_preserve_price_and_macaulay_but_transform_derivatives(self):
        for path, module in self.modules.items():
            for frequency in (1, 2, 12):
                with self.subTest(module=path, frequency=frequency):
                    z = 0.12
                    y = frequency * np.expm1(z / frequency)
                    continuous = module.bond_sensitivity(coupon_rate=0.10, coupons_per_year=frequency, ytm=z, quote="continuous")
                    nominal = module.bond_sensitivity(coupon_rate=0.10, coupons_per_year=frequency, ytm=y)
                    self.assertAlmostEqual(continuous["Price"], nominal["Price"])
                    self.assertAlmostEqual(nominal["Price"], module.bond_price(maturity=3, coupon_rate=0.10, coupons_per_year=frequency, ytm=y))
                    self.assertAlmostEqual(continuous["Macaulay duration"], nominal["Macaulay duration"])
                    self.assertAlmostEqual(nominal["Modified duration"], continuous["Macaulay duration"] * np.exp(-z / frequency))
                    self.assertAlmostEqual(nominal["Convexity"],
                                           (continuous["Convexity"] + continuous["Macaulay duration"] / frequency) * np.exp(-2 * z / frequency))

    def test_same_numeric_basis_point_shift_is_not_the_same_repricing_across_quotes(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                y = 2 * np.expm1(0.12 / 2)
                mapped = 2 * np.expm1(0.121 / 2)
                exact_cont = module.bond_sensitivity(coupon_rate=0.10, ytm=0.121, quote="continuous")["Price"]
                exact_nom = module.bond_sensitivity(coupon_rate=0.10, ytm=mapped)["Price"]
                wrong_shift = module.bond_sensitivity(coupon_rate=0.10, ytm=y + 0.001)["Price"]
                self.assertAlmostEqual(exact_cont, exact_nom)
                self.assertGreater(abs(wrong_shift - exact_cont), 0.01)

    def test_finite_shift_error_is_positive_and_grows_beyond_the_local_region(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                base = module.bond_sensitivity(coupon_rate=0.10, ytm=0.12, quote="continuous")
                for sign in (-1, 1):
                    errors = []
                    for shift in (0.0001, 0.001, 0.03):
                        exact = module.bond_sensitivity(coupon_rate=0.10, ytm=0.12 + sign * shift, quote="continuous")["Price"]
                        linear = base["Price"] - base["Dollar duration"] * sign * shift
                        errors.append(exact - linear)
                    self.assertTrue((np.array(errors) > 0).all())
                    self.assertTrue((np.diff(errors) > 0).all())

    def test_zero_coupon_and_face_value_scaling_identities(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                zero = module.bond_sensitivity(maturity=5, coupon_rate=0, ytm=0.12, quote="continuous")
                self.assertAlmostEqual(zero["Price"], 100 * np.exp(-0.6))
                self.assertEqual(zero["Macaulay duration"], 5)
                self.assertEqual(zero["Modified duration"], 5)
                self.assertEqual(zero["Convexity"], 25)
                base = module.bond_sensitivity(coupon_rate=0.10, ytm=0.12, quote="continuous")
                scaled = module.bond_sensitivity(principal=1000, coupon_rate=0.10, ytm=0.12, quote="continuous")
                for key in ("Price", "Dollar duration", "DV01"):
                    self.assertAlmostEqual(scaled[key], base[key] * 10)
                for key in ("Macaulay duration", "Modified duration", "Convexity"):
                    self.assertAlmostEqual(scaled[key], base[key])

    def test_quote_validation_keeps_continuous_and_nominal_domains_distinct(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                self.assertGreater(module.bond_sensitivity(ytm=-2, quote="continuous")["Price"], 0)
                for kwargs in ({"ytm": -2}, {"quote": "unknown"}, {"ytm": np.nan}, {"ytm": np.inf}):
                    with self.assertRaises(ValueError):
                        module.bond_sensitivity(**kwargs)

    def test_shared_chart_helper_labels_and_selected_points_follow_the_quote(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                messages = []
                with patch.object(__main__, "_emit_echarts", messages.append, create=True):
                    module.show_duration_echart(coupon_rate=0.10, ytm=0.12, shift_bps=10, quote="continuous")
                text, encoded = messages[0].split("<ECHARTS_DATA>")
                plots = json.loads(encoded)
                self.assertEqual(plots["durationSensitivity"]["xAxis"]["name"], "Continuous yield change (bp)")
                exact = (93.96342871603265 / 94.213020554763 - 1) * 100
                np.testing.assert_allclose(plots["durationSensitivity"]["series"]["Selected exact"], [[10, exact]])
                np.testing.assert_allclose(plots["durationSensitivity"]["series"]["Selected approximation"], [[10, -2.653010037390808 * 0.1]])
                self.assertIn("exact minus linear price: +0.000356", text)

    def test_sensitivity_functions_match_across_all_toolkit_copies(self):
        names = {"bond_sensitivity", "show_duration_echart"}
        definitions = []
        for path in MODULE_PATHS:
            definitions.append({node.name: ast.dump(node) for node in ast.parse((ROOT / path).read_text()).body
                                if isinstance(node, ast.FunctionDef) and node.name in names})
        self.assertEqual(set(definitions[0]), names)
        for candidate in definitions[1:]:
            self.assertEqual(candidate, definitions[0])


if __name__ == "__main__":
    unittest.main()
