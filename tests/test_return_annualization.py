"""Independent numerical cases for the portfolio metrics used in the lesson."""

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
# These existing copies can be imported through different local/browser paths.
# Exercise each until publication is consolidated into one generated artifact.
MODULE_PATHS = (
    "PortfolioOptimizationKit.py",
    "assets/PortfolioOptimizationKit.py",
    "data/PortfolioOptimizationKit.py",
    "docs/public/PortfolioOptimizationKit.py",
    "docs/public/assets/data/PortfolioOptimizationKit.py",
    "public/PortfolioOptimizationKit.py",
)


class ReturnAnnualizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules = {}
        for i, path in enumerate(MODULE_PATHS):
            spec = importlib.util.spec_from_file_location(f"annualization_copy_{i}", ROOT / path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cls.modules[path] = module

    def test_price_conversion_does_not_add_an_investment_period(self):
        # Three annual prices represent two years of 10% growth, not three.
        prices = pd.Series([100.0, 110.0, 121.0])
        for path, pok in self.modules.items():
            with self.subTest(module=path):
                returns = pok.compute_returns(prices)
                self.assertAlmostEqual(pok.annualize_rets(returns, 1), 0.10)

    def test_compounding_preserves_a_loss_despite_zero_arithmetic_mean(self):
        # Two half-year returns: 100 -> 110 -> 99, a 1% annual loss.
        for path, pok in self.modules.items():
            with self.subTest(module=path):
                result = pok.annualize_rets(pd.Series([0.10, -0.10]), 2)
                self.assertAlmostEqual(result, -0.01)

    def test_dataframe_counts_observations_per_column(self):
        returns = pd.DataFrame({
            "two_years": [0.10, 0.10, np.nan],
            "one_year": [np.nan, 0.21, np.nan],
            "no_history": [np.nan, np.nan, np.nan],
        })
        for path, pok in self.modules.items():
            with self.subTest(module=path):
                result = pok.annualize_rets(returns, 1)
                self.assertAlmostEqual(result["two_years"], 0.10)
                self.assertAlmostEqual(result["one_year"], 0.21)
                self.assertTrue(np.isnan(result["no_history"]))

    def test_empty_history_has_no_growth_estimate(self):
        for path, pok in self.modules.items():
            for values in ([], [np.nan, np.nan]):
                with self.subTest(module=path, values=values):
                    result = pok.annualize_rets(pd.Series(values, dtype=float), 12)
                    self.assertTrue(np.isnan(result))

    def test_total_loss_is_minus_one_hundred_percent(self):
        for path, pok in self.modules.items():
            with self.subTest(module=path):
                result = pok.annualize_rets(pd.Series([0.10, -1.0]), 12)
                self.assertEqual(result, -1.0)

    def test_dataframe_honors_the_variance_denominator(self):
        returns = pd.DataFrame({
            "A": [0.02, -0.02, 0.02, -0.02],
            "B": [0.04, -0.04, 0.04, -0.04],
        })
        # For A: squared deviations sum to 0.0016. Divide by 3 or 4.
        for path, pok in self.modules.items():
            with self.subTest(module=path):
                np.testing.assert_allclose(
                    pok.annualize_vol(returns, 12, ddof=1), [0.08, 0.16]
                )
                np.testing.assert_allclose(
                    pok.annualize_vol(returns, 12, ddof=0),
                    [0.06928203230275509, 0.13856406460551018],
                )

    def test_volatility_frequency_is_independent_of_sample_length(self):
        for path, pok in self.modules.items():
            for frequency in (4, 12, 52, 252):
                for observations in (2, 60):
                    with self.subTest(module=path, frequency=frequency, n=observations):
                        returns = pd.Series([0.02, -0.02] * (observations // 2))
                        self.assertAlmostEqual(
                            pok.annualize_vol(returns, frequency, ddof=0),
                            0.02 * np.sqrt(frequency),
                        )

    def test_constant_losses_have_zero_volatility(self):
        for path, pok in self.modules.items():
            with self.subTest(module=path):
                self.assertAlmostEqual(
                    pok.annualize_vol(pd.Series([-0.01] * 12), 12), 0.0
                )

    def test_invalid_observation_frequencies_are_rejected(self):
        returns = pd.Series([0.01, -0.01])
        for path, pok in self.modules.items():
            for frequency in (0, -12, np.nan, np.inf):
                for function in (pok.annualize_rets, pok.annualize_vol):
                    with self.subTest(module=path, frequency=frequency, function=function.__name__):
                        with self.assertRaisesRegex(ValueError, "positive and finite"):
                            function(returns, frequency)

    def test_sharpe_uses_arithmetic_excess_return_not_compounded_growth(self):
        # The mean return is zero even though compounded wealth falls to 99.
        for path, pok in self.modules.items():
            with self.subTest(module=path):
                self.assertAlmostEqual(
                    pok.sharpe_ratio(pd.Series([0.10, -0.10]), 0.0, 12), 0.0
                )

    def test_sharpe_converts_effective_annual_benchmark_to_monthly(self):
        # Mean monthly excess = 1.75%; annualized sample volatility = 8%.
        returns = pd.Series([0.04, 0.0, 0.04, 0.0])
        annual_risk_free = 1.0025 ** 12 - 1
        for path, pok in self.modules.items():
            with self.subTest(module=path):
                self.assertAlmostEqual(
                    pok.sharpe_ratio(returns, annual_risk_free, 12), 2.625
                )

    def test_sharpe_dataframe_uses_each_columns_observed_sample(self):
        returns = pd.DataFrame({
            "A": [0.04, 0.0, 0.04, 0.0, np.nan],
            "B": [np.nan, 0.08, 0.0, 0.08, 0.0],
            "no_history": [np.nan] * 5,
            "constant": [0.01] * 5,
        })
        annual_risk_free = 1.0025 ** 12 - 1
        for path, pok in self.modules.items():
            with self.subTest(module=path):
                result = pok.sharpe_ratio(returns, annual_risk_free, 12)
                self.assertAlmostEqual(result["A"], 2.625)
                self.assertAlmostEqual(result["B"], 2.8125)
                self.assertTrue(np.isnan(result["no_history"]))
                self.assertTrue(np.isnan(result["constant"]))

    def test_undefined_sample_sharpe_returns_nan(self):
        for path, pok in self.modules.items():
            for values in ([], [np.nan], [0.01], [0.01] * 12, [0.0] * 12):
                with self.subTest(module=path, values=values):
                    self.assertTrue(np.isnan(
                        pok.sharpe_ratio(pd.Series(values, dtype=float), 0.03, 12)
                    ))

    def test_scalar_sharpe_preserves_annual_input_convention(self):
        for path, pok in self.modules.items():
            with self.subTest(module=path):
                self.assertAlmostEqual(pok.sharpe_ratio(0.12, 0.03, 12, v=0.15), 0.6)
                self.assertTrue(np.isnan(pok.sharpe_ratio(0.12, 0.03, 12, v=0.0)))

    def test_sharpe_validates_benchmark_and_frequency(self):
        returns = pd.Series([0.04, 0.0])
        for path, pok in self.modules.items():
            for annual_risk_free in (-1.0, -1.1, np.nan, np.inf):
                with self.subTest(module=path, risk_free=annual_risk_free):
                    with self.assertRaisesRegex(ValueError, "risk_free_rate"):
                        pok.sharpe_ratio(returns, annual_risk_free, 12)
            for frequency in (0, -12, np.nan, np.inf):
                with self.subTest(module=path, frequency=frequency):
                    with self.assertRaisesRegex(ValueError, "periods_per_year"):
                        pok.sharpe_ratio(returns, 0.03, frequency)

    def test_drawdown_measures_initial_loss_against_starting_capital(self):
        returns = pd.Series([-0.20, 0.0], index=pd.period_range("2024-01", periods=2, freq="M"))
        for path, pok in self.modules.items():
            with self.subTest(module=path):
                result = pok.drawdown(returns, start=100.0)
                self.assertTrue(result.index.equals(returns.index))
                np.testing.assert_allclose(result["Wealth"], [80.0, 80.0])
                np.testing.assert_allclose(result["Peaks"], [100.0, 100.0])
                np.testing.assert_allclose(result["Drawdown"], [-0.20, -0.20])
                self.assertAlmostEqual(pok.summary_stats(returns)["Max drawdown"].iloc[0], -0.20)

    def test_drawdown_recovers_and_tracks_a_new_peak(self):
        for path, pok in self.modules.items():
            with self.subTest(module=path):
                result = pok.drawdown(pd.Series([0.10, -0.20, 0.25, 0.10]), start=100.0)
                np.testing.assert_allclose(result["Wealth"], [110.0, 88.0, 110.0, 121.0])
                np.testing.assert_allclose(result["Peaks"], [110.0, 110.0, 110.0, 121.0])
                np.testing.assert_allclose(result["Drawdown"], [0.0, -0.20, 0.0, 0.0], atol=1e-14)

    def test_drawdown_is_scale_invariant_but_depends_on_return_order(self):
        returns = pd.Series([-0.20, 0.25, -0.10, 0.05])
        reordered = pd.Series([-0.20, -0.10, 0.05, 0.25])
        for path, pok in self.modules.items():
            with self.subTest(module=path):
                original = pok.drawdown(returns, start=100.0)
                scaled = pok.drawdown(returns, start=1000.0)
                reordered_result = pok.drawdown(reordered, start=100.0)
                np.testing.assert_allclose(scaled["Drawdown"], original["Drawdown"], atol=1e-14)
                np.testing.assert_allclose(scaled["Wealth"], original["Wealth"] * 10)
                self.assertAlmostEqual(original["Wealth"].iloc[-1], 94.5)
                self.assertAlmostEqual(reordered_result["Wealth"].iloc[-1], 94.5)
                self.assertAlmostEqual(original["Drawdown"].min(), -0.20)
                self.assertAlmostEqual(reordered_result["Drawdown"].min(), -0.28)

    def test_drawdown_requires_positive_initial_capital(self):
        for path, pok in self.modules.items():
            for start in (0, -100, np.nan, np.inf):
                with self.subTest(module=path, start=start):
                    with self.assertRaisesRegex(ValueError, "start must be positive and finite"):
                        pok.drawdown(pd.Series([-0.20]), start=start)

    def test_size_loader_returns_decimal_monthly_observations(self):
        for path, pok in self.modules.items():
            with self.subTest(module=path), patch.object(pok, "path_to_data_folder", return_value=str(ROOT / "data")):
                returns = pok.get_ffme_returns()
                self.assertEqual(returns.shape, (1110, 2))
                self.assertEqual(returns.columns.tolist(), ["Lo 10", "Hi 10"])
                self.assertTrue(returns.index.equals(pd.period_range("1926-07", "2018-12", freq="M")))
                np.testing.assert_allclose(returns.iloc[0], [-0.0145, 0.0329])

    def test_size_loader_treats_missing_sentinels_as_missing_returns(self):
        with tempfile.TemporaryDirectory() as data_dir:
            (Path(data_dir) / "Portfolios_Formed_on_ME_monthly_EW.csv").write_text(
                ",Lo 10,Hi 10\n200001,-99.99,1.0\n200002,2.0,-999\n"
            )
            for path, pok in self.modules.items():
                with self.subTest(module=path), patch.object(pok, "path_to_data_folder", return_value=data_dir):
                    returns = pok.get_ffme_returns()
                    self.assertTrue(np.isnan(returns.iloc[0, 0]))
                    self.assertTrue(np.isnan(returns.iloc[1, 1]))
                    self.assertAlmostEqual(returns.iloc[0, 1], 0.01)
                    self.assertAlmostEqual(returns.iloc[1, 0], 0.02)

    def test_browser_size_datasets_match_the_tested_snapshot(self):
        filename = "Portfolios_Formed_on_ME_monthly_EW.csv"
        expected = pd.read_csv(ROOT / "data" / filename, index_col=0)
        for directory in ("assets/data", "public/assets/data", "docs/public/assets/data"):
            with self.subTest(directory=directory):
                pd.testing.assert_frame_equal(
                    pd.read_csv(ROOT / directory / filename, index_col=0), expected
                )

    def test_standardized_moments_match_the_hand_calculation_and_reflection(self):
        returns = pd.Series([-0.04, 0.01, 0.01, 0.01, 0.01])
        for path, pok in self.modules.items():
            with self.subTest(module=path):
                self.assertAlmostEqual(pok.skewness(returns), -1.5)
                self.assertAlmostEqual(pok.kurtosis(returns), 3.25)
                self.assertAlmostEqual(pok.exkurtosis(returns), 0.25)
                self.assertAlmostEqual(pok.skewness(-returns), 1.5)
                self.assertAlmostEqual(pok.kurtosis(-returns), 3.25)
                self.assertAlmostEqual(pok.skewness(100 * returns + 5), -1.5)
                self.assertAlmostEqual(pok.kurtosis(100 * returns + 5), 3.25)

    def test_moment_estimators_handle_missing_values_per_column(self):
        returns = pd.DataFrame({
            "negative": [-0.04, 0.01, 0.01, 0.01, 0.01, np.nan],
            "positive": [np.nan, 0.04, -0.01, -0.01, -0.01, -0.01],
            "constant": [0.01] * 6,
        })
        for path, pok in self.modules.items():
            with self.subTest(module=path):
                np.testing.assert_allclose(pok.skewness(returns), [-1.5, 1.5, np.nan])
                np.testing.assert_allclose(pok.kurtosis(returns), [3.25, 3.25, np.nan])
                np.testing.assert_allclose(pok.exkurtosis(returns), [0.25, 0.25, np.nan])

    def test_constant_or_unavailable_data_do_not_produce_moments_or_decisions(self):
        for path, pok in self.modules.items():
            for values in ([], [np.nan], [0.01], [0.01] * 12, [0.0] * 12, [0.01, np.inf]):
                for function in (pok.skewness, pok.kurtosis, pok.exkurtosis, pok.is_normal):
                    with self.subTest(module=path, values=values, function=function.__name__):
                        self.assertTrue(np.isnan(function(pd.Series(values, dtype=float))))

    def test_jarque_bera_nonrejection_is_columnwise_and_not_proof_of_normality(self):
        # This discrete distribution has S=0, K=3, despite not being Gaussian.
        matching_moments = np.tile([-0.02, 0.0, 0.0, 0.0, 0.0, 0.02], 100)
        skewed = np.tile([0.0, 0.0, 0.0, 0.0, 0.0, 0.02], 100)
        frame = pd.DataFrame({"matching_moments": matching_moments, "skewed": skewed,
                              "constant": 0.01, "unobserved": np.nan})
        for path, pok in self.modules.items():
            with self.subTest(module=path):
                result = pok.is_normal(frame, level=0.01)
                self.assertEqual(result.index.tolist(), frame.columns.tolist())
                self.assertTrue(result["matching_moments"])
                self.assertFalse(result["skewed"])
                self.assertTrue(np.isnan(result["constant"]))
                self.assertTrue(np.isnan(result["unobserved"]))
                self.assertFalse(pok.is_normal(np.concatenate([[np.nan], skewed])))

    def test_normality_helper_validates_significance_levels(self):
        for path, pok in self.modules.items():
            for level in (-0.1, 0, 1, 1.1, np.nan, np.inf):
                with self.subTest(module=path, level=level):
                    with self.assertRaisesRegex(ValueError, "level must be between"):
                        pok.is_normal(pd.Series([-0.02, 0.0, 0.02]), level=level)

    def test_hedge_fund_loader_uses_day_first_dates_and_decimal_returns(self):
        for path, pok in self.modules.items():
            with self.subTest(module=path), patch.object(pok, "path_to_data_folder", return_value=str(ROOT / "data")):
                returns = pok.get_hfi_returns()
                self.assertEqual(returns.shape, (263, 13))
                self.assertTrue(returns.index.to_period("M").equals(pd.period_range("1997-01", "2018-11", freq="M")))
                self.assertEqual(returns.index[0], pd.Timestamp("1997-01-31"))
                self.assertAlmostEqual(returns["Convertible Arbitrage"].iloc[0], 0.0119)
                self.assertAlmostEqual(returns["CTA Global"].iloc[0], 0.0393)
                self.assertEqual(returns.index[3], pd.Timestamp("1997-04-30"))

    def test_browser_hedge_fund_datasets_match_the_tested_snapshot(self):
        filename = "edhec-hedgefundindices.csv"
        expected = pd.read_csv(ROOT / "data" / filename, index_col=0)
        for directory in ("assets/data", "public/assets/data", "docs/public/assets/data"):
            with self.subTest(directory=directory):
                pd.testing.assert_frame_equal(
                    pd.read_csv(ROOT / directory / filename, index_col=0), expected
                )

    def test_semivolatility_measures_only_dispersion_among_negative_returns(self):
        returns = pd.DataFrame({
            "mixed": [-0.04, -0.02, 0.01, 0.03],
            "constant_loss": [-0.02] * 4,
            "all_gains": [0.01] * 4,
            "missing": [np.nan] * 4,
        })
        for path, pok in self.modules.items():
            with self.subTest(module=path):
                np.testing.assert_allclose(pok.semivolatility(returns), [0.01, 0.0, np.nan, np.nan])

    def test_historical_var_uses_linear_interpolation_after_omitting_missing_values(self):
        returns = pd.Series([np.nan, -0.04, 0.05, 0.02, -0.07, 0.01, 0.005, -0.02, -0.01, -0.02, 0.05])
        for path, pok in self.modules.items():
            with self.subTest(module=path):
                self.assertAlmostEqual(pok.var_historic(returns, level=0.10), 0.043)
                self.assertAlmostEqual(pok.var_historic(returns, level=0.20), 0.024)

    def test_expected_shortfall_weights_integer_fractional_and_sub_observation_tails(self):
        returns = pd.Series([-0.04, 0.05, 0.02, -0.07, 0.01, 0.005, -0.02, -0.01, -0.02, 0.05])
        for path, pok in self.modules.items():
            for level, expected in ((0.10, 0.07), (0.20, 0.055), (0.25, 0.048), (0.01, 0.07)):
                with self.subTest(module=path, level=level):
                    self.assertAlmostEqual(pok.cvar_historic(returns, level=level), expected)

    def test_expected_shortfall_keeps_tied_boundary_losses(self):
        returns = pd.Series([-0.04, -0.04, 0.02, 0.03])
        for path, pok in self.modules.items():
            with self.subTest(module=path):
                self.assertAlmostEqual(pok.var_historic(returns, level=0.25), 0.04)
                self.assertAlmostEqual(pok.cvar_historic(returns, level=0.25), 0.04)

    def test_constant_outcomes_have_signed_loss_quantiles_and_expected_shortfalls(self):
        for path, pok in self.modules.items():
            for outcome in (-0.02, 0.0, 0.01):
                with self.subTest(module=path, outcome=outcome):
                    returns = pd.Series([outcome] * 12)
                    self.assertAlmostEqual(pok.var_historic(returns), -outcome)
                    self.assertAlmostEqual(pok.cvar_historic(returns), -outcome)
                    self.assertAlmostEqual(pok.var_gaussian(returns), -outcome)
                    self.assertAlmostEqual(pok.var_gaussian(returns, cf=True), -outcome)

    def test_tail_risk_missing_data_are_handled_per_column(self):
        values = [-0.04, 0.05, 0.02, -0.07, 0.01, 0.005, -0.02, -0.01, -0.02, 0.05]
        returns = pd.DataFrame({"A": values + [np.nan],
                                "B": [np.nan] + [2 * r for r in values],
                                "empty": [np.nan] * 11})
        for path, pok in self.modules.items():
            with self.subTest(module=path):
                np.testing.assert_allclose(pok.var_historic(returns, level=0.10), [0.043, 0.086, np.nan])
                np.testing.assert_allclose(pok.cvar_historic(returns, level=0.25), [0.048, 0.096, np.nan])

    def test_gaussian_var_uses_population_scale_and_cornish_fisher_reduces_correctly(self):
        # The first sample has mean 1%, std(ddof=0) 4%; the second also has S=0, K=3.
        sample = pd.Series([-0.03, 0.05, -0.03, 0.05, np.nan])
        normal_moments = pd.Series(0.01 + 0.04 * np.array([-np.sqrt(3), 0, 0, 0, 0, np.sqrt(3)]))
        for path, pok in self.modules.items():
            with self.subTest(module=path):
                self.assertAlmostEqual(pok.var_gaussian(sample, level=0.05), 0.05579414507805889)
                self.assertAlmostEqual(pok.var_gaussian(normal_moments, level=0.05, cf=True), 0.05579414507805889)
                result = pok.var_gaussian(pd.DataFrame({"A": sample, "B": 2 * sample}), level=0.05)
                np.testing.assert_allclose(result, [0.05579414507805889, 0.11158829015611778])

    def test_unavailable_tail_samples_return_nan(self):
        for path, pok in self.modules.items():
            for values in ([], [np.nan], [0.01, np.inf]):
                for function in (pok.var_historic, pok.var_gaussian, pok.cvar_historic):
                    with self.subTest(module=path, values=values, function=function.__name__):
                        self.assertTrue(np.isnan(function(pd.Series(values, dtype=float))))

    def test_tail_probability_validation(self):
        returns = pd.Series([-0.02, 0.01])
        for path, pok in self.modules.items():
            for level in (0, 1, -0.05, 95, np.nan, np.inf):
                for function in (pok.var_historic, pok.var_gaussian, pok.cvar_historic):
                    with self.subTest(module=path, level=level, function=function.__name__):
                        with self.assertRaisesRegex(ValueError, "level must be between"):
                            function(returns, level=level)

    def test_tail_risk_respects_positive_scaling_and_return_translation(self):
        returns = pd.Series([-0.08, -0.02, 0.01, 0.02, 0.03])
        for path, pok in self.modules.items():
            for function in (pok.var_historic, pok.var_gaussian, pok.cvar_historic):
                with self.subTest(module=path, function=function.__name__):
                    baseline = function(returns, level=0.30)
                    self.assertAlmostEqual(function(2 * returns, level=0.30), 2 * baseline)
                    self.assertAlmostEqual(function(returns + 0.01, level=0.30), baseline - 0.01)

    def test_portfolio_metrics_match_the_two_asset_hand_calculation(self):
        covariance = np.array([[0.01, 0.005], [0.005, 0.04]])
        for path, pok in self.modules.items():
            with self.subTest(module=path):
                self.assertAlmostEqual(pok.portfolio_return([0.6, 0.4], [0.08, 0.12]), 0.096)
                self.assertAlmostEqual(pok.portfolio_volatility([0.6, 0.4], covariance), 0.11135528725660045)

    def test_portfolio_volatility_respects_perfect_correlation_limits(self):
        volatilities = np.array([0.10, 0.20])
        positive = np.outer(volatilities, volatilities)
        negative = positive * np.array([[1.0, -1.0], [-1.0, 1.0]])
        for path, pok in self.modules.items():
            with self.subTest(module=path):
                self.assertAlmostEqual(pok.portfolio_volatility([0.6, 0.4], positive), 0.14)
                self.assertAlmostEqual(pok.portfolio_volatility([0.6, 0.4], negative), 0.02)
                self.assertAlmostEqual(pok.portfolio_volatility([2 / 3, 1 / 3], negative), 0.0, places=10)

    def test_exact_hedge_roundoff_does_not_create_nan_volatility(self):
        sigma_1, sigma_2 = 0.07, 0.11
        covariance = np.array([[sigma_1 ** 2, -sigma_1 * sigma_2],
                               [-sigma_1 * sigma_2, sigma_2 ** 2]])
        weights = np.array([sigma_2, sigma_1]) / (sigma_1 + sigma_2)
        for path, pok in self.modules.items():
            with self.subTest(module=path):
                result = pok.portfolio_volatility(weights, covariance)
                self.assertTrue(np.isfinite(result))
                self.assertAlmostEqual(result, 0.0, places=10)
                # Small but genuinely positive variance must not be rounded to zero.
                self.assertEqual(pok.portfolio_volatility([1.0], [[1e-24]]), 1e-12)

    def test_invalid_portfolio_variance_or_dimensions_are_not_silently_clipped(self):
        for path, pok in self.modules.items():
            with self.subTest(module=path):
                for variance in (-1.0, -1e-24):
                    with self.assertRaisesRegex(ValueError, "negative portfolio variance"):
                        pok.portfolio_volatility([1.0], [[variance]])
                with self.assertRaisesRegex(ValueError, "matching square covariance"):
                    pok.portfolio_volatility([0.5, 0.5], np.eye(3))
                with self.assertRaisesRegex(ValueError, "must be finite"):
                    pok.portfolio_volatility([np.nan, 1.0], np.eye(2))


if __name__ == "__main__":
    unittest.main()
