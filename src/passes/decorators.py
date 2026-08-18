"""装饰器：``@decorator`` / ``@context`` 函数装饰、``@context`` 的 ``with`` 展开。

``@context`` 且含 ``yield``：可作上下文管理器，也可作装饰器（``yield`` 前为 enter、后为 exit）。
``@context`` 且无 ``yield``：与 ``@decorator`` 相同（整段工厂体替换被装饰函数体）。
"""
from __future__ import annotations

import ast
import copy
from typing import TYPE_CHECKING

if TYPE_CHECKING:
  from ..translator import Translator

from ..analysis.ir import ClassInfo, has_named_decorator

DECORATOR_MARKER = "decorator"
CONTEXT_MARKER = "context"
WITH_CONTEXT_FUNC_NAME = "<with context>"


def _has_marker(func: ast.FunctionDef, name: str) -> bool:
  for dec in func.decorator_list:
    if isinstance(dec, ast.Name) and dec.id == name:
      return True
    if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name) and dec.func.id == name:
      return True
  return False


def is_decorator_definition(func: ast.FunctionDef) -> bool:
  return _has_marker(func, DECORATOR_MARKER)


def is_context_definition(func: ast.FunctionDef) -> bool:
  return _has_marker(func, CONTEXT_MARKER)


def parse_decorator_applications(func: ast.FunctionDef) -> list[tuple[str, ast.Call | None]]:
  apps: list[tuple[str, ast.Call | None]] = []
  for dec in func.decorator_list:
    if isinstance(dec, ast.Name):
      if dec.id in (DECORATOR_MARKER, CONTEXT_MARKER):
        continue
      apps.append((dec.id, None))
    elif isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name):
      if dec.func.id in (DECORATOR_MARKER, CONTEXT_MARKER):
        continue
      apps.append((dec.func.id, dec))
  return apps


def _factory_default_bindings(factory: ast.FunctionDef) -> dict[str, ast.expr]:
  """工厂形参默认值（``def cm(a=1):`` / ``@cm`` / ``with cm`` 无实参时使用）。"""
  bound: dict[str, ast.expr] = {}
  args = factory.args
  pos = list(args.args)
  defaults = list(args.defaults or [])
  n = len(defaults)
  if n:
    for arg, default in zip(pos[-n:], defaults):
      bound[arg.arg] = _default_binding_expr(arg, default)
  for arg, default in zip(args.kwonlyargs or [], args.kw_defaults or []):
    if default is not None:
      bound[arg.arg] = _default_binding_expr(arg, default)
  return bound


def _default_binding_expr(arg: ast.arg, default: ast.expr) -> ast.expr:
  """``None`` 默认实参与 ``str`` 等标量注解：展开为可参与 ``or``/真值测试的空值。"""
  if isinstance(default, ast.Constant) and default.value is None and arg.annotation is not None:
    ann = ast.unparse(arg.annotation)
    if ann in ("str", "PyStr"):
      return ast.Constant(value="")
  return copy.deepcopy(default)


def bind_call_params(factory: ast.FunctionDef, call: ast.Call | None) -> dict[str, ast.expr]:
  bound = _factory_default_bindings(factory)
  if call is None:
    return bound
  params = [a.arg for a in factory.args.args]
  for i, name in enumerate(params):
    if i < len(call.args):
      bound[name] = call.args[i]
  for kw in call.keywords:
    if kw.arg:
      bound[kw.arg] = kw.value
  return bound


class _BindParams(ast.NodeTransformer):
  def __init__(self, bound: dict[str, ast.expr]):
    self._bound = bound

  def visit_Name(self, node: ast.Name) -> ast.expr:
    if isinstance(node.ctx, ast.Load) and node.id in self._bound:
      return copy.deepcopy(self._bound[node.id])
    return node


class _FactoryFuncNameReplacer(ast.NodeTransformer):
  """``@decorator`` / ``@context`` 工厂体内的 ``__func__.__name__`` → 工厂函数名。"""

  def __init__(self, factory_name: str):
    self._factory_name = factory_name

  def visit_Attribute(self, node: ast.Attribute) -> ast.expr:
    if (
      isinstance(node.value, ast.Name)
      and node.value.id == "__func__"
      and node.attr == "__name__"
    ):
      return ast.Constant(value=self._factory_name)
    return self.generic_visit(node)


def _normalize_factory_func_names(factory: ast.FunctionDef) -> None:
  replacer = _FactoryFuncNameReplacer(factory.name)
  factory.body = [replacer.visit(copy.deepcopy(stmt)) for stmt in factory.body]
  ast.fix_missing_locations(factory)


