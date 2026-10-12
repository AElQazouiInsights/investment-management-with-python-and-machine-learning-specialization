"""Protect runnable lesson coverage and the helpers actually published to browsers."""

import ast
import re
import unittest

from test_return_annualization import MODULE_PATHS, ROOT


class IntroDependencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.chapters = {
            chapter: (ROOT / "docs" / f"{chapter}.md").read_text()
            for chapter in ("1.0-overview", "1.1-risks", "1.2-optimization")
        }

    def test_every_python_example_has_a_unique_runnable_editor(self):
        all_ids = []
        for chapter, markdown in self.chapters.items():
            fences = re.findall(r'^```python[^\n]*\n(.*?)^```[ \t]*$', markdown, re.M | re.S)
            paired = re.findall(r'^```python[^\n]*\n(.*?)^```[ \t]*\n\s*<Editor id="([^"]+)"\s*/>',
                                markdown, re.M | re.S)
            ids = re.findall(r'<Editor\s+id="([^"]+)"', markdown)
            with self.subTest(chapter=chapter):
                self.assertEqual([code for code, _ in paired], fences)
                self.assertEqual([editor_id for _, editor_id in paired], ids)
            all_ids.extend(ids)
        self.assertEqual(len(all_ids), len(set(all_ids)))

    def test_direct_and_transitive_lesson_helpers_match_every_published_copy(self):
        copies = {
            path: {node.name: node for node in ast.parse((ROOT / path).read_text()).body
                   if isinstance(node, ast.FunctionDef)}
            for path in MODULE_PATHS
        }
        reference = copies[MODULE_PATHS[0]]
        dependencies = set()
        for markdown in self.chapters.values():
            for code in re.findall(r'^```python[^\n]*\n(.*?)^```[ \t]*$', markdown, re.M | re.S):
                dependencies.update(node.attr for node in ast.walk(ast.parse(code))
                                    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                                    and node.value.id == "pok")
        pending = list(dependencies)
        while pending:
            for node in ast.walk(reference[pending.pop()]):
                if isinstance(node, ast.Name) and node.id in reference and node.id not in dependencies:
                    dependencies.add(node.id)
                    pending.append(node.id)
        self.assertTrue(dependencies)
        for path, functions in copies.items():
            for name in sorted(dependencies):
                with self.subTest(copy=path, helper=name):
                    self.assertEqual(ast.dump(reference[name]), ast.dump(functions[name]))


if __name__ == "__main__":
    unittest.main()
