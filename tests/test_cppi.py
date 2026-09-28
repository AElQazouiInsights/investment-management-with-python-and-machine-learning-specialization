"""Independent CPPI paths, accounting identities, and input-alignment checks."""

import importlib.util
import unittest

import numpy as np
import pandas as pd

from test_return_annualization import MODULE_PATHS, ROOT


class CppiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules = {}
        for i, path in enumerate(MODULE_PATHS):
            spec = importlib.util.spec_from_file_location(f"cppi_copy_{i}", ROOT / path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cls.modules[path] = module

    def test_worked_path_includes_first_return_and_rebalances_after_the_loss(self):
        risky = pd.Series([-0.20, 0.25], name="Risky", index=pd.period_range("2000-01", periods=2, freq="M"))
        for path, module in self.modules.items():
            with self.subTest(module=path):
                result = module.cppi(risky, start_value=1000, floor=0.9, m=4, risk_free_rate=0)
                np.testing.assert_allclose(result["CPPI wealth"]["Risky"], [920, 940])
                np.testing.assert_allclose(result["Risky wealth"]["Risky"], [800, 1000])
                np.testing.assert_allclose(result["CPPI returns"]["Risky"], [-0.08, 20 / 920])
                np.testing.assert_allclose(result["Risky allocation"]["Risky"], [0.4, 80 / 920])
                np.testing.assert_allclose(result["Cushions"]["Risky"], [0.1, 20 / 920])
                self.assertTrue(result["CPPI returns"].index.equals(risky.index))
                np.testing.assert_allclose(1000 * (1 + result["CPPI returns"]).cumprod(), result["CPPI wealth"])
                np.testing.assert_allclose(result["Floor value"], 900)
                self.assertFalse(result["Floor breaches"].to_numpy().any())

    def test_gap_losses_exhaust_or_breach_the_floor_and_cash_lock_misses_recovery(self):
        for path, module in self.modules.items():
            for loss, expected_wealth, breached in ((0.25, 900, False), (0.30, 880, True)):
                with self.subTest(module=path, loss=loss):
                    result = module.cppi(pd.Series([-loss, 0.50]), floor=0.9, m=4, risk_free_rate=0)
                    np.testing.assert_allclose(result["CPPI wealth"].iloc[:, 0], [expected_wealth] * 2)
                    self.assertAlmostEqual(result["Risky allocation"].iloc[1, 0], 0)
                    self.assertEqual(result["Floor breaches"].iloc[0, 0], breached)
                    self.assertEqual(result["Floor breaches"].iloc[1, 0], breached)
            with self.subTest(module=path, multiplier=6):
                result = module.cppi(pd.Series([-0.20]), floor=0.9, m=6, risk_free_rate=0)
                self.assertAlmostEqual(result["CPPI wealth"].iloc[0, 0], 880)
                self.assertTrue(result["Floor breaches"].iloc[0, 0])

    def test_fractional_multiplier_and_allocation_cap(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                fractional = module.cppi(pd.Series([0.10]), floor=0.8, m=2.5, risk_free_rate=0)
                self.assertAlmostEqual(fractional["Risky allocation"].iloc[0, 0], 0.5)
                self.assertAlmostEqual(fractional["CPPI wealth"].iloc[0, 0], 1050)
                capped = module.cppi(pd.Series([-0.20]), floor=0.8, m=6, risk_free_rate=0)
                self.assertAlmostEqual(capped["Risky allocation"].iloc[0, 0], 1.0)
                self.assertAlmostEqual(capped["CPPI wealth"].iloc[0, 0], 800)
                self.assertFalse(capped["Floor breaches"].iloc[0, 0])

    def test_default_cash_compounds_to_the_effective_annual_rate(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                result = module.cppi(pd.Series([0.10] * 12), m=0, risk_free_rate=0.03, periods_per_year=12)
                self.assertAlmostEqual(result["CPPI wealth"].iloc[-1, 0], 1030)
                self.assertAlmostEqual((1 + result["CPPI returns"].iloc[:, 0]).prod() - 1, 0.03)
                np.testing.assert_allclose(result["Safe returns"], 1.03 ** (1 / 12) - 1)

    def test_accounts_are_independent_and_safe_series_broadcasts_by_date(self):
        risky = pd.DataFrame({"A": [-0.20, 0.25], "B": [0.10, -0.10]})
        safe = pd.Series([0.001, 0.002], name="Cash")
        for path, module in self.modules.items():
            with self.subTest(module=path):
                together = module.cppi(risky, safe_rets=safe, floor=0.9, m=4)
                for column in risky:
                    alone = module.cppi(risky[column], safe_rets=safe, floor=0.9, m=4)
                    for key in ("Risky wealth", "CPPI wealth", "CPPI returns", "Risky allocation", "Floor value"):
                        pd.testing.assert_series_equal(together[key][column], alone[key][column])
                self.assertAlmostEqual(together["CPPI returns"].loc[0, "A"], 0.4 * -0.20 + 0.6 * 0.001)
                self.assertAlmostEqual(together["CPPI returns"].loc[0, "B"], 0.4 * 0.10 + 0.6 * 0.001)

    def test_decisions_do_not_use_current_or_future_risky_returns(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                first = module.cppi(pd.Series([0.10, -0.20, 0.50]), risk_free_rate=0)
                changed = module.cppi(pd.Series([0.10, 0.40, -0.50]), risk_free_rate=0)
                np.testing.assert_allclose(first["Risky allocation"].iloc[:2], changed["Risky allocation"].iloc[:2])
                self.assertNotAlmostEqual(first["Risky allocation"].iloc[2, 0], changed["Risky allocation"].iloc[2, 0])

    def test_fixed_floor_is_not_a_drawdown_cap(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                result = module.cppi(pd.Series([1.0, -0.40]), floor=0.8, m=3, risk_free_rate=0)
                np.testing.assert_allclose(result["CPPI wealth"].iloc[:, 0], [1600, 960])
                self.assertFalse(result["Floor breaches"].to_numpy().any())
                self.assertAlmostEqual(module.drawdown(result["CPPI returns"].iloc[:, 0])["Drawdown"].min(), -0.40)

    def test_total_depletion_does_not_create_spurious_later_returns(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                result = module.cppi(pd.Series([-1.0, 0.50]), floor=0, m=1)
                np.testing.assert_allclose(result["CPPI wealth"], 0)
                self.assertEqual(result["CPPI returns"].iloc[0, 0], -1)
                self.assertTrue(np.isnan(result["CPPI returns"].iloc[1, 0]))
                self.assertEqual(result["Risky allocation"].iloc[1, 0], 0)

    def test_dynamic_floor_uses_only_prior_peaks_and_preserves_legacy_multiplier(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                result = module.cppi(pd.Series([0.10, -0.30, 0.20]), drawdown=0.2, risk_free_rate=0)
                self.assertEqual(result["m"], 5)
                np.testing.assert_allclose(result["Peaks"].iloc[:, 0], [1000, 1100, 1100])
                np.testing.assert_allclose(result["Floor value"].iloc[:, 0], [800, 880, 880])
                np.testing.assert_allclose(result["CPPI wealth"].iloc[:, 0], [1100, 770, 770])
                self.assertEqual(result["Floor breaches"].iloc[:, 0].tolist(), [False, True, True])

    def test_invalid_returns_alignment_and_parameters_are_rejected(self):
        risky = pd.DataFrame({"A": [0.1, -0.1], "B": [0.0, 0.02]})
        for path, module in self.modules.items():
            with self.subTest(module=path):
                for safe in (risky.iloc[::-1], risky[["B", "A"]]):
                    with self.assertRaisesRegex(ValueError, "identical dates and column order"):
                        module.cppi(risky, safe_rets=safe)
                for value in (np.nan, np.inf, -1.01):
                    invalid = risky.copy()
                    invalid.iloc[0, 0] = value
                    with self.assertRaisesRegex(ValueError, "complete, finite, and at least -1"):
                        module.cppi(invalid)
                    with self.assertRaisesRegex(ValueError, "complete, finite, and at least -1"):
                        module.cppi(risky, safe_rets=invalid)
                for parameters in ({"start_value": 0}, {"floor": 1.1}, {"m": -1},
                                   {"periods_per_year": 0}, {"risk_free_rate": -1}, {"drawdown": 0}):
                    with self.assertRaises(ValueError):
                        module.cppi(risky, **parameters)

    def test_high_water_ratchet_matches_the_worked_path_for_independent_accounts(self):
        risky = pd.DataFrame({"A": [0.10, -0.10, 0.10], "B": [0.0, 0.20, -0.10]})
        for path, module in self.modules.items():
            with self.subTest(module=path):
                result = module.cppi(risky, drawdown=0.20, risk_free_rate=0)
                np.testing.assert_allclose(result["CPPI wealth"]["A"], [1100, 990, 1045])
                np.testing.assert_allclose(result["Risky allocation"]["A"], [1, 1, 5 / 9])
                np.testing.assert_allclose(result["Peaks"]["A"], [1000, 1100, 1100])
                np.testing.assert_allclose(result["Floor value"]["A"], [800, 880, 880])
                np.testing.assert_allclose(result["CPPI wealth"]["B"], [1000, 1200, 1080])
                np.testing.assert_allclose(result["Peaks"]["B"], [1000, 1000, 1200])
                np.testing.assert_allclose(result["Floor value"]["B"], [800, 800, 960])

    def test_reciprocal_policy_changes_both_floor_and_multiplier(self):
        for path, module in self.modules.items():
            for target in (0.20, 0.40, 0.60):
                with self.subTest(module=path, target=target):
                    # Valid fixed-floor/m arguments are superseded in drawdown mode.
                    result = module.cppi(pd.Series([-0.10, 0.0]), drawdown=target,
                                         floor=0.1, m=2, risk_free_rate=0)
                    self.assertEqual(result["m"], 1 / target)
                    np.testing.assert_allclose(result["Floor value"], (1 - target) * 1000)
                    self.assertAlmostEqual(result["Risky allocation"].iloc[0, 0], 1.0)
                    expected_weight = (target - 0.10) / (target * 0.90)
                    self.assertAlmostEqual(result["Risky allocation"].iloc[1, 0], expected_weight)

    def test_floor_breaches_agree_with_drawdown_from_ending_peaks(self):
        for path, module in self.modules.items():
            with self.subTest(module=path):
                result = module.cppi(pd.Series([0.10, -0.10, 0.10, -0.30]), drawdown=0.20, risk_free_rate=0)
                wealth = result["CPPI wealth"]
                ending_peaks = wealth.cummax().clip(lower=1000)
                drawdowns = 1 - wealth / ending_peaks
                np.testing.assert_allclose(drawdowns.iloc[:, 0], [0, 0.10, 0.05, 0.275], atol=1e-12)
                np.testing.assert_array_equal(result["Floor breaches"], drawdowns > 0.20)
                np.testing.assert_allclose(result["Floor value"].iloc[1:], 0.80 * ending_peaks.iloc[:-1])


if __name__ == "__main__":
    unittest.main()
