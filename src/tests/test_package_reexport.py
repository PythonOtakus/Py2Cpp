"""包 ``__init__`` 再导出 + ``from m import x as y`` 须绑到定义模块。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.analysis.imports import _package_reexport_source, _resolve_symbol
from src.translator import Translator


class PackageReexportTests(unittest.TestCase):
  def test_from_import_as_emits_defining_call_not_alias(self) -> None:
    """``from .fs import mkdir as fs_mkdir`` 调用须发射 ``mkdir``，不得留下 Python 别名。"""
    src_fs = "def mkdir(n: int) -> None:\n  return\n"
    src_path = (
      "from .fs import mkdir as fs_mkdir\n"
      "\n"
      "class Path:\n"
      "  def mkdir(self, n: int) -> None:\n"
      "    fs_mkdir(n)\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
      root = Path(tmp)
      (root / "fs.py").write_text(src_fs, encoding="utf-8")
      user = root / "path.py"
      user.write_text(src_path, encoding="utf-8")
      out = root / "out"
      _, cpp_path = Translator.translate_file(
        str(user), output_dir=str(out), include_stdlib=False, strict=False,
      )
      cpp = cpp_path.read_text(encoding="utf-8")
      compact = cpp.replace(" ", "")
      self.assertNotIn("fs_mkdir(", cpp)
      self.assertIn("mkdir(n)", compact)


if __name__ == "__main__":
  unittest.main()
