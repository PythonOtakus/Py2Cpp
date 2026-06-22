"""``@refcount`` 托管类：按 AST 语义生成 C++，不翻译方法体。"""

from __future__ import annotations

import ast
from contextlib import nullcontext
from typing import TYPE_CHECKING

from .copy_move_emit import emit_auto_copy_move, emit_copy_move_special_members
from ..analysis.ir import ClassInfo, MethodSig, cpp_param, format_fn_sig

if TYPE_CHECKING:
  from ..translator import Translator


def emit_refcount_class_impl(translator: Translator, info: ClassInfo) -> None:
  """为 ``@refcount`` 类生成构造/析构与 ``__copy__`` / ``__move__`` 实现。"""
  from ..emit.class_emit import _emit_method

  emitter = _RefcountEmitter(translator, info)
  for init, sig in zip(info.inits, info.init_sigs):
    emitter.emit_ctor(init, sig)
  if info.needs_auto_dtor():
    emitter.emit_default_dtor()
  elif "__del__" in info.methods:
    emitter.emit_dtor(info.methods["__del__"], info.method_sigs["__del__"])
  for name in ("__copy__", "__move__"):
    if name in info.methods:
      _emit_method(translator, info, info.methods[name], info.method_sigs[name])
  emit_auto_copy_move(translator, info)
  emit_copy_move_special_members(translator, info)
  for method in info.methods.values():
    if method.name in ("__del__", "__copy__", "__move__"):
      continue
    _emit_method(translator, info, method, info.method_sigs[method.name])
  from .class_emit import _emit_class_properties

  _emit_class_properties(translator, info)


