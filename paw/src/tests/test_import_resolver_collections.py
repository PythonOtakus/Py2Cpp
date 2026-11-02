"""``from .util import *`` 须解析为 py2cpp 子包，勿与 stdlib ``util`` 混淆。"""
from __future__ import annotations

import unittest
from pathlib import Path

from src.analysis.import_resolver import (
  ImportRequest,
  discover_import_targets,
  discover_translation_modules,
  resolve_import_target_path,
  resolve_relative_module_path,
)


class ImportResolverCollectionsTests(unittest.TestCase):
  def test_relative_collections_star_resolves(self):
    rt = Path("py2cpp").resolve()
    req = ImportRequest(
      level=1,
      module="util",
      names=(("*", None),),
      is_star=True,
      is_plain_import=False,
    )
    targets = discover_import_targets(
      "py2cpp", req, project_root=Path(".").resolve(), runtime_root=rt,
    )
    self.assertEqual(targets, ["py2cpp/util"])

  def test_relative_helper_in_test_package(self):
    root = Path(".").resolve()
    rt = Path("py2cpp").resolve()
    req = ImportRequest(
      level=1,
      module="helper",
      names=(("get_import_value", None),),
      is_star=False,
      is_plain_import=False,
    )
    target = resolve_import_target_path(
      "test_import",
      req,
      project_root=root / "test" / "import_tests",
      runtime_root=rt,
    )
    self.assertEqual(target, "helper")

  def test_serde_json_level2_vs_level3(self):
    """``serde/json.py`` 锚点为 ``py2cpp/serde``；level=3 不得与 level=2 同解到 ``py2cpp/…``。"""
    rt = Path("py2cpp").resolve()
    imp = "py2cpp/serde/json"
    p2 = resolve_relative_module_path(
      imp, level=2, module="util.memory", runtime_root=rt,
    )
    self.assertEqual(p2, "py2cpp/util/memory")
    with self.assertRaises(ValueError):
      resolve_relative_module_path(
        imp, level=3, module="util.memory", runtime_root=rt,
      )

  def test_io_path_level3_to_py2cpp(self):
    rt = Path("py2cpp").resolve()
    p = resolve_relative_module_path(
      "py2cpp/io/path", level=2, module="text", runtime_root=rt,
    )
    self.assertEqual(p, "py2cpp/text")

  def test_user_subpackage_level2_to_project_root(self):
    """``editor/inspector`` 上 ``from ..command`` → 工程根 ``command``（勿误判越界）。"""
    rt = Path("py2cpp").resolve()
    p = resolve_relative_module_path(
      "editor/inspector",
      level=2,
      module="command",
      runtime_root=rt,
      project_root=Path("zeus/src").resolve(),
    )
    self.assertEqual(p, "command")
    with self.assertRaises(ValueError):
      resolve_relative_module_path(
        "editor/inspector",
        level=3,
        module="command",
        runtime_root=rt,
        project_root=Path("zeus/src").resolve(),
      )

  def test_discover_includes_set_via_py2cpp_star(self):
    mods = discover_translation_modules(
      Path("test/util/test_list.py").resolve(),
      include_stdlib=True,
      runtime_root=Path("py2cpp").resolve(),
      project_root=Path(".").resolve(),
    )
    paths = [mp for mp, _ in mods]
    self.assertIn("py2cpp/util/set", paths)


if __name__ == "__main__":
  unittest.main()