class _WithBlockFuncNameReplacer(ast.NodeTransformer):
  """``with`` 展开时，上下文体内的 ``__func__.__name__`` → ``\"<with context>\"``。"""

  def visit_Attribute(self, node: ast.Attribute) -> ast.expr:
    if (
      isinstance(node.value, ast.Name)
      and node.value.id == "__func__"
      and node.attr == "__name__"
    ):
      return ast.Constant(value=WITH_CONTEXT_FUNC_NAME)
    return self.generic_visit(node)


class _FoldStringOr(ast.NodeTransformer):
  """编译期折叠 ``\"a\" or \"b\"``（含空串）。"""

  def visit_BoolOp(self, node: ast.BoolOp) -> ast.expr:
    self.generic_visit(node)
    if isinstance(node.op, ast.Or) and all(
      isinstance(v, ast.Constant) and isinstance(v.value, str) for v in node.values
    ):
      for v in node.values:
        if v.value:
          return ast.Constant(value=v.value)
      return ast.Constant(value=node.values[-1].value)
    return node


class _FuncDecoratorInliner(ast.NodeTransformer):
  def __init__(self, wrapped: ast.FunctionDef, impl_name: str, *, impl_on_class: bool = False):
    self._wrapped_name = wrapped.name
    self._impl_name = impl_name
    self._param_names = [a.arg for a in wrapped.args.args]
    self._impl_on_class = impl_on_class and (
      self._param_names and self._param_names[0] == "self"
    )

  def visit_Attribute(self, node: ast.Attribute) -> ast.expr:
    if (
      isinstance(node.value, ast.Name)
      and node.value.id == "__func__"
      and node.attr == "__name__"
    ):
      return ast.Constant(value=self._wrapped_name)
    return self.generic_visit(node)

  def visit_Call(self, node: ast.Call) -> ast.expr:
    node = self.generic_visit(node)
    if isinstance(node.func, ast.Name) and node.func.id == "__func__":
      raise ValueError("装饰器内请用 yield 调用被装饰函数，__func__(...) 已弃用")
    return node

  def _impl_call(self) -> ast.Call:
    if self._impl_on_class:
      return ast.Call(
        func=ast.Attribute(
          value=ast.Name(id="self", ctx=ast.Load()),
          attr=self._impl_name,
          ctx=ast.Load(),
        ),
        args=[],
        keywords=[],
      )
    return ast.Call(
      func=ast.Name(id=self._impl_name, ctx=ast.Load()),
      args=[ast.Name(id=p, ctx=ast.Load()) for p in self._param_names],
      keywords=[],
    )

  def visit_Yield(self, node: ast.Yield) -> ast.expr:
    """``@decorator`` 体内 ``yield`` / ``(yield)`` / ``yield ...`` 表示调用被装饰实现。"""
    if node.value is None or _is_ellipsis(node.value):
      return self._impl_call()
    raise NotImplementedError("装饰器内仅支持 yield / (yield) / yield ... 转发被装饰函数")


def _is_ellipsis(node: ast.expr) -> bool:
  return (isinstance(node, ast.Constant) and node.value is Ellipsis) or isinstance(
    node, ast.Ellipsis
  )


def _function_needs_return(func: ast.FunctionDef) -> bool:
  if func.returns is None:
    return False
  if isinstance(func.returns, ast.Constant) and func.returns.value is None:
    return False
  if isinstance(func.returns, ast.Name) and func.returns.id in ("None", "NoneType"):
    return False
  return True


def _body_has_return(body: list[ast.stmt]) -> bool:
  return any(isinstance(s, ast.Return) for s in body)


def _default_return_stmt(func: ast.FunctionDef) -> ast.Return:
  if isinstance(func.returns, ast.Name) and func.returns.id == "bool":
    return ast.Return(value=ast.Constant(value=False))
  return ast.Return(value=ast.Constant(value=None))


def _make_impl_function(wrapped: ast.FunctionDef) -> ast.FunctionDef:
  impl = copy.deepcopy(wrapped)
  impl.name = f"{wrapped.name}_impl"
  impl.decorator_list = []
  return impl


def _impl_on_host_class(wrapped: ast.FunctionDef, impl: ast.FunctionDef) -> bool:
  return bool(
    wrapped.args.args
    and wrapped.args.args[0].arg == "self"
    and impl.name == f"{wrapped.name}_impl"
  )


