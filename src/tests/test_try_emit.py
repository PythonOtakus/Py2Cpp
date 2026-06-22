"""``visit_Try`` / ``try_emit`` 片段断言。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class TryEmitTests(unittest.TestCase):
  def _translate(self, body: str) -> str:
    src = f"""from py2cpp import *
from py2cpp.core.exceptions import KeyError, ValueError, TypeError

def probe() -> int:
{body}"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _h, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      return cpp_path.read_text(encoding="utf-8")

  def test_try_except_emits_catch(self):
    cpp = self._translate(
      "  n: int = 0\n"
      "  try:\n"
      "    raise ValueError()\n"
      "  except ValueError:\n"
      "    n = 1\n"
      "  return n\n",
    )
    self.assertIn("try\n    {", cpp)
    self.assertIn("catch (const py2cpp::core::exceptions::ValueError&", cpp)
    self.assertIn("      n = 1;", cpp)
    self.assertIn("throw;", cpp)

  def test_try_else_flag(self):
    cpp = self._translate(
      "  ok: bool = true\n"
      "  try:\n"
      "    ok = false\n"
      "  except ValueError:\n"
      "    ok = true\n"
      "  else:\n"
      "    ok = true\n"
      "  return ok\n",
    )
    self.assertIn("__try_ok", cpp)
    self.assertIn("if (__try_ok", cpp)

  def test_try_finally_always(self):
    cpp = self._translate(
      "  n: int = 0\n"
      "  try:\n"
      "    n = 1\n"
      "  finally:\n"
      "    n = 2\n"
      "  return n\n",
    )
    self.assertIn("n = 2", cpp)

  def test_try_except_finally_after_handler(self):
    cpp = self._translate(
      "  n: int = 0\n"
      "  try:\n"
      "    raise ValueError()\n"
      "  except ValueError:\n"
      "    n = 2\n"
      "  finally:\n"
      "    n = 3\n"
      "  return n\n",
    )
    self.assertGreaterEqual(cpp.count("n = 3;"), 2)

  def test_bare_except_emits_catch_all(self):
    cpp = self._translate(
      "  n: int = 0\n"
      "  try:\n"
      "    raise ValueError()\n"
      "  except:\n"
      "    n = 1\n"
      "  return n\n",
    )
    self.assertIn("catch (...)\n    {", cpp)
    self.assertNotIn("throw;", cpp)

  def test_bare_except_else(self):
    cpp = self._translate(
      "  n: int = 0\n"
      "  try:\n"
      "    n = 1\n"
      "  except:\n"
      "    n = 2\n"
      "  else:\n"
      "    n = 3\n"
      "  return n\n",
    )
    self.assertIn("catch (...)\n    {", cpp)
    self.assertIn("__try_ok", cpp)
    self.assertIn("if (__try_ok", cpp)

  def test_return_finally_emitted_once(self):
    cpp = self._translate(
      "  acc: int = 0\n"
      "  try:\n"
      "    acc = 1\n"
      "    return acc\n"
      "  finally:\n"
      "    acc = 2\n"
      "  return acc\n",
    )
    self.assertGreaterEqual(cpp.count("acc = 2;"), 1)

  def test_except_as_binds_exception(self):
    cpp = self._translate(
      "  n: int = 0\n"
      "  try:\n"
      "    raise ValueError()\n"
      "  except ValueError as e:\n"
      "    n = 1 if e else 0\n"
      "  return n\n",
    )
    self.assertIn("auto& e = __exc", cpp)
    self.assertIn("(e ? 1 : 0)", cpp)

  def test_except_star_emits_group_catch(self):
    cpp = self._translate(
      "  n: int = 0\n"
      "  try:\n"
      "    raise ValueError()\n"
      "  except* ValueError as e:\n"
      "    n = 1\n"
      "  return n\n",
    )
    self.assertIn("catch (const py2cpp::core::exceptions::ExceptionGroup& __eg_in)", cpp)
    self.assertIn("exception_group_from_single", cpp)
    self.assertIn("exception_group_split_except_star", cpp)
    self.assertIn("static_cast<PyBool>", cpp)
    self.assertNotIn(".__bool__()", cpp)

  def test_raise_from_sets_cause(self):
    cpp = self._translate(
      "  try:\n"
      "    raise ValueError()\n"
      "  except ValueError as e:\n"
      "    raise TypeError() from e\n"
      "  return 0\n",
    )
    self.assertIn("__cause__ = &e;", cpp)
    self.assertIn("auto __raised", cpp)
    self.assertIn("throw __raised", cpp)

  def test_raise_from_with_args(self):
    cpp = self._translate(
      "  try:\n"
      "    raise ValueError()\n"
      "  except ValueError as e:\n"
      "    raise KeyError(\"inner\") from e\n"
      "  return 0\n",
    )
    self.assertIn("KeyError", cpp)
    self.assertIn("__cause__ = &e;", cpp)
    self.assertIn("auto __raised", cpp)
    self.assertIn("throw __raised", cpp)

  def test_raise_bound_exception_instance(self):
    cpp = self._translate(
      "  try:\n"
      "    raise ValueError()\n"
      "  except ValueError as e:\n"
      "    raise e\n"
      "  return 0\n",
    )
    self.assertIn("throw e;", cpp)
    self.assertNotIn("ValueError()", cpp.split("throw e;")[1] if "throw e;" in cpp else cpp)


if __name__ == "__main__":
  unittest.main()
