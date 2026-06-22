"""``@dataclass``：``new(...)`` 默认在非容器注解上进入 ``__init__`` 形参。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class DataclassMakeInitParamTests(unittest.TestCase):
  def _translate(self, extra: str) -> str:
    src = f"""
from py2cpp import dataclass, new, optional

@dataclass
class Inner:
  v: int = 0

{extra}
"""
    with tempfile.TemporaryDirectory() as tmp:
      py = Path(tmp) / "mod.py"
      py.write_text(src, encoding="utf-8")
      out = Path(tmp) / "out"
      h_path, _cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=True,
      )
      return h_path.read_text(encoding="utf-8")

  def test_nested_new_default_in_ctor(self):
    h = self._translate(
      """
@dataclass
class Outer:
  inner: Inner = new()
""",
    )
    self.assertRegex(h, r"Outer\(Inner& inner = Inner\(\)\)")

  def test_list_new_stays_body_init(self):
    h = self._translate(
      """
@dataclass
class WithList:
  items: list[int] @optional = new()
""",
    )
    self.assertRegex(h, r"WithList\(\)")
    self.assertNotIn("items =", h.split("WithList(")[1].split(")")[0])

  def test_list_literal_stays_body_init(self):
    h = self._translate(
      """
@dataclass
class WithList:
  items: list[int] @optional = []
""",
    )
    self.assertRegex(h, r"WithList\(\)")

  def test_new_args_default_in_ctor(self):
    h = self._translate(
      """
@dataclass
class Outer:
  inner: Inner = new(7)
""",
    )
    self.assertRegex(h, r"Outer\(Inner& inner = Inner\(7\)\)")

  def test_new_kwargs_default_in_ctor(self):
    h = self._translate(
      """
@dataclass
class Outer:
  inner: Inner = new(v=7)
""",
    )
    self.assertRegex(h, r"Outer\(Inner& inner = Inner\(7\)\)")


if __name__ == "__main__":
  unittest.main()
