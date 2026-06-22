"""``Json`` 类静态 ``@overload`` → ``Json::dumps`` / ``Json::dump`` C++ 重载。"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class JsonClassSerializeOverloadTest(unittest.TestCase):
  @staticmethod
  def _root() -> Path:
    return Path(__file__).resolve().parents[2]

  def test_json_header_emits_class_static_overloads(self) -> None:
    root = self._root()
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      subprocess.run(
        [sys.executable, "main.py", "py2cpp/__init__.py", "-o", str(out), "--no-main"],
        cwd=root,
        check=True,
      )
      header = out / "runtime" / "py2cpp" / "serde" / "json.h"
      text = header.read_text(encoding="utf-8")
      self.assertIn("static PyStr dumps(PyBool obj, PyInt indent = 0);", text)
      self.assertIn(
        "static PyStr dumps(const PyList<PyInt>& obj, PyInt indent = 0);",
        text,
      )
      self.assertIn(
        "static void dump(PyBool obj, PyStringIO& fp, PyInt indent = 0);",
        text,
      )
      self.assertIn(
        "static void dump(PyBool obj, PyTextIOWrapper& fp, PyInt indent = 0);",
        text,
      )
      self.assertNotIn("_json_dumps(", text)
      self.assertNotIn("_json_dump(", text)

  def test_json_calls_use_json_class_methods(self) -> None:
    root = self._root()
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      subprocess.run(
        [
          sys.executable,
          "main.py",
          "test/serde/test_json.py",
          "-o",
          str(out),
          "--no-main",
        ],
        cwd=root,
        check=True,
      )
      cpp = out / "test" / "stdlib" / "serde" / "test_json.cpp"
      text = cpp.read_text(encoding="utf-8")
      self.assertIn("Json::dumps(", text)
      self.assertIn("Json::dump(", text)
      self.assertNotIn("_json_dumps(", text)
      self.assertNotIn("_json_dump(", text)


if __name__ == "__main__":
  unittest.main()
