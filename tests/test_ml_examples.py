"""Independent worked answers, chronology, chart values, and ML widget parity."""
import ast
import contextlib
import io
import json
import re
import unittest

import numpy as np
import pandas as pd
import PortfolioOptimizationKit as pok

from test_return_annualization import ROOT, MODULE_PATHS


class MachineLearningExampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.markdown = (ROOT / 'docs/3.1-ml-fundamentals.md').read_text()
        cls.examples = dict((editor, code) for code, editor in re.findall(
            r'```python:line-numbers\n(.*?)\n```\s*<Editor id="([^"]+)"\s*/>', cls.markdown, re.S))
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

    def test_cells_and_charts_execute_in_order(self):
        ids = re.findall(r'<Editor id="([^"]+)"', self.markdown)
        self.assertEqual(ids, list(self.examples))
        self.assertEqual(len(ids), 10)
        self.assertEqual(self.markdown.count('```python'), 10)
        self.assertEqual(len(self.charts), 7)

    def test_four_row_arithmetic_and_least_squares_normal_equations(self):
        v = self.values
        np.testing.assert_allclose(v['baseline_errors'], [-2, 0, 0, 2])
        self.assertEqual(v['baseline_mean'], 1)
        self.assertEqual(v['baseline_mse'], 2)
        self.assertAlmostEqual(v['slope'], 1.2)
        self.assertAlmostEqual(v['intercept'], 0.4)
        np.testing.assert_allclose(v['line_train_predictions'], [-0.8, 0.4, 1.6, 2.8])
        residual = v['y_train'] - v['library_predictions']
        np.testing.assert_allclose(np.column_stack([np.ones(4), v['x_train']]).T @ residual, 0, atol=1e-12)
        self.assertAlmostEqual(v['line_train_mse'], 0.2)
        self.assertAlmostEqual(v['exercise_prediction'], 1)
        self.assertAlmostEqual(v['exercise_error'] ** 2, 0.09)

    def test_split_labels_and_forecast_availability(self):
        v = self.values
        for block in ('train', 'validation', 'test'):
            frame = v[block]
            self.assertEqual(len(frame), 4)
            self.assertTrue((pd.PeriodIndex(frame['Target month']) == frame.index + 1).all())
        self.assertEqual(v['train']['Target month'].max(), v['validation'].index.min())
        self.assertEqual(v['validation']['Target month'].max(), v['test'].index.min())
        self.assertTrue(v['train'].index.intersection(v['validation'].index).empty)
        self.assertTrue(v['development'].index.intersection(v['test'].index).empty)
        self.assertEqual(str(v['test_results'].index[0]), '2020-10')
        self.assertEqual(str(v['test_results'].index[-1]), '2021-01')

    def test_candidate_errors_and_tie_break_match_worked_results(self):
        v = self.values
        np.testing.assert_allclose(v['scores']['Training'], [2, .2, .2, 0], atol=1e-12)
        np.testing.assert_allclose(v['scores']['Validation'], [.5475, .0375, .0375, .1725], atol=1e-12)
        self.assertEqual(v['selected_degree'], 1)
        cubic = v['candidate_models'][3]
        np.testing.assert_allclose(cubic[-1].coef_, [1/3, -1, 2/3], atol=1e-12)
        self.assertAlmostEqual(cubic[-1].intercept_, 1)

    def test_final_refit_and_frozen_baseline(self):
        v = self.values
        # Independent linear solve rather than the lesson's sklearn pipeline.
        x = v['development']['Feature (%)'].to_numpy()
        design = np.column_stack([np.ones(8), x])
        coefficients = np.linalg.solve(design.T @ design, design.T @ v['development']['Target (%)'])
        expected = coefficients[0] + coefficients[1] * v['test']['Feature (%)'].to_numpy()
        np.testing.assert_allclose(v['test_predictions'], expected, atol=1e-12)
        np.testing.assert_allclose(v['test_baseline'], 1.0625)
        self.assertAlmostEqual(v['test_mse'], 0.02372842525439931)
        self.assertAlmostEqual(v['test_baseline_mse'], 1.06078125)

    def test_test_outcomes_cannot_change_selection_or_final_predictions(self):
        v = self.values.copy()
        v['test'] = v['test'].copy()
        v['test']['Target (%)'] = [100, -200, 300, -400]
        with contextlib.redirect_stdout(io.StringIO()):
            exec(self.examples['ml-model-selection'], v)
            exec(self.examples['ml-final-test'], v)
        self.assertEqual(v['selected_degree'], self.values['selected_degree'])
        np.testing.assert_allclose(v['test_predictions'], self.values['test_predictions'])
        np.testing.assert_allclose(v['test_baseline'], self.values['test_baseline'])
        self.assertGreater(v['test_mse'], 1000)

    def test_chart_tables_dates_and_units_agree(self):
        v, charts = self.values, self.charts
        for key, table in [('mlBaseline', v['train']), ('mlValidation', v['validation'])]:
            self.assertEqual(charts[key]['xAxis']['data'], table.index.astype(str).tolist())
            np.testing.assert_allclose(charts[key]['series']['Actual'], table['Target (%)'])
            self.assertIn('(%)', charts[key]['yAxisName'])
        np.testing.assert_allclose(charts['mlBaseline']['series']['Training mean'], v['baseline_predictions'])
        np.testing.assert_allclose(charts['mlValidation']['series']['Fitted line'], v['validation_predictions'])
        for name in ('Training', 'Validation'):
            np.testing.assert_allclose(charts['mlModelSelection']['series'][name], v['scores'][name])
        self.assertEqual(charts['mlModelSelection']['yAxisName'], 'Mean squared error (pp²)')
        final = charts['mlFinalTest']
        self.assertEqual(final['xAxis']['data'], v['test_results'].index.astype(str).tolist())
        for name, column in [('Actual', 'Actual (%)'), ('Selected model', 'Selected model (%)'), ('Development mean', 'Baseline (%)')]:
            np.testing.assert_allclose(final['series'][name], v['test_results'][column])
        line = np.array(charts['mlFittedLine']['series']['Fitted line'])
        np.testing.assert_allclose(line[:, 1], .4 + 1.2 * line[:, 0])

    def test_widget_curves_match_analytical_polynomials_and_lesson_data(self):
        for degree in (1, 2, 3):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                pok.show_ml_complexity_echart(degree)
            payload = json.loads(output.getvalue().split('<ECHARTS_DATA>')[1])
            series = payload['mlComplexityFit']['series']
            grid, prediction = np.array(series['Fitted curve']).T
            expected = .4 + 1.2 * grid if degree < 3 else 1 + grid/3 - grid**2 + 2*grid**3/3
            np.testing.assert_allclose(prediction, expected, atol=1e-12)
            for name, block in [('Training', 'train'), ('Validation', 'validation')]:
                np.testing.assert_allclose(series[name], self.values[block][['Feature (%)', 'Target (%)']])
            np.testing.assert_allclose(payload['mlComplexityError']['series']['Selected curve'],
                                       self.values['scores'].loc[degree], atol=1e-12)
            self.assertEqual(set(series), {'Training', 'Validation', 'Fitted curve', 'Training mean'})

    def test_widget_rejects_invalid_degrees(self):
        for degree in (0, 4, -1, 1.5, 2.0, True, np.bool_(False), '2', None):
            with self.subTest(degree=degree), self.assertRaises(ValueError):
                pok.show_ml_complexity_echart(degree)

    def test_widget_source_matches_across_published_copies(self):
        definitions = []
        for path in MODULE_PATHS:
            node = next(n for n in ast.parse((ROOT / path).read_text()).body
                        if isinstance(n, ast.FunctionDef) and n.name == 'show_ml_complexity_echart')
            definitions.append(ast.dump(node))
        self.assertEqual(len(set(definitions)), 1)

    def test_new_widget_exports_callback_and_integer_parameter(self):
        source = (ROOT / 'src/pyodide-worker.js').read_text()
        export = next(block for block in re.findall(r'pyodide\.runPython\(`(.*?)`\)', source, re.S)
                      if 'from ipywidgets.embed import dependency_state' in block)
        namespace = {'widget_instance': self.values['widget_instance']}
        exec(export, namespace)
        state = json.loads(namespace['_widget_json_result'])['state']
        box = self.values['widget_instance']
        self.assertEqual(state[box.model_id]['state']['_echarts_callback'], 'show_ml_complexity_echart')
        self.assertEqual(state[box.model_id]['state']['_echarts_kwargs'], {'degree': 1})


if __name__ == '__main__':
    unittest.main()
