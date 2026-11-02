"""``_class_info_for_type``：带 ``::`` 的模板实参不误伤类名解析。"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

from src.analysis.import_resolver import discover_translation_modules
from src.analysis.ir import cpp_fill_allocator_default_args
from src.passes.mixins import expand_mixins
from src.translator import Translator


class ClassInfoForTypeTests(unittest.TestCase):
  def _translator_with_list(self) -> Translator:
    path = Path("test/util/test_list.py").resolve()
    runtime_root = Path("py2cpp").resolve()
    project_root = path.parent.parent.parent
    modules = discover_translation_modules(
      path,
      include_stdlib=True,
      runtime_root=runtime_root,
      project_root=project_root,
    )
    tr = Translator("test_list", str(path))
    tr._import_project_root_cache = project_root
    tr._parse_modules(modules)
    expand_mixins(tr)
    return tr

  def test_pylist_with_default_allocator_resolves_list(self):
    tr = self._translator_with_list()
    cpp = cpp_fill_allocator_default_args("PyList<PyInt>")
    info = tr._class_info_for_type(cpp)
    self.assertIsNotNone(info)
    assert info is not None
    self.assertEqual(info.name, "list")

  def test_template_args_match_cpp_name(self):
    import ast

    from src.analysis.ir import ClassInfo, class_info_for_cpp_type, clear_class_cpp_index

    node = ast.parse("class list: pass").body[0]
    info = ClassInfo(node, "py2cpp/util/list")
    info.cpp_rename = "PyList"
    classes = {"list": info}
    clear_class_cpp_index()
    self.assertIs(class_info_for_cpp_type("PyList<PyInt>", classes), info)
    self.assertIs(class_info_for_cpp_type("PyList", classes), info)
    self.assertIsNone(class_info_for_cpp_type("PySet<PyInt>", classes))

  def test_pyset_still_resolves(self):
    tr = self._translator_with_list()
    info = tr._class_info_for_type("PySet<PyInt>")
    self.assertIsNotNone(info)
    assert info is not None
    self.assertEqual(info.name, "set")


if __name__ == "__main__":
  unittest.main()
