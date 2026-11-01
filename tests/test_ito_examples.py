"""Independent moment, pathwise, funding-convention, and log-price checks for Itô."""
import ast
import contextlib
import importlib.util
import io
import json
import math
import re
import unittest

import numpy as np
import PortfolioOptimizationKit as pok

from test_return_annualization import ROOT, MODULE_PATHS


class ItoExampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.markdown = (ROOT / 'docs/random-motion-ito.md').read_text()
        cls.examples = {editor: code for code, editor in re.findall(
            r'```python:line-numbers\n(.*?)\n```\s*<Editor id="([^"]+)"\s*/>', cls.markdown, re.S)}
        cls.values, output = {}, io.StringIO()
        with contextlib.redirect_stdout(output):
            for editor, code in cls.examples.items():
                exec(compile(code, editor, 'exec'), cls.values)
        cls.charts = {}
        for line in output.getvalue().splitlines():
            if line.startswith('<ECHARTS_DATA>'):
                cls.charts.update(json.loads(line[len('<ECHARTS_DATA>'):]))

    @classmethod
    def tearDownClass(cls):
        cls.values['widget_instance'].close()

    def rerun(self, editor, old, new):
        namespace = dict(self.values)
        with contextlib.redirect_stdout(io.StringIO()):
            exec(self.examples[editor].replace(old, new), namespace)
        return namespace

    def test_every_example_and_chart_is_executable_finite_and_labeled(self):
        ids = re.findall(r'<Editor id="([^"]+)"', self.markdown)
        self.assertEqual(ids, list(self.examples))
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 10)
        self.assertEqual(self.markdown.count('```python'), 10)
        self.assertEqual(len(self.charts), 9)
        for chart in self.charts.values():
            self.assertTrue(chart['yAxisName'])
            self.assertTrue(chart['xAxis']['name'])
            json.dumps(chart, allow_nan=False)
            for data in chart['series'].values():
                self.assertTrue(np.isfinite(data).all())

    def test_curvature_numbers_and_shock_scaling(self):
        v = self.values
        np.testing.assert_allclose(v['curvature_table'], [[1.9, 3.61, -.39, -.4, .01], [2.1, 4.41, .41, .4, .01]])
        np.testing.assert_allclose(v['exact_changes'], v['linear_changes'] + v['curvature_changes'])
        changed = self.rerun('ito-curvature', '[-0.1, 0.1]', '[-0.2, 0.2]')
        self.assertAlmostEqual((changed['inputs'] ** 2).mean(), 4.04)
        np.testing.assert_allclose(changed['curvature_changes'], 4 * v['curvature_changes'])
        chart = self.charts['itoCurvature']['series']
        np.testing.assert_allclose(chart['Two outcomes'], [[1.9, 3.61], [2.1, 4.41]])
        x, y = np.array(chart['Tangent at 2']).T
        np.testing.assert_allclose(y, 4 + 4 * (x - 2))

    def test_brownian_increment_scaling_and_path_construction(self):
        v = self.values
        self.assertEqual(v['path_dt'], 1/256)
        self.assertEqual(np.sqrt(v['path_dt']), 1/16)
        self.assertEqual(v['brownian_paths'].shape, (257, 4))
        np.testing.assert_allclose(v['brownian_paths'][0], 0)
        np.testing.assert_allclose(np.diff(v['brownian_paths'], axis=0), v['path_increments'], atol=1e-14)
        changed = self.rerun('ito-brownian', 'path_steps = 256', 'path_steps = 64')
        self.assertEqual(np.sqrt(changed['path_dt']), .125)
        for index, values in enumerate(self.charts['itoBrownianPaths']['series'].values()):
            np.testing.assert_allclose(values, np.column_stack([v['path_times'], v['brownian_paths'][:, index]]))

    def test_nested_endpoints_moments_and_smooth_comparison(self):
        v = self.values
        qv = v['qv_table']
        np.testing.assert_allclose(qv['Endpoint W'], v['fine_increments'].sum())
        np.testing.assert_allclose(qv['Theoretical SD (years)'], [math.sqrt(2/n) for n in (16, 64, 256, 1024, 4096)])
        np.testing.assert_allclose(qv['Smooth squared sum'], [1/16, 1/64, 1/256, 1/1024, 1/4096])
        # Independent normal quadrature checks the moment argument behind Q_n's variance.
        nodes, weights = np.polynomial.hermite.hermgauss(24)
        z, probabilities = nodes * math.sqrt(2), weights / math.sqrt(math.pi)
        self.assertAlmostEqual(np.dot(probabilities, z**2), 1)
        self.assertAlmostEqual(np.dot(probabilities, z**4), 3)
        for horizon, count in ((1, 16), (1, 4096), (.5, 64)):
            squared = horizon / count * z**2
            mean = np.dot(probabilities, squared)
            variance = np.dot(probabilities, (squared - mean)**2)
            self.assertAlmostEqual(count * mean, horizon)
            self.assertAlmostEqual(count * variance, 2 * horizon**2 / count)
        chart = self.charts['itoQuadraticVariation']
        self.assertIn('dimensionless', chart['yAxisName'])
        np.testing.assert_allclose(chart['series']['Brownian squared sum'], qv['Squared sum (years)'])
        self.assertGreater(abs(qv['Squared sum (years)'].iloc[-1] - 1), 1e-5)

    def test_pathwise_square_identity_left_endpoint_and_midpoint(self):
        v = self.values
        np.testing.assert_allclose(v['square_discrete'], v['square_exact'], atol=1e-12)
        np.testing.assert_allclose(v['square_ito'] - v['square_exact'], v['square_times'] - v['square_qv'], atol=1e-12)
        # Midpoint weighting has a different limit; its exact finite sum includes Q_n.
        w, dw = v['square_path'], v['square_increments']
        midpoint = np.r_[0, np.cumsum((w[:-1] + w[1:]) * dw)]
        np.testing.assert_allclose(midpoint, v['square_exact'], atol=1e-12)
        np.testing.assert_allclose(midpoint - v['square_first_order'], v['square_qv'], atol=1e-12)
        changed = self.rerun('ito-square-identity', 'square_steps = 256', 'square_steps = 1024')
        np.testing.assert_allclose(changed['square_path'][::4], v['square_path'], atol=1e-12)
        hand_dw = np.array([.5, -.5, .5, .5])
        hand_w = np.r_[0, np.cumsum(hand_dw)]
        self.assertEqual(2 * np.dot(hand_w[:-1], hand_dw), 0)
        self.assertEqual(np.dot(hand_dw, hand_dw), 1)
        self.assertEqual(hand_w[-1]**2, 1)

    def test_general_formula_time_drift_curvature_and_conditional_expectation(self):
        v = self.values
        self.assertAlmostEqual(v['transformed_drift'], .51)
        self.assertAlmostEqual(v['transformed_noise'], 1.2)
        np.testing.assert_allclose(v['transformed_exact'], [-.114959, .125161])
        np.testing.assert_allclose(v['transformed_ito'], [-.1149, .1251])
        self.assertAlmostEqual(v['exact_expected_change'], .005101)
        # Integrate the actual finite Gaussian step, rather than assuming the two displayed shocks are the distribution.
        nodes, weights = np.polynomial.hermite.hermgauss(24)
        dw = math.sqrt(2 * .01) * nodes
        exact = (2 + .1 * .01 + .3 * dw)**2 + .02 * .01 - 4
        self.assertAlmostEqual(np.dot(weights, exact) / math.sqrt(math.pi), .005101)
        zero = self.rerun('ito-general-formula', '2., 0.1, 0.3, 0.02', '2., 0.1, 0.0, 0.02')
        np.testing.assert_allclose(zero['transformed_exact'] - zero['transformed_ito'], .000001, atol=1e-12)
        doubled = self.rerun('ito-general-formula', '2., 0.1, 0.3, 0.02', '2., 0.1, 0.6, 0.02')
        self.assertAlmostEqual(doubled['transformed_drift'], .78)
        self.assertAlmostEqual(doubled['transformed_noise'], 2.4)

    def test_return_conventions_log_price_solution_and_gaussian_mean(self):
        v = self.values
        self.assertAlmostEqual(v['continuous_rate'], math.log(1.05))
        for horizon in (.5, 1, 2):
            self.assertAlmostEqual(math.exp(v['continuous_rate'] * horizon), 1.05**horizon)
        np.testing.assert_allclose(np.expm1(v['log_returns']), v['simple_returns'], atol=1e-12)
        self.assertAlmostEqual(v['log_drift'], .06)
        self.assertTrue((v['gbm_prices'] > 0).all())
        np.testing.assert_allclose(np.log(v['gbm_prices'] / 100), .06 * v['price_times'] + .2 * v['price_brownian'], atol=1e-12)
        np.testing.assert_allclose(v['uncorrected_prices'] / v['gbm_prices'], np.exp(.02 * v['price_times']))
        nodes, weights = np.polynomial.hermite.hermgauss(32)
        terminal_prices = 100 * np.exp(.06 + .2 * math.sqrt(2) * nodes)
        self.assertAlmostEqual(np.dot(weights, terminal_prices) / math.sqrt(math.pi), 100 * math.exp(.08))
        self.assertAlmostEqual(v['mean_prices'][-1], 108.32870676749586)
        self.assertAlmostEqual(v['median_prices'][-1], 106.18365465453596)
        changed = self.rerun('ito-log-price', '100., 0.08, 0.20', '100., 0.08, 0.40')
        self.assertAlmostEqual(changed['log_drift'], 0)
        self.assertAlmostEqual(changed['median_prices'][-1], 100)
        np.testing.assert_allclose(changed['mean_prices'], v['mean_prices'])
        zero = self.rerun('ito-log-price', '100., 0.08, 0.20', '100., 0.08, 0.0')
        for name in ('gbm_prices', 'uncorrected_prices', 'median_prices'):
            np.testing.assert_allclose(zero[name], v['mean_prices'])

    def test_exercise_horizon_units_and_realization(self):
        v = self.values
        self.assertAlmostEqual(v['exercise_log_drift'], .015)
        self.assertAlmostEqual(v['exercise_expected_log'], .0075)
        self.assertAlmostEqual(v['exercise_realized_log'], .0675)
        self.assertAlmostEqual(v['exercise_price'], 85.58642076812977)
        self.assertAlmostEqual(v['exercise_mean'], 82.43636271628135)
        self.assertAlmostEqual(v['exercise_median'], 80.60225563556271)
        self.assertAlmostEqual(v['exercise_qv_sd'], math.sqrt(1/128))

    def test_all_widget_grids_are_nested_and_preserve_discrete_identities(self):
        finest_square = None
        for power in range(12, 3, -1):
            with contextlib.redirect_stdout(output := io.StringIO()):
                pok.show_ito_refinement_echart(power)
            text, raw = output.getvalue().split('<ECHARTS_DATA>')
            charts = json.loads(raw)
            self.assertIn(f'Grid power: {power}; intervals: {2**power}', text)
            series = charts['itoRefinementSquare']['series']
            exact = np.array(series['Exact square'])
            first = np.array(series['First order only'])[:, 1]
            corrected = np.array(series['First order + time'])[:, 1]
            qv = np.array(charts['itoRefinementVariation']['series']['Squared increments'])[:, 1]
            self.assertEqual(len(exact), 2**power + 1)
            self.assertEqual(exact[0, 0], 0)
            self.assertEqual(exact[-1, 0], 1)
            if finest_square is None:
                finest_square = exact
            np.testing.assert_allclose(exact, finest_square[::2**(12-power)], atol=1e-12)
            np.testing.assert_allclose(first + qv, exact[:, 1], atol=1e-12)
            np.testing.assert_allclose(corrected - exact[:, 1], exact[:, 0] - qv, atol=1e-12)
            self.assertTrue((np.diff(qv) >= 0).all())
            if power == 8:
                np.testing.assert_allclose(exact[:, 1], self.values['square_exact'])
                np.testing.assert_allclose(qv, self.values['square_qv'])

    def test_widget_invalid_inputs(self):
        for power in (3, 13, 8.0, True, None, '8', np.nan):
            with self.subTest(power=power), self.assertRaises(ValueError):
                pok.show_ito_refinement_echart(power)

    def test_helper_copies_match_and_execute(self):
        definitions, outputs = [], []
        for index, path in enumerate(MODULE_PATHS):
            tree = ast.parse((ROOT / path).read_text())
            definitions.append(ast.dump(next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                                              and n.name == 'show_ito_refinement_echart')))
            spec = importlib.util.spec_from_file_location(f'ito_copy_{index}', ROOT / path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with contextlib.redirect_stdout(output := io.StringIO()):
                module.show_ito_refinement_echart(4)
            outputs.append(output.getvalue())
        self.assertEqual(len(definitions), 6)
        self.assertEqual(len(set(definitions)), 1)
        self.assertEqual(len(set(outputs)), 1)

    def test_widget_standalone_callback_and_grid_keyword(self):
        namespace = {}
        with contextlib.redirect_stdout(io.StringIO()):
            exec(self.examples['ito-refinement-widget'], namespace)
        widget = namespace['widget_instance']
        try:
            export = next(block for block in re.findall(r'pyodide\.runPython\(`(.*?)`\)',
                          (ROOT / 'src/pyodide-worker.js').read_text(), re.S)
                          if 'from ipywidgets.embed import dependency_state' in block)
            exec(export, namespace)
            state = json.loads(namespace['_widget_json_result'])['state']
            box = state[widget.model_id]['state']
            self.assertEqual(box['_echarts_callback'], 'show_ito_refinement_echart')
            self.assertEqual(box['_echarts_kwargs'], {'grid_power': 8})
            slider = next(item['state'] for item in state.values() if item['model_name'] == 'IntSliderModel')
            self.assertEqual(slider['_echarts_parameter'], 'grid_power')
            self.assertEqual(slider['min'], 4)
            self.assertEqual(slider['max'], 12)
        finally:
            widget.close()


if __name__ == '__main__':
    unittest.main()
