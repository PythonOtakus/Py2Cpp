"""``@dataclass`` / ``record`` 合成方法须回写 ``module_mids``（MidClass.methods）。"""
from __future__ import annotations

from compiler.py.frontend.lexer import Lexer
from compiler.py.frontend.parser import parse_tokens
from compiler.py.frontend.source import FileId
from compiler.py.mid.mutate import find_mid_class
from compiler.py.mid.nodes import MidClass, MidFunction
from compiler.py.passes.apply_mid_decls import (
  apply_mid_class_flags,
  register_module_from_mid,
)
from compiler.py.sema.bind import bind_module, lower_to_mid
from host.passes.dataclass_expand import expand_dataclass
from host.translator import Translator


def _mid_from_src(src: str, path: str = "m"):
  return lower_to_mid(
    bind_module(parse_tokens(Lexer(src, FileId(0)).tokenize(), src), path=path)
  )


def test_dataclass_registers_init_on_mid_class():
  src = (
    "record Point:\n"
    "  x: int = 0\n"
    "  y: int = 1\n"
  )
  mid = _mid_from_src(src)
  classes = {it.name: it for it in mid.items if isinstance(it, MidClass)}
  assert "Point" in classes
  assert classes["Point"].is_record
  assert all(m.name != "__init__" for m in classes["Point"].methods)

  tr = Translator("m", "m.paw")
  tr.module_mids = {"m": mid}
  register_module_from_mid(tr, mid, "m")
  apply_mid_class_flags(tr, mid)
  expand_dataclass(tr)

  info = tr.classes["Point"]
  assert info.is_dataclass
  assert info.inits
  assert info.inits[0].name == "__init__"

  mid_after = tr.module_mids["m"]
  mid_cls = find_mid_class(mid_after, "Point")
  assert mid_cls is not None
  by_name = {m.name: m for m in mid_cls.methods}
  assert "__init__" in by_name
  init = by_name["__init__"]
  assert isinstance(init, MidFunction) and not init.is_static
  assert init.body or init.body_source
  assert "__eq__" in by_name
  assert "__repr__" in by_name
