"""``@refcount`` + ``@dataclass`` 混入：构造体内 ``self._children = []`` 按字段注解生成空 ``PyList``。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class RefcountDataclassEmptyListTests(unittest.TestCase):
  def test_mixin_dataclass_empty_list_children_init(self):
    src = """
from py2cpp import *

@dataclass(eq=False, repr=False)
@mixin
class NodeMixin:
  name: str = "root"
  _children: list[Self] @optional = []

@refcount
class Node(NodeMixin):
  pass

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
      cpp = cpp_path.read_text(encoding="utf-8")
      self.assertIn("PyList<PyRefCount<Node>, 0>", cpp)
      self.assertIn("this->_children = PyList<PyRefCount<Node>, 0>()", cpp)


if __name__ == "__main__":
  unittest.main()
