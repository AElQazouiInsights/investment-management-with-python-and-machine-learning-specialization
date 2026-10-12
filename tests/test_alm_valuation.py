"""Cash-flow timing, rate scenarios, label alignment, and funding-ratio checks."""

import importlib.util
import unittest

import numpy as np
import pandas as pd

from test_return_annualization import MODULE_PATHS, ROOT


class AlmValuationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules = {}
        for i, path in enumerate(MODULE_PATHS):
            spec = importlib.util.spec_from_file_location(f"alm_copy_{i}", ROOT / path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cls.modules[path] = module

    def schedules(self):
        return pd.DataFrame({"Plan A": [8000, 11000, 6000], "Plan B": [11000, 2000, 15000]},
                            index=pd.Index([1, 2, 3], name="Payment year"))

    def test_discount_factors_handle_zero_fractional_times_and_negative_rates(self):
        rates = pd.Series({"Zero": 0.0, "Positive": 0.21, "Negative": -0.19})
        for path, module in self.modules.items():
            with self.subTest(module=path):
                factors = module.discount([0, 0.5, 1, 2], rates)
                self.assertEqual(factors.columns.tolist(), rates.index.tolist())
                np.testing.assert_allclose(factors.loc[0], 1.0)
                np.testing.assert_allclose(factors["Zero"], 1.0)
                self.assertAlmostEqual(factors.loc[0.5, "Positive"], 1 / 1.1)
                self.assertAlmostEqual(factors.loc[0.5, "Negative"], 1 / 0.9)
                self.assertAlmostEqual(module.discount(3, 0.03).iloc[0, 0], 0.9151416593531595)

    def test_scalar_rate_values_every_named_stream_without_pandas_misalignment(self):
        flows = self.schedules()
        expected = [8000 / 1.05 + 11000 / 1.05 ** 2 + 6000 / 1.05 ** 3,
                    11000 / 1.05 + 2000 / 1.05 ** 2 + 15000 / 1.05 ** 3]
        for path, module in self.modules.items():
            with self.subTest(module=path):
                value = module.present_value(flows, 0.05)
                self.assertEqual(value.index.tolist(), ["Plan A", "Plan B"])
                np.testing.assert_allclose(value, expected)
                np.testing.assert_allclose(module.present_value(flows, 0), [25000, 28000])

    def test_multiple_rates_pair_by_label_or_explicit_position(self):
        flows = self.schedules()
        expected = [8000 / 1.05 + 11000 / 1.05 ** 2 + 6000 / 1.05 ** 3,
                    11000 / 1.03 + 2000 / 1.03 ** 2 + 15000 / 1.03 ** 3]
        for path, module in self.modules.items():
            with self.subTest(module=path):
                rates = pd.Series({"Plan B": 0.03, "Plan A": 0.05})
                np.testing.assert_allclose(module.present_value(flows, rates), expected)
                np.testing.assert_allclose(module.present_value(flows, [0.05, 0.03]), expected)
                numeric_columns = flows.set_axis([0, 1], axis=1)
                np.testing.assert_allclose(module.present_value(numeric_columns, [0.05, 0.03]), expected)
                with self.assertRaisesRegex(ValueError, "Rate labels"):
                    module.present_value(flows, pd.Series({"Wrong": 0.03, "Plan A": 0.05}))
                with self.assertRaisesRegex(ValueError, "one rate per"):
                    module.present_value(flows, [0.01, 0.02, 0.03])

    def test_one_stream_can_be_valued_in_several_flat_rate_scenarios(self):
        flows = self.schedules()[["Plan A"]]
        rates = pd.Series({"No discount": 0, "Five percent": 0.05, "Two percent": 0.02})
        for path, module in self.modules.items():
            with self.subTest(module=path):
                values = module.present_value(flows, rates)
                self.assertEqual(values.index.tolist(), rates.index.tolist())
                np.testing.assert_allclose(values, [25000,
                    8000 / 1.05 + 11000 / 1.05 ** 2 + 6000 / 1.05 ** 3,
                    8000 / 1.02 + 11000 / 1.02 ** 2 + 6000 / 1.02 ** 3])
                ratios = module.funding_ratio(24000, flows, rates)
                np.testing.assert_allclose(ratios, 24000 / values)

    def test_payment_timing_and_current_cash_are_valued_explicitly(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                current_and_future = pd.DataFrame({"Due": [100.0, 110.25]}, index=[0, 2])
                self.assertAlmostEqual(module.present_value(current_and_future, 0.05).iloc[0], 200)
                same_date = pd.DataFrame({"Due": [100.0, 200.0]}, index=[1, 1])
                self.assertAlmostEqual(module.present_value(same_date, 0.05).iloc[0], 300 / 1.05)
                scheduled = module.present_value(self.schedules()[["Plan A"]], 0.05).iloc[0]
                delayed = module.present_value(pd.DataFrame({"Due": [25000]}, index=[3]), 0.05).iloc[0]
                self.assertGreater(scheduled, delayed)

    def test_funding_assets_align_by_label_and_broadcast_only_when_unambiguous(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                flows = self.schedules()
                values = module.present_value(flows, 0.05)
                assets = pd.Series({"Plan B": 27000, "Plan A": 20000})
                ratios = module.funding_ratio(assets, flows, 0.05)
                self.assertEqual(ratios.index.tolist(), flows.columns.tolist())
                np.testing.assert_allclose(ratios, np.array([20000, 27000]) / values)
                asset_cases = pd.Series({"No assets": 0, "Fully funded": values["Plan A"], "Surplus": 2 * values["Plan A"]})
                np.testing.assert_allclose(module.funding_ratio(asset_cases, flows[["Plan A"]], 0.05), [0, 1, 2])
                with self.assertRaisesRegex(ValueError, "Asset labels"):
                    module.funding_ratio(pd.Series({"A": 20000, "B": 27000}), flows, 0.05)

    def test_invalid_or_missing_inputs_do_not_become_zero_present_values(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                for rates in (-1, -1.1, np.nan, [0.03, np.inf]):
                    with self.assertRaises(ValueError):
                        module.discount([1, 2], rates)
                for times in ([], [-1], [np.nan], pd.date_range("2026-01-01", periods=2)):
                    with self.assertRaises(ValueError):
                        module.discount(times, 0.03)
                missing = self.schedules().astype(float)
                missing.iloc[0, 0] = np.nan
                with self.assertRaisesRegex(ValueError, "Cash flows must be complete"):
                    module.present_value(missing, 0.05)
                with self.assertRaisesRegex(ValueError, "positive, finite liability"):
                    module.funding_ratio(100, pd.DataFrame({"Due": [0]}, index=[1]), 0.05)
                with self.assertRaisesRegex(ValueError, "nonnegative"):
                    module.funding_ratio(-1, self.schedules(), 0.05)

    def test_coupon_bond_valuation_still_uses_coupon_period_rates(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                self.assertAlmostEqual(module.bond_price(principal=100, maturity=3, coupon_rate=0.04,
                                                       coupons_per_year=2, ytm=0.04), 100)
                expected = sum(2 / 1.03 ** period for period in range(1, 7)) + 100 / 1.03 ** 6
                self.assertAlmostEqual(module.bond_price(principal=100, maturity=3, coupon_rate=0.04,
                                                       coupons_per_year=2, ytm=0.06), expected)

    def test_rate_quotes_match_semiannual_monthly_and_continuous_hand_values(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                self.assertAlmostEqual(module.compounding_rate(0.10, 1), 0.10)
                self.assertAlmostEqual(module.compounding_rate(0.10, 2), 0.1025)
                self.assertAlmostEqual(module.compounding_rate(0.10, 12), 0.10471306744129724)
                self.assertAlmostEqual(module.compounding_rate(0.10), 0.10517091807564763)
                self.assertAlmostEqual(module.compounding_rate_inv(0.10, 12), 0.0956896851468449)
                self.assertAlmostEqual(module.compounding_rate_inv(0.10), 0.09531017980432487)

    def test_rate_round_trips_preserve_dataframe_series_and_array_structure(self):
        effective = pd.DataFrame({"Base": [-0.10, 0, 0.03], "Alternative": [0.04, 0.10, 0.25]},
                                 index=["A", "B", "C"])
        for path, module in self.modules.items():
            for frequency in (None, 1, 2, 12, 365):
                with self.subTest(module=path, frequency=frequency):
                    quotes = module.compounding_rate_inv(effective, frequency)
                    restored = module.compounding_rate(quotes, frequency)
                    pd.testing.assert_frame_equal(restored, effective.astype(float), atol=1e-14, rtol=1e-13)
                    series = effective["Base"]
                    result = module.compounding_rate(module.compounding_rate_inv(series, frequency), frequency)
                    pd.testing.assert_series_equal(result, series, atol=1e-14, rtol=1e-13)
                    array = effective.to_numpy()
                    result = module.compounding_rate(module.compounding_rate_inv(array, frequency), frequency)
                    self.assertEqual(result.shape, array.shape)
                    np.testing.assert_allclose(result, array, atol=1e-14)

    def test_small_rate_conversions_do_not_round_nonzero_quotes_to_zero(self):
        tiny = np.array([1e-16, -1e-16])
        for path, module in self.modules.items():
            for frequency in (None, 12, 365):
                with self.subTest(module=path, frequency=frequency):
                    effective = module.compounding_rate(tiny, frequency)
                    quoted = module.compounding_rate_inv(tiny, frequency)
                    np.testing.assert_allclose(effective, tiny, rtol=1e-14, atol=0)
                    np.testing.assert_allclose(quoted, tiny, rtol=1e-14, atol=0)

    def test_equivalent_quotes_produce_identical_discount_factors(self):
        times = np.array([0.0, 0.5, 1.0, 3.0, 10.0])
        for path, module in self.modules.items():
            for effective in (-0.01, 0, 0.03, 0.10):
                with self.subTest(module=path, effective=effective):
                    nominal = module.compounding_rate_inv(effective, 12)
                    continuous = module.compounding_rate_inv(effective)
                    expected = module.discount(times, effective).iloc[:, 0]
                    np.testing.assert_allclose((1 + nominal / 12) ** (-12 * times), expected, rtol=1e-13)
                    np.testing.assert_allclose(np.exp(-continuous * times), expected, rtol=1e-13)

    def test_rate_conversion_domains_are_explicit(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                for frequency in (0, -1, 1.5, True, np.nan, np.inf):
                    for function in (module.compounding_rate, module.compounding_rate_inv):
                        with self.assertRaisesRegex(ValueError, "positive integer"):
                            function(0.03, frequency)
                for value in (np.nan, np.inf, -np.inf):
                    for function in (module.compounding_rate, module.compounding_rate_inv):
                        with self.assertRaisesRegex(ValueError, "finite"):
                            function(value)
                with self.assertRaisesRegex(ValueError, "gross return"):
                    module.compounding_rate(-12, 12)
                with self.assertRaisesRegex(ValueError, "greater than -1"):
                    module.compounding_rate_inv(-1)
                # A nominal annual quote below -100% can still have valid monthly gross returns.
                self.assertTrue(-1 < module.compounding_rate(-2, 12) < 0)
                self.assertTrue(-1 < module.compounding_rate(-2) < 0)
                for value in (-1000, 1000):
                    with self.assertRaisesRegex(ValueError, "representable bounds"):
                        module.compounding_rate(value)


if __name__ == "__main__":
    unittest.main()
