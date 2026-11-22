"""``@serializable`` 合成方法须回写 ``module_mids``（MidClass.methods）。"""
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
from host.passes.serializable import expand_serializable
from host.translator import Translator


def _mid_from_src(src: str, path: str = "m"):
  return lower_to_mid(
    bind_module(parse_tokens(Lexer(src, FileId(0)).tokenize(), src), path=path)
  )


def test_serializable_registers_mid_methods():
  src = (
    "@serializable\n"
    "record Point:\n"
    "  x: int = 0\n"
    "  y: int = 1\n"
  )
  mid = _mid_from_src(src)
  assert isinstance(mid, object)
  classes = {it.name: it for it in mid.items if isinstance(it, MidClass)}
  assert "Point" in classes
  assert classes["Point"].is_record

  tr = Translator("m", "m.paw")
  tr.module_mids = {"m": mid}
  register_module_from_mid(tr, mid, "m")
  apply_mid_class_flags(tr, mid)
  expand_dataclass(tr)
  expand_serializable(tr)

  info = tr.classes["Point"]
  assert info.is_serializable
  assert "serialize" in info.methods
  assert "deserialize" in info.methods

  mid_after = tr.module_mids["m"]
  mid_cls = find_mid_class(mid_after, "Point")
  assert mid_cls is not None
  by_name = {m.name: m for m in mid_cls.methods}
  assert "serialize" in by_name
  assert "deserialize" in by_name
  ser = by_name["serialize"]
  des = by_name["deserialize"]
  assert isinstance(ser, MidFunction) and not ser.is_static
  assert isinstance(des, MidFunction) and des.is_static
  assert ser.body or ser.body_source
  assert des.body or des.body_source
