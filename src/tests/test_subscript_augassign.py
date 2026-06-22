"""映射 / 容器下标增强赋值 → ``__setitem__`` + ``__getitem__``。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class SubscriptAugassignTests(unittest.TestCase):
  def _translate(self, src: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _h, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      return cpp_path.read_text(encoding="utf-8")

  def test_dict_subscript_iadd(self):
    cpp = self._translate(
      '''
from py2cpp.util.dict import dict

def f(d: dict[str, int], k: str, v: int) -> None:
  d[k] += v
'''
    )
    self.assertIn("d.__setitem__(k, (d.__getitem__(k) + v)", cpp)

  def test_self_dict_field_subscript_iadd(self):
    cpp = self._translate(
      '''
from py2cpp.util.dict import dict

class Box:
  data: dict[str, int]

  def bump(self, k: str, v: int) -> None:
    self.data[k] += v
'''
    )
    self.assertIn("this->data.__setitem__(k, (this->data.__getitem__(k) + v)", cpp)


if __name__ == "__main__":
  unittest.main()
