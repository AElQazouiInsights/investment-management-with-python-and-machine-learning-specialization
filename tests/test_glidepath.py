"""Beginning-period timing, sequence effects, and paired glide-path comparisons."""

import __main__
import ast
import importlib.util
import json
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from test_return_annualization import MODULE_PATHS, ROOT


class GlidePathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules = {}
        for i, path in enumerate(MODULE_PATHS):
            spec = importlib.util.spec_from_file_location(f"glide_copy_{i}", ROOT / path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cls.modules[path] = module

    def test_schedule_preserves_labels_endpoints_and_mean_target(self):
        returns = pd.DataFrame(0.01, index=pd.date_range("2020-06-30", periods=20, freq="6ME"), columns=["A", "B"])
        for path, module in self.modules.items():
            with self.subTest(module=path):
                weights = module.ldi_glidepath_allocator(returns, returns, 0.8, 0.2)
                pd.testing.assert_index_equal(weights.index, returns.index)
                pd.testing.assert_index_equal(weights.columns, returns.columns)
                np.testing.assert_allclose(weights.iloc[0], 0.8)
                np.testing.assert_allclose(weights.iloc[-1], 0.2)
                np.testing.assert_allclose(np.diff(weights["A"]), -0.6 / 19)
                np.testing.assert_allclose(weights.mean(), 0.5)
                np.testing.assert_array_equal(weights["A"], weights["B"])

    def test_targets_do_not_depend_on_future_or_scenario_returns(self):
        first = pd.DataFrame({"A": [0.1, -0.2, 0.3], "B": [-0.1, 0.2, -0.3]}, index=[1, 2, 3])
        changed = first.copy()
        changed.iloc[-1] = [0.99, -0.9]
        for path, module in self.modules.items():
            with self.subTest(module=path):
                pd.testing.assert_frame_equal(module.ldi_glidepath_allocator(first, first, 0.8, 0.2),
                                              module.ldi_glidepath_allocator(changed, changed, 0.8, 0.2))

    def test_single_interval_uses_start_and_equal_endpoints_reproduce_fixed_mix(self):
        stocks = pd.DataFrame({"A": [0.1, -0.2, 0.3]}, index=[1, 2, 3])
        bonds = stocks * 0 + 0.01
        for path, module in self.modules.items():
            with self.subTest(module=path):
                weights = module.ldi_glidepath_allocator(stocks.iloc[:1], bonds.iloc[:1], 0.8, 0.2)
                self.assertEqual(weights.iloc[0, 0], 0.8)
                for weight in (0, 0.5, 1):
                    glide = module.ldi_mixer(stocks, bonds, module.ldi_glidepath_allocator, start=weight, end=weight)
                    fixed = module.ldi_mixer(stocks, bonds, module.ldi_fixed_allocator, w1=weight)
                    pd.testing.assert_frame_equal(glide, fixed)

    def test_return_order_matters_for_glide_but_not_constant_weights_and_no_floor_is_guaranteed(self):
        early_loss = pd.DataFrame({"Path": [-0.5, 0]}, index=[1, 2])
        late_loss = pd.DataFrame({"Path": [0, -0.5]}, index=[1, 2])
        flat = early_loss * 0
        for path, module in self.modules.items():
            with self.subTest(module=path):
                early = module.ldi_mixer(early_loss, flat, module.ldi_glidepath_allocator, start=0.8, end=0.2)
                late = module.ldi_mixer(late_loss, flat, module.ldi_glidepath_allocator, start=0.8, end=0.2)
                self.assertAlmostEqual(module.terminal_wealth(early).iloc[0], 0.6)
                self.assertAlmostEqual(module.terminal_wealth(late).iloc[0], 0.9)
                self.assertLess(module.terminal_wealth(early).iloc[0], 0.8)
                for stocks in (early_loss, late_loss):
                    fixed = module.ldi_mixer(stocks, flat, module.ldi_fixed_allocator, w1=0.5)
                    self.assertAlmostEqual(module.terminal_wealth(fixed).iloc[0], 0.75)

    def test_invalid_weights_and_misaligned_frames_are_rejected(self):
        frame = pd.DataFrame({"A": [0.01, 0.02]}, index=[1, 2])
        for path, module in self.modules.items():
            for kwargs in ({"start": -0.1}, {"end": 1.1}, {"start": np.nan}, {"end": np.inf}):
                with self.subTest(module=path, kwargs=kwargs), self.assertRaises(ValueError):
                    module.ldi_glidepath_allocator(frame, frame, **kwargs)
            for bad in (frame.rename(columns={"A": "B"}), frame.set_axis([0, 1]), frame.iloc[:0]):
                with self.subTest(module=path), self.assertRaises(ValueError):
                    module.ldi_glidepath_allocator(frame, bad)

    def test_chart_targets_use_decision_times_and_wealth_uses_the_same_scenarios(self):
        for path, module in self.modules.items():
            messages = []
            with self.subTest(module=path), patch.object(__main__, "_emit_echarts", messages.append, create=True):
                module.show_glidepath_echart(n_years=2, n_scenarios=10)
                text, encoded = messages[-1].split("<ECHARTS_DATA>")
                plots = json.loads(encoded)
                targets = np.asarray(plots["glideTargets"]["series"]["Glide path"])
                np.testing.assert_allclose(targets[:, 0], [0, 0.5, 1, 1.5, 2])
                np.testing.assert_allclose(targets[:, 1], [80, 60, 40, 20, 20])
                self.assertEqual(plots["glideTargets"]["seriesOptions"]["Glide path"]["step"], "end")
                sample = module.simulate_psp_lhp(n_years=2, n_scenarios=10)
                glide = module.ldi_mixer(sample["Stocks"], sample["Bonds"], module.ldi_glidepath_allocator, start=0.8, end=0.2)
                expected = np.median(np.vstack([np.ones(10), (1 + glide).cumprod()]), axis=1)
                np.testing.assert_allclose(np.asarray(plots["glideWealth"]["series"]["Glide path"])[:, 1], expected)
                self.assertIn("last applied target 20.0% at year 1.5", text)
                self.assertIn("does not guarantee a floor", text)

    def test_changing_endpoints_preserves_fixed_comparator_and_one_interval_chart_is_defined(self):
        module = self.modules["PortfolioOptimizationKit.py"]
        messages = []
        with patch.object(__main__, "_emit_echarts", messages.append, create=True):
            module.show_glidepath_echart(n_years=2, n_scenarios=10)
            module.show_glidepath_echart(start=0.2, end=0.8, n_years=2, n_scenarios=10)
            module.show_glidepath_echart(n_years=0.5, n_scenarios=10)
        charts = [json.loads(message.split("<ECHARTS_DATA>")[1]) for message in messages]
        self.assertEqual(charts[0]["glideWealth"]["series"]["Fixed 70/30"], charts[1]["glideWealth"]["series"]["Fixed 70/30"])
        self.assertNotEqual(charts[0]["glideWealth"]["series"]["Glide path"], charts[1]["glideWealth"]["series"]["Glide path"])
        np.testing.assert_allclose(charts[2]["glideTargets"]["series"]["Glide path"], [[0, 80], [0.5, 80]])

    def test_glide_helpers_match_across_toolkit_copies(self):
        names = {"ldi_glidepath_allocator", "show_glidepath_echart"}
        definitions = []
        for path in MODULE_PATHS:
            definitions.append({node.name: ast.dump(node) for node in ast.parse((ROOT / path).read_text()).body
                                if isinstance(node, ast.FunctionDef) and node.name in names})
        self.assertEqual(set(definitions[0]), names)
        for candidate in definitions[1:]:
            self.assertEqual(candidate, definitions[0])


if __name__ == "__main__":
    unittest.main()
