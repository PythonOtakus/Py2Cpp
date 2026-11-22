"""ClassInfo.from_mid_class：不经 ast.ClassDef / classdef_from_mid 构造。"""
from __future__ import annotations

import host.tree_nodes as ast
from compiler.py.frontend.lexer import Lexer
from compiler.py.frontend.parser import parse_tokens
from compiler.py.frontend.source import FileId
from compiler.py.mid.nodes import MidClass, MidFunction
from compiler.py.passes.apply_mid_decls import register_module_from_mid
from compiler.py.sema.bind import bind_module, lower_to_mid
from host.analysis.ir import ClassInfo
from host.translator import Translator


def _mid_from_src(src: str, path: str = "m"):
  return lower_to_mid(
    bind_module(parse_tokens(Lexer(src, FileId(0)).tokenize(), src), path=path)
  )


def test_from_mid_class_direct_api():
  src = (
    "protocol Drawable:\n"
    "  def draw(self) -> None: ...\n"
    "\n"
    "final native class Spot:\n"
    "  x: int = 0\n"
    "  def ping(self) -> int:\n"
    "    return self.x\n"
  )
  mid = _mid_from_src(src)
  classes = {it.name: it for it in mid.items if isinstance(it, MidClass)}
  assert "Drawable" in classes and classes["Drawable"].is_protocol
  assert "Spot" in classes
  spot_mid = classes["Spot"]
  assert spot_mid.is_final and spot_mid.is_native
  assert any(isinstance(m, MidFunction) and m.name == "ping" for m in spot_mid.methods)

  info = ClassInfo.from_mid_class(spot_mid, "m")
  assert info.mid is spot_mid
  assert info.name == "Spot"
  assert info.is_final and info.is_native
  assert "x" in info.fields
  assert info.field_default_sources.get("x") == "0"
  assert "ping" in info.mid_methods
  assert isinstance(info.mid_methods["ping"], MidFunction)
  # Zero-AST Phase 2：methods 保持空；emit/同步/ensure_* 再桥
  assert info.methods == {}
  assert info.inits == []
  # 占位 node 存在，但非 classdef_from_mid 产物要求
  assert isinstance(info.node, ast.ClassDef)
  assert info.node.name == "Spot"
  info.ensure_methods_bridged_from_mid()
  assert "ping" in info.methods
  assert isinstance(info.methods["ping"], ast.FunctionDef)

  proto = ClassInfo.from_mid_class(classes["Drawable"], "m")
  assert proto.is_protocol
  assert proto.mid is classes["Drawable"]
  assert "draw" in proto.mid_methods


def test_register_module_from_mid_classinfo_has_mid():
  src = (
    "record Point:\n"
    "  x: int = 0\n"
    "  y: int = 1\n"
    "\n"
    "  def sum(self) -> int:\n"
    "    return self.x + self.y\n"
  )
  mid = _mid_from_src(src)
  tr = Translator("m", "m.paw")
  tr.module_mids = {"m": mid}
  n = register_module_from_mid(tr, mid, "m")
  assert n >= 1
  info = tr.classes["Point"]
  assert isinstance(info.mid, MidClass)
  assert info.mid.name == "Point"
  assert "sum" in info.mid_methods
  assert isinstance(info.mid_methods["sum"], MidFunction)
  assert getattr(info, "is_record_from_mid", False)
  # 未要求经过 ClassInfo(ast.ClassDef)：mid 锚点即真源
  assert info.mid_methods["sum"].body_source or info.mid_methods["sum"].body


def test_from_mid_bridges_same_name_overloads():
  """同名 Mid 方法须全部进 method_overloads（勿只留第一个薄转发）。"""
  src = (
    "from paw.core.protocols import GeneratorType\n"
    "\n"
    "class Box:\n"
    "  def xsplit(self, maxSplit: int = 0) -> GeneratorType[str, None, None]:\n"
    "    return self.xsplit('', maxSplit)\n"
    "\n"
    "  def xsplit(self, sep: str, maxSplit: int = 0) -> GeneratorType[str, None, None]:\n"
    "    i: int = 0\n"
    "    yield sep\n"
    "    yield self\n"
  )
  mid = _mid_from_src(src)
  box = next(it for it in mid.items if isinstance(it, MidClass) and it.name == "Box")
  info = ClassInfo.from_mid_class(box, "m")
  info.ensure_methods_bridged_from_mid()
  assert "xsplit" not in info.methods
  overs = info.method_overloads.get("xsplit") or []
  assert len(overs) == 2
  assert any(
    len(m.args.args) == 2 for m in overs
  )  # self, maxSplit
  assert any(
    len(m.args.args) == 3 for m in overs
  )  # self, sep, maxSplit


def test_from_mid_weakref_self_optional_field_ann():
  """``WeakRef[Self] | None`` 字段注解须为 ``BinOp(..., Constant(None))``。"""
  src = (
    "from paw.weak.ref import WeakRef\n"
    "\n"
    "@refcount\n"
    "class Node:\n"
    "  _parent: WeakRef[Self] | None = None\n"
  )
  mid = _mid_from_src(src)
  node = next(it for it in mid.items if isinstance(it, MidClass) and it.name == "Node")
  info = ClassInfo.from_mid_class(node, "m")
  assert "_parent" in info.fields
  from host.analysis.type_emit import field_ann_ast

  ann = field_ann_ast(info, "_parent")
  assert isinstance(ann, ast.BinOp)
  assert isinstance(ann.op, ast.BitOr)
  assert isinstance(ann.right, ast.Constant) and ann.right.value is None
  assert isinstance(ann.left, ast.Subscript)
