"""``obj.select("…")`` 译期内联；返回类型由后处理推断。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.passes.selector_parse import SliceStep, parse_selector_path
from src.translator import Translator


class SelectInlineCppTests(unittest.TestCase):
  def _translate(self, src: str) -> tuple[str, str]:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      h_path, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      return h_path.read_text(encoding="utf-8"), cpp_path.read_text(encoding="utf-8")

  def test_select_no_cpp_method(self):
    src = '''
from py2cpp import dataclass

@dataclass
class Team:
  name: str

@dataclass
class Org:
  teams: list[Team]

def use(org: Org):
  names: list[str] = org.select(".teams[0].name")
'''
    h, cpp = self._translate(src)
    self.assertNotIn("void select(", h)
    self.assertNotIn(" select(", h)
    self.assertIn("__getitem__(0)", cpp)
    self.assertIn(".append(", cpp)

  def test_filter_emits_loop(self):
    src = '''
from py2cpp import dataclass

@dataclass
class Member:
  score: int

@dataclass
class Team:
  members: list[Member]

def use(t: Team):
  out: list[Member] = t.select(".members{.score > 0}")
'''
    _, cpp = self._translate(src)
    self.assertIn(".append(", cpp)
    self.assertIn(".score > 0", cpp)

  def test_projection_emits_multi_append(self):
    src = '''
from py2cpp import dataclass

@dataclass
class Leaf:
  d: str

@dataclass
class NodeB:
  b: Leaf

@dataclass
class Mid:
  a: NodeB
  c: Leaf

@dataclass
class Root:
  f: Mid

def use(r: Root):
  out: list[str] = r.select(".f.(a.b, c).d")
'''
    _, cpp = self._translate(src)
    self.assertEqual(cpp.count(".append("), 2)

  def test_multi_bracket_emits(self):
    src = '''
from py2cpp import dataclass

@dataclass
class Member:
  score: int

@dataclass
class Team:
  members: list[Member]

def use(t: Team):
  out: list[Member] = t.select(".members[0, 1]")
'''
    _, cpp = self._translate(src)
    self.assertIn("__getitem__(0)", cpp)
    self.assertIn("__getitem__(1)", cpp)

  def test_filter_local_binding_emits(self):
    src = '''
from py2cpp import dataclass

@dataclass
class Member:
  score: int

@dataclass
class Team:
  members: list[Member]

def use(t: Team, threshold: int):
  out: list[Member] = t.select(".members{.score > threshold}")
'''
    _, cpp = self._translate(src)
    self.assertIn(".score > threshold", cpp)

  def test_wildcard_slice_emits(self):
    src = '''
from py2cpp import dataclass

@dataclass
class Team:
  name: str

@dataclass
class Org:
  teams: list[Team]

def use(o: Org):
  names: list[str] = o.select(".teams[:].name")
'''
    _, cpp = self._translate(src)
    self.assertIn(".append(", cpp)
    self.assertIn(".name", cpp)

  def test_open_lo_slice_emits(self):
    src = '''
from py2cpp import dataclass

@dataclass
class Member:
  score: int

@dataclass
class Team:
  members: list[Member]

def use(t: Team):
  out: list[Member] = t.select(".members[2:]")
'''
    _, cpp = self._translate(src)
    self.assertIn("for (int", cpp)
    self.assertIn("= 2;", cpp)

  def test_slice_step_emits(self):
    src = '''
from py2cpp import dataclass

@dataclass
class Member:
  score: int

@dataclass
class Team:
  members: list[Member]

def use(t: Team):
  out: list[Member] = t.select(".members[1:4:2]")
'''
    _, cpp = self._translate(src)
    self.assertIn("= 1;", cpp)
    self.assertIn("< 4;", cpp)
    self.assertIn("+= 2)", cpp)

  def test_descendant_emits(self):
    src = '''
from py2cpp import dataclass

@dataclass
class Team:
  name: str

@dataclass
class Org:
  teams: list[Team]

def use(o: Org):
  names: list[str] = o.select(".teams..name")
'''
    _, cpp = self._translate(src)
    self.assertGreaterEqual(cpp.count(".append("), 1)

  def test_multi_index_names_emits(self):
    src = '''
from py2cpp import dataclass

@dataclass
class Team:
  name: str

@dataclass
class Org:
  teams: list[Team]

def use(o: Org):
  names: list[str] = o.select(".teams[0, 1].name")
'''
    _, cpp = self._translate(src)
    self.assertGreaterEqual(cpp.count(".append("), 2)

  def test_str_index_emits(self):
    src = '''
from py2cpp import dataclass

@dataclass
class Bag:
  data: dict[str, int]

def use(b: Bag):
  out: list[int] = b.select(".data['x']")
'''
    _, cpp = self._translate(src)
    self.assertIn('__getitem__(PyStr("x"))', cpp.replace(" ", ""))

  def test_multi_str_index_emits(self):
    src = '''
from py2cpp import dataclass

@dataclass
class Bag:
  data: dict[str, int]

def use(b: Bag):
  out: list[int] = b.select(".data['u', 'v']")
'''
    _, cpp = self._translate(src)
    self.assertIn('PyStr("u")', cpp)
    self.assertIn('PyStr("v")', cpp)
    self.assertGreaterEqual(cpp.count(".append("), 2)

  def test_optional_index_emits_guard(self):
    src = '''
from py2cpp import dataclass

@dataclass
class Team:
  name: str

@dataclass
class Org:
  teams: list[Team]

def use(o: Org):
  out: list[str] = o.select(".teams?[0].name")
'''
    _, cpp = self._translate(src)
    self.assertIn("if (", cpp)
    self.assertIn("__len__()", cpp)

  def test_optional_dict_key_emits_guard(self):
    src = '''
from py2cpp import dataclass

@dataclass
class Bag:
  data: dict[str, int]

def use(b: Bag):
  out: list[int] = b.select(".data?['x']")
'''
    _, cpp = self._translate(src)
    self.assertIn("__contains__", cpp)

  def test_bind_ref_emits(self):
    src = '''
from py2cpp import dataclass

@dataclass
class Team:
  name: str

@dataclass
class Org:
  teams: list[Team]

def use(o: Org):
  names: list[str] = o.select(".teams[0]:$t; $t.name")
'''
    _, cpp = self._translate(src)
    self.assertIn("sel_t", cpp)
    self.assertIn(".name", cpp)

  def test_filter_bind_ref_emits(self):
    src = '''
from py2cpp import dataclass

@dataclass
class Member:
  score: int
  name: str

@dataclass
class Team:
  min_score: int
  members: list[Member]

@dataclass
class Org:
  teams: list[Team]

def use(o: Org):
  out: list[str] = o.select(".teams[0]:$t.members{.score > $t.min_score}.name")
'''
    _, cpp = self._translate(src)
    self.assertIn("sel_t", cpp)
    self.assertIn(".min_score", cpp)
    self.assertIn(".score >", cpp)


class SelectorParsePlanTests(unittest.TestCase):
  def test_open_hi_slice(self):
    plan = parse_selector_path(".items[:2]")
    sl = plan.steps[1]
    self.assertIsInstance(sl, SliceStep)
    self.assertIsNone(sl.lo)
    self.assertEqual(sl.hi, 2)
    self.assertIsNone(sl.step)

  def test_open_lo_slice(self):
    plan = parse_selector_path(".items[2:]")
    sl = plan.steps[1]
    self.assertIsInstance(sl, SliceStep)
    self.assertEqual(sl.lo, 2)
    self.assertIsNone(sl.hi)
    self.assertIsNone(sl.step)

  def test_full_wildcard_slice(self):
    plan = parse_selector_path(".items[:]")
    sl = plan.steps[1]
    self.assertIsInstance(sl, SliceStep)
    self.assertIsNone(sl.lo)
    self.assertIsNone(sl.hi)
    self.assertIsNone(sl.step)

  def test_slice_step_only(self):
    plan = parse_selector_path(".items[::2]")
    sl = plan.steps[1]
    self.assertEqual((sl.lo, sl.hi, sl.step), (None, None, 2))


class SelectPostEmitTests(unittest.TestCase):
  def _translate(self, src: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=False,
      )
      return cpp_path.read_text(encoding="utf-8")

  def test_sort_emits_insertion(self):
    src = '''
from py2cpp import dataclass

@dataclass
class Member:
  score: int
  name: str

@dataclass
class Team:
  members: list[Member]

def use(t: Team):
  out: list[Member] = t.select(".members@sort(-.score, .name)")
'''
    cpp = self._translate(src)
    self.assertIn("sel_before", cpp)
    self.assertIn("sel_out", cpp)

  def test_sort_parent_bind_key_emits(self):
    src = '''
from py2cpp import dataclass

@dataclass
class Member:
  score: int
  name: str

@dataclass
class Team:
  name: str
  members: list[Member]

@dataclass
class Org:
  teams: list[Team]

def use(o: Org):
  out: list[Member] = o.select(
    ".teams[0]:$t; $t.members@sort($t.name, .name)",
  )
'''
    cpp = self._translate(src)
    self.assertIn("sel_t", cpp)
    self.assertIn("sel_before", cpp)

  def test_sort_expr_binop_emits(self):
    src = '''
from py2cpp import dataclass

@dataclass
class Member:
  score: int
  name: str

@dataclass
class Team:
  min_score: int = 0
  members: list[Member] = []

@dataclass
class Org:
  teams: list[Team] = []

def use(o: Org):
  out: list[Member] = o.select(
    ".teams[0]:$t; $t.members@sort(.score - $t.min_score)",
  )
'''
    cpp = self._translate(src)
    self.assertIn("sel_before", cpp)
    self.assertIn("-", cpp)

  def test_count_emits_len(self):
    src = '''
from py2cpp import dataclass

@dataclass
class Team:
  name: str

@dataclass
class Org:
  teams: list[Team]

def use(o: Org):
  n: int = o.select(".teams@count")
'''
    cpp = self._translate(src)
    self.assertIn(".__len__()", cpp)

  def test_count_field_emits_counter(self):
    src = '''
from py2cpp import Counter, dataclass

@dataclass
class Member:
  dept: str

@dataclass
class Team:
  members: list[Member]

def use(t: Team):
  freq: Counter[str] = t.select(".members@count(.dept)")
'''
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=True,
      )
      cpp = cpp_path.read_text(encoding="utf-8")
    self.assertIn("Counter<PyStr>", cpp)
    self.assertNotIn("PyDict<PyStr, PyInt>", cpp)

  def test_group_emits_dict(self):
    src = '''
from py2cpp import dataclass

@dataclass
class Member:
  name: str

@dataclass
class Team:
  members: list[Member]

def use(t: Team):
  g: dict[str, list[Member]] = t.select(".members@group(.name)")
'''
    cpp = self._translate(src)
    self.assertIn("sel_grp", cpp)
    self.assertIn(".__contains__", cpp)


if __name__ == "__main__":
  unittest.main()
