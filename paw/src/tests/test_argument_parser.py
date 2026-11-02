"""``expand_argument_parser``：``*ArgMeta`` 校验与 ``parse[T]`` 负向。"""
from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path

from src.translator import Translator
from src.translation_error import TranslationError


_PREAMBLE = """
from py2cpp import *
from py2cpp.console.parse import ArgumentParserMixin, FlagArgMeta, OptArgMeta, PosArgMeta
"""


class ArgumentParserPassTests(unittest.TestCase):
  def _translate(self, extra: str, *, include_stdlib: bool = True) -> str:
    src = _PREAMBLE + extra
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(textwrap.dedent(src), encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py),
        output_dir=str(out / "gen"),
        include_stdlib=include_stdlib,
      )
      return cpp_path.read_text(encoding="utf-8")

  def test_host_parse_from_mixin(self):
    cpp = self._translate(
      """
@dataclass
class BuildArgs(ArgumentParserMixin):
  source: str @PosArgMeta()
  jobs: int @OptArgMeta() = 1

def probe(argv: list[str]) -> BuildArgs:
  return new.parse(argv)
"""
    )
    self.assertIn("BuildArgs::parse", cpp)
    self.assertNotIn("ArgumentParserMixin::parse", cpp)

  def test_mixin_parse_subscript_is_translation_error(self):
    src = _PREAMBLE + """
@dataclass
class BuildArgs(ArgumentParserMixin):
  source: str @PosArgMeta()

def probe(argv: list[str]) -> BuildArgs:
  return ArgumentParserMixin.parse[BuildArgs](argv)
"""
    with tempfile.TemporaryDirectory() as tmp:
      py = Path(tmp) / "mod.py"
      py.write_text(textwrap.dedent(src), encoding="utf-8")
      with self.assertRaises(TranslationError) as ctx:
        Translator.translate_file(
          str(py),
          output_dir=str(Path(tmp) / "gen"),
          include_stdlib=True,
        )
      self.assertIn("勿 ArgumentParserMixin.parse[T]", str(ctx.exception))

  def test_missing_mixin_is_translation_error(self):
    src = _PREAMBLE + """
@dataclass
class Bad:
  source: str @PosArgMeta()
"""
    with tempfile.TemporaryDirectory() as tmp:
      py = Path(tmp) / "mod.py"
      py.write_text(textwrap.dedent(src), encoding="utf-8")
      with self.assertRaises(TranslationError) as ctx:
        Translator.translate_file(
          str(py),
          output_dir=str(Path(tmp) / "gen"),
          include_stdlib=True,
        )
      self.assertIn("须继承 ArgumentParserMixin", str(ctx.exception))

  def test_flag_on_non_bool_is_translation_error(self):
    src = _PREAMBLE + """
@dataclass
class Bad:
  n: int @FlagArgMeta() = 0
"""
    with tempfile.TemporaryDirectory() as tmp:
      py = Path(tmp) / "mod.py"
      py.write_text(textwrap.dedent(src), encoding="utf-8")
      with self.assertRaises(TranslationError) as ctx:
        Translator.translate_file(
          str(py),
          output_dir=str(Path(tmp) / "gen"),
          include_stdlib=True,
        )
      self.assertIn("FlagArgMeta 仅允许 bool", str(ctx.exception))

  def test_opt_on_bool_is_translation_error(self):
    src = _PREAMBLE + """
@dataclass
class Bad:
  flag: bool @OptArgMeta() = False
"""
    with tempfile.TemporaryDirectory() as tmp:
      py = Path(tmp) / "mod.py"
      py.write_text(textwrap.dedent(src), encoding="utf-8")
      with self.assertRaises(TranslationError) as ctx:
        Translator.translate_file(
          str(py),
          output_dir=str(Path(tmp) / "gen"),
          include_stdlib=True,
        )
      self.assertIn("OptArgMeta 不能标在 bool", str(ctx.exception))


if __name__ == "__main__":
  unittest.main()
