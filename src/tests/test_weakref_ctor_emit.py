"""``WeakRef[T](obj)`` 构造与字段存储一致：内层 ``T: refcount`` 使用 unwrap。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class WeakRefCtorEmitTests(unittest.TestCase):
  def test_weakref_subscript_ctor_unwraps_refcount_tparam(self):
    src = """
from py2cpp import *

@refcount
class Node:
  pass

class Bag[T: refcount]:
  _refs: list[WeakRef[T]] = []

  def append(self, obj: T) -> None:
    self._refs.append(WeakRef[T](obj))
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=True, strict=False,
      )
      text = cpp_path.read_text(encoding="utf-8")
      inl = cpp_path.with_suffix(".inl")
      if inl.is_file():
        text += inl.read_text(encoding="utf-8")
      compact = text.replace(" ", "").replace("\n", "")
      self.assertIn(
        "PyWeakRef<typenamepy2cpp_refcount_unwrap<T>::type>(obj)",
        compact,
      )
      self.assertNotIn("PyWeakRef<T>(obj)", compact)


if __name__ == "__main__":
  unittest.main()