class _RefcountEmitter:
  def __init__(self, translator: Translator, info: ClassInfo) -> None:
    self.t = translator
    self.info = info
    self.cpp = info.cpp_name()
    self._field_free: dict[str, str] = {}

  def _ctx(self):
    if self.info.is_template():
      return self.t._use_module_inl(self.info.module_path)
    if self.t._is_stdlib_module(self.info.module_path):
      return self.t._use_module_inl(self.info.module_path)
    return nullcontext()

  def _method_qual(self) -> str:
    if hasattr(self.t, "_class_method_qualifier"):
      return self.t._class_method_qualifier(self.info)
    return self.cpp

  def emit_ctor(self, init: ast.FunctionDef, sig: MethodSig) -> None:
    with self._ctx(), self.t._use_source():
      if self.info.is_template():
        self.t._emit_template_prefix(self.info)
      qual = self._method_qual()
      header = f"{qual}::{self.cpp}({sig.params_def})"
      with self.t._use_self_type(self.info), self.t._use_block(header):
        for stmt in init.body:
          self._emit_init_stmt(stmt)

  def emit_default_dtor(self) -> None:
    with self._ctx(), self.t._use_source():
      if self.info.is_template():
        self.t._emit_template_prefix(self.info)
      qual = self._method_qual()
      with self.t._use_block(f"{qual}::~{self.cpp}()"):
        self._emit_owned_field_releases(self.info.owned_fields)
      self.t.write_line()

  def emit_dtor(self, method: ast.FunctionDef, sig: MethodSig) -> None:
    with self._ctx(), self.t._use_source():
      if self.info.is_template():
        self.t._emit_template_prefix(self.info)
      qual = self._method_qual()
      header = f"{qual}::~{self.cpp}()"
      with self.t._use_block(header):
        for stmt in method.body:
          self._emit_del_stmt(stmt)
      self.t.write_line()

  def _emit_owned_field_releases(self, owned: dict[str, tuple[str, str]]) -> None:
    for field, (elem, kind) in owned.items():
      fn = "freeArray" if kind == "freeArray" else "free"
      with self.t._use_block(f"if ((this->{field} != nullptr))"):
        self.t.write_line(f"{fn}<{elem}>(this->{field});")

  def _emit_del_stmt(self, stmt: ast.stmt) -> None:
    match stmt:
      case ast.If(test=test, body=body, orelse=()):
        cond = self._emit_none_check(test)
        with self.t._use_block(f"if ({cond})"):
          for inner in body:
            self._emit_free_stmt(inner)
      case _:
        for inner in ast.walk(stmt):
          if isinstance(inner, ast.Expr) and isinstance(inner.value, ast.Call):
            self._emit_free_stmt(inner)

  def _emit_none_check(self, test: ast.expr) -> str:
    match test:
      case ast.Compare(left=ast.Attribute(value=ast.Name(id="self"), attr=field), ops=[ast.IsNot()], comparators=[ast.Constant(value=None)]):
        return f"(this->{field} != nullptr)"
      case ast.Compare(left=ast.Attribute(value=ast.Name(id="self"), attr=field), ops=[ast.Is()], comparators=[ast.Constant(value=None)]):
        return f"(this->{field} == nullptr)"
      case _:
        return self.t.visit(test)

  def _emit_field_assign(self, tgt: ast.expr, value: ast.expr) -> None:
    if not (isinstance(tgt, ast.Attribute) and isinstance(tgt.value, ast.Name) and tgt.value.id == "self"):
      raise NotImplementedError(f"@refcount 构造赋值目标: {ast.dump(tgt)}")
    field = tgt.attr
    match value:
      case ast.Constant(value=None):
        self.t.write_line(f"this->{field} = nullptr;")
      case ast.Call(func=ast.Subscript(value=ast.Name(id="alloc"), slice=sl), args=[]) if isinstance(sl, ast.Name):
        elem = sl.id
        self._field_free[field] = "free"
        self.info.owned_fields[field] = (elem, "free")
        self.t.write_line(f"this->{field} = alloc<{elem}>();")
      case ast.Call(func=ast.Subscript(value=ast.Name(id="allocArray"), slice=sl), args=args) if isinstance(sl, ast.Name):
        elem = sl.id
        self._field_free[field] = "freeArray"
        self.info.owned_fields[field] = (elem, "freeArray")
        count = self.t.visit(args[0]) if args else "1"
        self.t.write_line(f"this->{field} = allocArray<{elem}>({count});")
      case ast.Name(id=name):
        self.t.write_line(f"this->{field} = {cpp_param(name)};")
      case ast.Attribute(value=ast.Name(id="new")) as new_attr:
        from .call_emit import try_emit_new_staticproperty_ref

        from ..analysis.type_emit import field_storage_cpp

        ft = field_storage_cpp(self.info, field, fallback="") or None
        if not ft and self.info.dataclass_field_specs:
          for spec in self.info.dataclass_field_specs:
            if spec.name == field:
              ft = self.t._parse_storage_type(
                spec.annotation, self.t._active_type_params(),
              )
              break
        sp = try_emit_new_staticproperty_ref(
          self.t, new_attr, field_cpp_type=ft,
        )
        if sp is not None:
          self.t.write_line(f"this->{field} = {sp};")
        else:
          self.t.write_line(f"this->{field} = {self.t.visit(value)};")
      case _:
        self.t.write_line(f"this->{field} = {self.t.visit(value)};")

  def _emit_field_subscript_assign(self, stmt: ast.Assign) -> None:
    tgt = stmt.targets[0]
    if not isinstance(tgt, ast.Subscript):
      raise NotImplementedError(ast.dump(stmt))
    base = tgt.value
    if not (isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name) and base.value.id == "self"):
      raise NotImplementedError(ast.dump(stmt))
    idx = self.t.visit(tgt.slice)
    self.t.write_line(f"this->{base.attr}[{idx}] = {self.t.visit(stmt.value)};")

  def _emit_init_stmt(self, stmt: ast.stmt) -> None:
    match stmt:
      case ast.Assign(targets=[ast.Subscript() as tgt], value=value):
        fake = ast.Assign(targets=[tgt], value=value)
        self._emit_field_subscript_assign(fake)
      case ast.Assign(targets=[tgt], value=value):
        self._emit_field_assign(tgt, value)
      case ast.Pass() | ast.Expr(value=ast.Constant(value=None)):
        pass
      case _:
        raise NotImplementedError(f"@refcount 构造语句: {ast.dump(stmt)}")

  def _emit_free_stmt(self, stmt: ast.stmt) -> None:
    call = stmt.value if isinstance(stmt, ast.Expr) else stmt
    if not isinstance(call, ast.Call):
      return
    match call.func:
      case ast.Subscript(value=ast.Name(id=name), slice=sl) if name in ("free", "freeArray") and isinstance(sl, ast.Name):
        elem = sl.id
        kind = "freeArray" if name == "freeArray" else "free"
        buf = self.t.visit(call.args[0])
        if isinstance(call.args[0], ast.Attribute) and isinstance(call.args[0].value, ast.Name):
          if call.args[0].value.id == "self":
            kind = self._field_free.get(call.args[0].attr, kind)
        fn = "freeArray" if kind == "freeArray" else "free"
        self.t.write_line(f"{fn}<{elem}>({buf});")
      case _:
        raise NotImplementedError(f"@refcount 析构释放: {ast.dump(call)}")
