"""单模块 stdlib 翻译：``.inl`` 实现勿重复 emit。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class StdlibSingleModuleInlTests(unittest.TestCase):
  def test_flow_model_inl_no_duplicate_copy(self):
    repo = Path(__file__).resolve().parents[2]
    model_py = repo / "py2cpp" / "ui" / "flow" / "model.py"
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      Translator.translate_file(
        str(model_py),
        output_dir=str(out),
        include_stdlib=False,
        emit_main=False,
      )
      inl = out / "runtime" / "py2cpp" / "ui" / "flow" / "model.inl"
      self.assertTrue(inl.is_file(), f"missing {inl}")
      text = inl.read_text(encoding="utf-8")
      self.assertEqual(text.count("FlowGraph::__copy__"), 1)
      self.assertNotIn("PyList<PyTuple<FlowNode, 0>>", text)


if __name__ == "__main__":
  unittest.main()
