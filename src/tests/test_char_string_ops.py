"""``PyChar`` 与 ``int``/``float`` 同级的 ``str`` / ``repr`` / ``format`` 降级。"""
from __future__ import annotations

import ast
import unittest

from src.translator import Translator


def _emit_return(body: str, *, entry: str = "mod") -> str:
  mod_src = f"from py2cpp import char\n\ndef probe():\n{body}"
  tree = ast.parse(mod_src)
  func = tree.body[1]
  assert isinstance(func, ast.FunctionDef)
  ret = func.body[-1]
  assert isinstance(ret, ast.Return) and ret.value is not None
  tr = Translator(entry, f"{entry}.py")
  tr.entry_module_path = entry
  tr._parse_modules([(entry, mod_src)])
  return tr.visit(ret.value)


class CharStringEmitTests(unittest.TestCase):
  def test_str_char_uses_pystr_ctor(self):
    out = _emit_return("  c: char = 65\n  return str(c)\n")
    self.assertIn("PyStr(c)", out.replace(" ", ""))

  def test_repr_char_uses_global_repr(self):
    out = _emit_return("  c: char = 65\n  return repr(c)\n")
    self.assertIn("::repr(c)", out)

  def test_format_char_uses_global_format(self):
    out = _emit_return("  c: char = 65\n  return format(c)\n")
    self.assertIn("::format(c", out)

  def test_str_add_char_in_os_path_inl(self):
    """bootstrap 后 ``os/path.inl`` 中 ``str + char`` 应经 ``PyStr(码点)`` 而非 ``chbuf`` 临时数组。"""
    from pathlib import Path

    inl = Path("generated/runtime/py2cpp/io/file/path.inl").read_text(encoding="utf-8")
    self.assertNotIn("chbuf", inl)
    self.assertIn("__add__(PyStr(", inl.replace(" ", ""))


if __name__ == "__main__":
  unittest.main()