def apply_decorator(
  wrapped: ast.FunctionDef,
  factory: ast.FunctionDef,
  call: ast.Call | None,
) -> tuple[ast.FunctionDef, ast.FunctionDef]:
  impl = _make_impl_function(wrapped)
  bound = bind_call_params(factory, call)
  binder = _BindParams(bound)
  raw_body = copy.deepcopy(factory.body)
  _reject_deprecated_func_call(raw_body)
  inliner = _FuncDecoratorInliner(
    wrapped, impl.name, impl_on_class=_impl_on_host_class(wrapped, impl),
  )
  body = [inliner.visit(binder.visit(stmt)) for stmt in raw_body]
  if _function_needs_return(wrapped) and not _body_has_return(body):
    body.append(_default_return_stmt(wrapped))
  out = copy.deepcopy(wrapped)
  out.body = body
  out.decorator_list = []
  ast.fix_missing_locations(out)
  ast.fix_missing_locations(impl)
  return out, impl


def apply_context_decorator(
  wrapped: ast.FunctionDef,
  factory: ast.FunctionDef,
  call: ast.Call | None,
) -> tuple[ast.FunctionDef, ast.FunctionDef | None]:
  """将含 ``yield`` 的 ``@context`` 工厂展开为 enter + 被装饰体 + exit。"""
  pre, post = _split_context_body(factory.body)
  bound = bind_call_params(factory, call)
  pre_b = _bind_stmts(pre, bound)
  post_b = _bind_stmts(post, bound)
  inner_body = copy.deepcopy(wrapped.body)
  impl: ast.FunctionDef | None = None
  _reject_deprecated_func_call(pre_b + post_b)
  if _stmts_reference_func(pre_b + post_b):
    if _stmts_invoke_wrapped(pre_b + post_b):
      impl = _make_impl_function(wrapped)
      inner_body = impl.body
    inliner = _FuncDecoratorInliner(
      wrapped,
      impl.name if impl else wrapped.name,
      impl_on_class=impl is not None and _impl_on_host_class(wrapped, impl),
    )
    pre_b = [inliner.visit(s) for s in pre_b]
    post_b = [inliner.visit(s) for s in post_b]
  out = copy.deepcopy(wrapped)
  out.body = pre_b + inner_body + post_b
  out.decorator_list = []
  if _function_needs_return(wrapped) and not _body_has_return(out.body):
    out.body.append(_default_return_stmt(wrapped))
  ast.fix_missing_locations(out)
  if impl is not None:
    ast.fix_missing_locations(impl)
  return out, impl


def _resolve_decorator_factory(
  dec_name: str,
  decorator_defs: dict[str, ast.FunctionDef],
  context_defs: dict[str, ast.FunctionDef],
) -> ast.FunctionDef | None:
  if dec_name in decorator_defs:
    return decorator_defs[dec_name]
  if dec_name in context_defs:
    return context_defs[dec_name]
  return None


def _apply_named_decorator(
  wrapped: ast.FunctionDef,
  factory: ast.FunctionDef,
  call: ast.Call | None,
) -> tuple[ast.FunctionDef, ast.FunctionDef | None]:
  if is_context_definition(factory) and _has_yield(factory.body):
    return apply_context_decorator(wrapped, factory, call)
  return apply_decorator(wrapped, factory, call)


def _parse_context_call(expr: ast.expr) -> tuple[str, ast.Call | None] | None:
  match expr:
    case ast.Call(func=ast.Name(id=name)):
      return name, expr
    case ast.Name(id=name):
      return name, None
    case _:
      return None


def _has_yield(body: list[ast.stmt]) -> bool:
  for node in ast.walk(ast.Module(body=body, type_ignores=[])):
    if isinstance(node, (ast.Yield, ast.YieldFrom)):
      return True
  return False


def _split_context_body(body: list[ast.stmt]) -> tuple[list[ast.stmt], list[ast.stmt]]:
  pre: list[ast.stmt] = []
  post: list[ast.stmt] = []
  after_yield = False
  for stmt in body:
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, (ast.Yield, ast.YieldFrom)):
      after_yield = True
      continue
    (post if after_yield else pre).append(stmt)
  if not after_yield:
    raise ValueError("上下文管理器须在函数体中包含 yield")
  return pre, post


def _stmts_reference_func(stmts: list[ast.stmt]) -> bool:
  for node in ast.walk(ast.Module(body=stmts, type_ignores=[])):
    if isinstance(node, ast.Name) and node.id == "__func__":
      return True
  return False


