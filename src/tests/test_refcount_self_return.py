"""``@refcount`` 类方法 ``-> Self`` / 形参 ``Self`` 均生成 ``PyRefCount<T>``。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class RefcountSelfReturnTests(unittest.TestCase):
  def test_self_return_and_param_use_pyrefcount(self):
    src = """
from py2cpp import *

@refcount
class Node:
  def child_at(self, index: int) -> Self:
    raise RuntimeError()

  def take(self, other: Self) -> None:
    pass

  def find(self, name: str) -> Self | None:
    return None

def main():
  pass
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py),
        output_dir=str(out),
        include_stdlib=False,
        strict=False,
      )
      h = cpp_path.with_suffix(".h").read_text(encoding="utf-8")
      self.assertIn("PyRefCount<Node> child_at(PyInt index);", h)
      self.assertIn("void take(PyRefCount<Node> other);", h)
      self.assertIn("PyRefCount<Node> find(PyStr name);", h)
      self.assertNotIn("\n    Node child_at(", h)


if __name__ == "__main__":
  unittest.main()
