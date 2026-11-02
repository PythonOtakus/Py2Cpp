"""``def f[*Ts](*args: Ts)`` 译器：签名、递归 peel、调用展开、非法注解。"""
from __future__ import annotations

import ast
import re
import tempfile
import unittest
from pathlib import Path

from src.translation_error import TranslationError
from src.translator import Translator


class VariadicTemplateEmitTests(unittest.TestCase):
  def _translate(self, extra: str, *, entry_body: str = "") -> str:
    src = f"""
def sum_all[*Ts](*args: Ts) -> int:
  total: int = 0
  for x in args:
    total += x
  return total

def main():
{entry_body or "    pass\n"}
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src + extra, encoding="utf-8")
      _h, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=True,
      )
      text = cpp_path.read_text(encoding="utf-8")
      inl = cpp_path.with_suffix(".inl")
      if inl.is_file():
        text += inl.read_text(encoding="utf-8")
      return text

  def test_signature_template_and_param_pack(self):
    cpp = self._translate("")
    self.assertIn("template<typename... Ts>", cpp)
    self.assertRegex(
      cpp,
      re.compile(
        r"template\s*<\s*typename\.\.\.\s+Ts\s*>\s*"
        r"PyInt\s+sum_all\s*\(\s*Ts\.\.\.\s+args\s*\)",
      ),
    )
    self.assertIn("struct __py2cpp_vt_loop_sum_all_L", cpp)

  def test_for_loop_recursive_peel(self):
    cpp = self._translate("")
    self.assertIn("__py2cpp_vt_loop_sum_all_L", cpp)
    self.assertIn("step(PyInt& total, TsHead head)", cpp)
    self.assertIn("__call__(PyInt& total, TsHead head, TsTail... tail)", cpp)
    self.assertNotIn("static void go(", cpp)

  def test_call_expands_scalars(self):
    cpp = self._translate("", entry_body="    sum_all(1, 2, 3)\n")
    self.assertRegex(cpp, re.compile(r"sum_all\s*\(\s*1\s*,\s*2\s*,\s*3\s*\)"))

  def test_forward_star_args(self):
    src = """
def sum_all[*Ts](*args: Ts) -> int:
  total: int = 0
  for x in args:
    total += x
  return total

def fwd[*Ts](*args: Ts) -> int:
  return sum_all(*args)

def main():
  fwd(1, 2)
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _h, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=True,
      )
      text = cpp_path.read_text(encoding="utf-8")
    self.assertRegex(text, re.compile(r"sum_all\s*\(\s*args\s*\.\.\.\s*\)"))

  def test_unannotated_vararg_defaults_to_pack(self):
    src = """
def pack_len[*Ts](*args) -> int:
  return len(args)

def main():
  pack_len(1, 2)
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _h, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=True,
      )
      text = cpp_path.read_text(encoding="utf-8")
    self.assertIn("template<typename... Ts, typename... __Ts>", text)
    self.assertRegex(text, re.compile(r"pack_len\s*\(\s*__Ts\.\.\.\s+args\s*\)"))
    self.assertIn("sizeof...(args)", text.replace("\n", ""))

  def test_len_rest_param(self):
    src = """
def head[*Ts](first: int, *rest) -> int:
  return first + len(rest)

def main():
  head(1, 2, 3)
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _h, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=True,
      )
      text = cpp_path.read_text(encoding="utf-8")
    self.assertIn("template<typename... Ts, typename... __Ts>", text)
    self.assertIn("sizeof...(rest)", text.replace("\n", ""))

  def test_unannotated_vararg_without_header_tuple(self):
    src = """
def only_args(*args) -> int:
  return len(args)

def main():
  only_args(1)
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _h, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=True,
      )
      text = cpp_path.read_text(encoding="utf-8")
    self.assertIn("template<typename... __Ts>", text)
    self.assertNotIn("template<typename... Ts>", text)
    self.assertRegex(text, re.compile(r"only_args\s*\(\s*__Ts\.\.\.\s+args\s*\)"))

  def test_pack_tuple_ann_assign_and_spread(self):
    src = """
def sum_all[*Ts](*args: Ts) -> int:
  total: int = 0
  for x in args:
    total += x
  return total

def via[*Ts](*args: Ts) -> int:
  t: (*Ts,) = args
  return sum_all(*t)

def main():
  via(1, 2)
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _h, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=True,
      )
      text = cpp_path.read_text(encoding="utf-8")
    self.assertIn("PyTuple<Ts...> t(args...);", text.replace("\n", ""))
    self.assertRegex(text, re.compile(r"sum_all\s*\(\s*args\s*\.\.\.\s*\)"))

  def test_class_method_pack_tuple(self):
    src = """
def sum_all[*Ts](*args: Ts) -> int:
  total: int = 0
  for x in args:
    total += x
  return total

class Box[*Ts]:
  def fwd(self, *args: Ts) -> int:
    t: (*Ts,) = args
    return sum_all(*t)

def main():
  pass
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _h, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=True,
      )
      text = cpp_path.read_text(encoding="utf-8")
      inl = cpp_path.with_suffix(".inl")
      if inl.is_file():
        text += inl.read_text(encoding="utf-8")
    self.assertIn("PyTuple<Ts...> t(args...);", text.replace("\n", ""))

  def test_tuple_subscript_pack_type(self):
    from src.analysis.analyzer import TypeParser

    parser = TypeParser()
    ann = ast.parse("tuple[*Ts]", mode="eval").body
    cpp = parser.parse_type(ann, {"Ts"}, typevar_tuple_names=frozenset({"Ts"}))
    self.assertEqual(cpp, "PyTuple<Ts...>")

  def test_rejects_star_on_tuple_annotation(self):
    src = """
def bad[*Ts](*args: *Ts) -> int:
  return 0

def main():
  pass
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      with self.assertRaises(TranslationError):
        Translator.translate_file(str(py), output_dir=str(out), include_stdlib=True)


if __name__ == "__main__":
  unittest.main()