def _stmts_invoke_wrapped(stmts: list[ast.stmt]) -> bool:
  """装饰器展开体内用于调用被装饰函数的 ``yield``（非上下文 enter/exit 分界）。"""
  for node in ast.walk(ast.Module(body=stmts, type_ignores=[])):
    if isinstance(node, ast.Yield) and (node.value is None or _is_ellipsis(node.value)):
      return True
  return False


def _reject_deprecated_func_call(stmts: list[ast.stmt]) -> None:
  for node in ast.walk(ast.Module(body=stmts, type_ignores=[])):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "__func__":
      raise ValueError("装饰器内请用 yield 调用被装饰函数，__func__(...) 已弃用")


def _bind_stmts(stmts: list[ast.stmt], bound: dict[str, ast.expr]) -> list[ast.stmt]:
  binder = _BindParams(bound)
  return [binder.visit(copy.deepcopy(s)) for s in stmts]


def _bind_stmts_for_with(stmts: list[ast.stmt], bound: dict[str, ast.expr]) -> list[ast.stmt]:
  replacer = _WithBlockFuncNameReplacer()
  folder = _FoldStringOr()
  out: list[ast.stmt] = []
  for s in _bind_stmts(stmts, bound):
    s = replacer.visit(s)
    s = folder.visit(s)
    out.append(s)
  return out


def _is_expandable_context_with(
  node: ast.With, context_defs: dict[str, ast.FunctionDef]
) -> bool:
  """仅 ``@context`` 工厂且单上下文、无 ``as`` 时在翻译期展开；其余走 ``__enter__`` / ``__exit__``。"""
  if getattr(node, "is_async", False):
    return False
  if len(node.items) != 1:
    return False
  item = node.items[0]
  if item.optional_vars is not None:
    return False
  parsed = _parse_context_call(item.context_expr)
  if parsed is None:
    return False
  cm_name, _ = parsed
  return cm_name in context_defs


def _expand_with_stmt(node: ast.With, context_defs: dict[str, ast.FunctionDef]) -> list[ast.stmt]:
  if not _is_expandable_context_with(node, context_defs):
    return [copy.deepcopy(node)]
  item = node.items[0]
  parsed = _parse_context_call(item.context_expr)
  assert parsed is not None
  cm_name, call = parsed
  cm = context_defs[cm_name]
  pre, post = _split_context_body(cm.body)
  bound = bind_call_params(cm, call)
  inner = expand_with_in_stmts(node.body, context_defs)
  return _bind_stmts_for_with(pre, bound) + inner + _bind_stmts_for_with(post, bound)


def expand_with_in_stmts(stmts: list[ast.stmt], context_defs: dict[str, ast.FunctionDef]) -> list[ast.stmt]:
  out: list[ast.stmt] = []
  for stmt in stmts:
    if isinstance(stmt, ast.With):
      out.extend(_expand_with_stmt(stmt, context_defs))
      continue
    if isinstance(stmt, ast.If):
      stmt = copy.deepcopy(stmt)
      stmt.body = expand_with_in_stmts(stmt.body, context_defs)
      stmt.orelse = expand_with_in_stmts(stmt.orelse, context_defs)
      out.append(stmt)
      continue
    if isinstance(stmt, ast.For):
      stmt = copy.deepcopy(stmt)
      stmt.body = expand_with_in_stmts(stmt.body, context_defs)
      stmt.orelse = expand_with_in_stmts(stmt.orelse, context_defs)
      out.append(stmt)
      continue
    if isinstance(stmt, ast.While):
      stmt = copy.deepcopy(stmt)
      stmt.body = expand_with_in_stmts(stmt.body, context_defs)
      stmt.orelse = expand_with_in_stmts(stmt.orelse, context_defs)
      out.append(stmt)
      continue
    out.append(stmt)
  return out


def expand_with_in_function(func: ast.FunctionDef, context_defs: dict[str, ast.FunctionDef]) -> None:
  if not context_defs:
    return
  func.body = expand_with_in_stmts(func.body, context_defs)
  ast.fix_missing_locations(func)


def _expand_with_in_class(info, context_defs: dict[str, ast.FunctionDef]) -> None:
  for init in info.inits:
    expand_with_in_function(init, context_defs)
  for method in info.iter_methods():
    expand_with_in_function(method, context_defs)
  for prop in info.properties.values():
    if prop.getter:
      expand_with_in_function(prop.getter, context_defs)
    if prop.setter:
      expand_with_in_function(prop.setter, context_defs)
    if prop.postsetter:
      expand_with_in_function(prop.postsetter, context_defs)
  for prop in info.static_properties.values():
    if prop.getter:
      expand_with_in_function(prop.getter, context_defs)
    if prop.setter:
      expand_with_in_function(prop.setter, context_defs)
    if prop.postsetter:
      expand_with_in_function(prop.postsetter, context_defs)


