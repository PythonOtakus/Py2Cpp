"""``Type.build("…")`` 译期内联。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class BuildInlineCppTests(unittest.TestCase):
  def _translate(self, src: str) -> tuple[str, str]:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      h_path, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      return h_path.read_text(encoding="utf-8"), cpp_path.read_text(encoding="utf-8")

  def test_build_no_cpp_method(self):
    src = '''
from py2cpp import dataclass

@dataclass
class Team:
  name: str

@dataclass
class Org:
  teams: list[Team]

def use():
  org: Org = Org.build('teams[:1] > name="alpha"')
'''
    h, cpp = self._translate(src)
    self.assertNotIn("void build(", h)
    self.assertNotIn(" build(", h)
    self.assertIn(".append(", cpp)

  def test_index_bind_loop(self):
    src = '''
from py2cpp import dataclass

@dataclass
class Team:
  name: str
  min_score: int

@dataclass
class Org:
  teams: list[Team]

def use():
  prefix: str = "t"
  org: Org = Org.build(
    "teams[:3]: $i > name={prefix + str($i)}, min_score=$i"
  )
'''
    _, cpp = self._translate(src)
    self.assertIn("for (int i = 0; i < 3; ++i)", cpp)
    self.assertIn(".append(", cpp)

  def test_list_root_build(self):
    src = '''
from py2cpp import dataclass

@dataclass
class Team:
  name: str

def use():
  teams: list[Team] = list[Team].build("[:2]: $i > name={str($i)}")
'''
    _, cpp = self._translate(src)
    self.assertIn("for (int i = 0; i < 2; ++i)", cpp)
    self.assertIn("PyList<Team>", cpp)

  def test_repeat_template(self):
    src = '''
from py2cpp import dataclass

@dataclass
class Member:
  score: int
  name: str

@dataclass
class Team:
  members: list[Member]

def use():
  t: Team = Team.build('members[:2] > score=10,name="amy"')
'''
    _, cpp = self._translate(src)
    self.assertIn("for (int", cpp)
    self.assertIn("< 2; ++", cpp)


if __name__ == "__main__":
  unittest.main()
