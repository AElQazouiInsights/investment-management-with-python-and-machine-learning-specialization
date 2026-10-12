"""Exercise the worker's actual Python widget export against native ipywidgets."""

import json
import re
import unittest

import ipywidgets as widgets

from test_return_annualization import ROOT


class WidgetSerializationTests(unittest.TestCase):
    def test_interactive_keywords_survive_custom_display_labels(self):
        source = (ROOT / "src/pyodide-worker.js").read_text()
        blocks = re.findall(r"pyodide\.runPython\(`(.*?)`\)", source, re.DOTALL)
        export = next(block for block in blocks if "from ipywidgets.embed import dependency_state" in block)
        amount = widgets.IntSlider(value=130000, max=250000, description="Assets ($)")
        frequency = widgets.Dropdown(options=[("Annual", 1), ("Quarterly", 4)], value=4, description="Long coupons")
        box = widgets.interactive(lambda asset_value, long_frequency, seed: None,
                                  asset_value=amount, long_frequency=frequency, seed=widgets.fixed(9))
        try:
            namespace = {"widget_instance": box}
            exec(export, namespace)
            state = json.loads(namespace["_widget_json_result"])["state"]
            self.assertEqual(state[box.model_id]["state"]["_echarts_kwargs"],
                             {"asset_value": 130000, "long_frequency": 4, "seed": 9})
            self.assertEqual(state[amount.model_id]["state"]["description"], "Assets ($)")
            self.assertEqual(state[amount.model_id]["state"]["_echarts_parameter"], "asset_value")
            selection = state[frequency.model_id]["state"]
            self.assertEqual(selection["_echarts_parameter"], "long_frequency")
            self.assertEqual(selection["_echarts_option_values"][selection["index"]], 4)
        finally:
            box.close()
            amount.close()
            frequency.close()

    def test_export_preserves_float_steps_and_dropdown_values(self):
        source = (ROOT / "src/pyodide-worker.js").read_text()
        blocks = re.findall(r"pyodide\.runPython\(`(.*?)`\)", source, re.DOTALL)
        export = next(block for block in blocks if "from ipywidgets.embed import dependency_state" in block)
        amount = widgets.FloatSlider(value=1.0, min=0.5, max=2.0, step=0.1)
        frequency = widgets.Dropdown(options=[("Monthly", 12), ("Weekly", 52)], value=52)
        box = widgets.VBox([amount, frequency])
        try:
            namespace = {"widget_instance": box}
            exec(export, namespace)
            state = json.loads(namespace["_widget_json_result"])["state"]
            slider = state[amount.model_id]["state"]
            self.assertEqual(slider["_model_name"], "FloatSliderModel")
            self.assertEqual(slider["step"], 0.1)
            self.assertEqual(slider["value"], 1.0)
            selection = state[frequency.model_id]["state"]
            self.assertEqual(selection["_options_labels"], ["Monthly", "Weekly"])
            self.assertEqual(selection["_echarts_option_values"][selection["index"]], 52)
        finally:
            box.close()
            amount.close()
            frequency.close()


if __name__ == "__main__":
    unittest.main()