def _expandable_decorator_apps(
  func: ast.FunctionDef,
  decorator_defs: dict[str, ast.FunctionDef],
  context_defs: dict[str, ast.FunctionDef],
) -> list[tuple[str, ast.Call | None]]:
  """仅 ``@decorator`` / ``@context`` 工厂；忽略 ``@override``、``@immutable`` 等。"""
  return [
    (name, call)
    for name, call in parse_decorator_applications(func)
    if _resolve_decorator_factory(name, decorator_defs, context_defs) is not None
  ]


def _apply_decorator_chain(
  func: ast.FunctionDef,
  decorator_defs: dict[str, ast.FunctionDef],
  context_defs: dict[str, ast.FunctionDef],
) -> tuple[ast.FunctionDef, list[ast.FunctionDef]]:
  apps = _expandable_decorator_apps(func, decorator_defs, context_defs)
  if not apps:
    return func, []
  current = func
  impls: list[ast.FunctionDef] = []
  for dec_name, call in apps:
    factory = _resolve_decorator_factory(dec_name, decorator_defs, context_defs)
    if factory is None:
      raise ValueError(f"未知装饰器: @{dec_name}（需先用 @decorator 或 @context 定义）")
    current, impl = _apply_named_decorator(current, factory, call)
    if impl is not None:
      impls.append(impl)
  return current, impls


def _sync_method_in_class_body(info: ClassInfo, name: str, method: ast.FunctionDef) -> None:
  """``info.methods`` 更新后同步 ``ClassDef.body`` AST。"""
  out: list[ast.stmt] = []
  for stmt in info.node.body:
    if (
      isinstance(stmt, ast.FunctionDef)
      and stmt.name == name
      and not has_named_decorator(stmt, "overload")
    ):
      out.append(method)
    else:
      out.append(stmt)
  info.node.body = out


def _append_impl_methods_to_class(info: ClassInfo, impls: list[ast.FunctionDef]) -> None:
  """``*_impl`` 挂在类上生成，避免模块级 static 误用 ``this``。"""
  for impl in impls:
    info.methods[impl.name] = impl
    info.node.body.append(impl)


def _expand_class_method_decorators(
  tr: Translator,
  decorator_defs: dict[str, ast.FunctionDef],
  context_defs: dict[str, ast.FunctionDef],
) -> None:
  for info in tr.classes.values():
    if info.is_descriptor or info.is_mixin or info.is_annotation:
      continue
    if info.module_path != tr.entry_module_path:
      continue
    for name, method in list(info.methods.items()):
      if name.endswith("_impl"):
        continue
      current, impls = _apply_decorator_chain(method, decorator_defs, context_defs)
      if current is method and not impls:
        continue
      info.methods[name] = current
      _sync_method_in_class_body(info, name, current)
      _append_impl_methods_to_class(info, impls)


def expand_decorators(tr: Translator) -> None:
  decorator_defs: dict[str, ast.FunctionDef] = {}
  context_defs: dict[str, ast.FunctionDef] = {}
  to_remove: list[tuple[str, ast.FunctionDef]] = []

  for mp, func in tr.module_functions:
    if is_decorator_definition(func):
      _normalize_factory_func_names(func)
      decorator_defs[func.name] = func
      to_remove.append((mp, func))
    elif is_context_definition(func):
      _normalize_factory_func_names(func)
      context_defs[func.name] = func
      to_remove.append((mp, func))

  for item in to_remove:
    tr.module_functions.remove(item)

  impls: list[tuple[str, ast.FunctionDef]] = []
  skip = getattr(tr, "skip_cached_analysis_module", None)
  for mp, func in list(tr.module_functions):
    if skip is not None and skip(mp):
      continue
    current, new_impls = _apply_decorator_chain(func, decorator_defs, context_defs)
    if current is func and not new_impls:
      continue
    for impl in new_impls:
      impls.append((mp, impl))
    idx = tr.module_functions.index((mp, func))
    tr.module_functions[idx] = (mp, current)

  _expand_class_method_decorators(tr, decorator_defs, context_defs)

  tr.module_functions[:0] = impls

  for _mp, func in tr.module_functions:
    if skip is not None and skip(_mp):
      continue
    expand_with_in_function(func, context_defs)
  for info in tr.classes.values():
    if skip is not None and skip(info.module_path):
      continue
    if info.is_descriptor or info.is_mixin or info.is_annotation:
      continue
    _expand_with_in_class(info, context_defs)
