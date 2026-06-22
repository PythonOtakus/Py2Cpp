"""``VarStack``：``@mixin`` 内 ``s: VarStack = new()`` + ``s.push`` / ``s.pop`` / ``s.top()`` + ``new(*s)`` / ``fn(*s)`` 译期展开。"""
from __future__ import annotations

import ast
import copy
from dataclasses import dataclass, field

from ..analysis.ir import ClassInfo, strip_type_annotation_markers
from ..analysis.type_emit import field_ann_ast
from .match_case import (
  _clone_body_replace_names,
  _host_iter_field_names,
  _is_any_fields_loop_call,
  _is_iter_fields_call,
  _parse_iter_fields_public_only,
)
from .static_reflect import StaticReflectFolder


def _is_varstack_annotation(node: ast.expr | None) -> bool:
  return isinstance(node, ast.Name) and node.id == "VarStack"


def _is_varstack_new_init(value: ast.expr | None) -> bool:
  """``new()`` 无实参，作为 ``VarStack`` 声明初始化（译期占位，无 C++ 构造）。"""
  return (
    isinstance(value, ast.Call)
    and isinstance(value.func, ast.Name)
    and value.func.id == "new"
    and not value.args
    and not value.keywords
  )


def _varstack_decl_error(node: ast.AST, detail: str) -> NotImplementedError:
  lineno = getattr(node, "lineno", 0) or 0
  return NotImplementedError(f"{lineno}: VarStack {detail}（须写 ``s: VarStack = new()``）")


def _validate_varstack_decl(node: ast.AnnAssign) -> str:
  if not isinstance(node.target, ast.Name) or not _is_varstack_annotation(node.annotation):
    raise ValueError("_validate_varstack_decl: 非 VarStack AnnAssign")
  if not _is_varstack_new_init(node.value):
    raise _varstack_decl_error(node.target, f"声明 {node.target.id!r} 须写 ``= new()``")
  return node.target.id


def _varstack_pop_name(node: ast.Call) -> str | None:
  if node.args or node.keywords:
    return None
  if not (
    isinstance(node.func, ast.Attribute)
    and node.func.attr == "pop"
    and isinstance(node.func.value, ast.Name)
  ):
    return None
  return node.func.value.id


def _is_varstack_pop_expr(node: ast.expr) -> str | None:
  if not isinstance(node, ast.Call):
    return None
  return _varstack_pop_name(node)


def _varstack_top_name(node: ast.Call) -> str | None:
  if node.args or node.keywords:
    return None
  if not (
    isinstance(node.func, ast.Attribute)
    and node.func.attr == "top"
    and isinstance(node.func.value, ast.Name)
  ):
    return None
  return node.func.value.id


def _is_varstack_top_expr(node: ast.expr) -> str | None:
  if not isinstance(node, ast.Call):
    return None
  return _varstack_top_name(node)


def _parse_varstack_push(stmt: ast.stmt) -> tuple[str, ast.expr] | None:
  """``stack.push(expr)`` 语句 → ``(stack, expr)``。"""
  expr_node: ast.expr | None = None
  if isinstance(stmt, ast.Expr):
    expr_node = stmt.value
  elif isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
    if isinstance(stmt.targets[0], ast.Name) and stmt.targets[0].id == "_":
      expr_node = stmt.value
  if not isinstance(expr_node, ast.Call):
    return None
  call = expr_node
  if not (
    isinstance(call.func, ast.Attribute)
    and call.func.attr == "push"
    and isinstance(call.func.value, ast.Name)
    and len(call.args) == 1
    and not call.keywords
  ):
    return None
  return call.func.value.id, call.args[0]


def _parse_varstack_pop_stmt(stmt: ast.stmt) -> tuple[str, ast.stmt] | None:
  """顶层 ``pop`` 语句 → ``(stack, 原语句)``。"""
  if isinstance(stmt, ast.Expr):
    stack = _is_varstack_pop_expr(stmt.value)
    if stack is not None:
      return stack, stmt
  if isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
    stack = _is_varstack_pop_expr(stmt.value)
    if stack is not None:
      return stack, stmt
  if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and stmt.value is not None:
    stack = _is_varstack_pop_expr(stmt.value)
    if stack is not None:
      return stack, stmt
  return None


def _starred_stack_name(node: ast.Starred) -> str | None:
  if isinstance(node.value, ast.Name):
    return node.value.id
  return None


def _collect_varstack_names(method: ast.FunctionDef) -> set[str]:
  names: set[str] = set()
  for node in ast.walk(method):
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
      if _is_varstack_annotation(node.annotation):
        names.add(_validate_varstack_decl(node))
  return names


def _varstack_push_name_from_call(node: ast.Call) -> str | None:
  if not (
    isinstance(node.func, ast.Attribute)
    and node.func.attr == "push"
    and isinstance(node.func.value, ast.Name)
    and len(node.args) == 1
    and not node.keywords
  ):
    return None
  return node.func.value.id


def _iter_varstack_top_uses_in_expr(node: ast.AST) -> list[tuple[str, ast.AST]]:
  """表达式子树内的 ``top()`` → ``(栈名, 节点)``（仅须已声明，可跨内层作用域）。"""
  out: list[tuple[str, ast.AST]] = []
  for sub in ast.walk(node):
    if isinstance(sub, ast.Call):
      stack = _varstack_top_name(sub)
      if stack is not None:
        out.append((stack, sub))
  return out


def _iter_varstack_uses_in_expr(node: ast.AST) -> list[tuple[str, ast.AST]]:
  """表达式子树内的 ``pop`` / ``*stack`` → ``(栈名, 节点)``。"""
  out: list[tuple[str, ast.AST]] = []
  for sub in ast.walk(node):
    if isinstance(sub, ast.Starred):
      stack = _starred_stack_name(sub)
      if stack is not None:
        out.append((stack, sub))
    elif isinstance(sub, ast.Call):
      stack = _varstack_pop_name(sub)
      if stack is not None:
        out.append((stack, sub))
  return out


def _varstack_scope_error(name: str, node: ast.AST, detail: str) -> NotImplementedError:
  lineno = getattr(node, "lineno", 0) or 0
  return NotImplementedError(
    f"{lineno}: VarStack {name!r} {detail}（``Self.iter_fields`` 循环体译期展开，不另计作用域）"
  )


class _VarStackScopeChecker(ast.NodeVisitor):
  """``VarStack`` 声明与 ``push`` / ``pop`` / ``*s`` 须在同一块作用域；``top()`` 可跨内层作用域。"""

  def __init__(self) -> None:
    self._next_scope_id = 0
    self._scope_stack: list[int] = [0]
    self._decl_scope: dict[str, int] = {}

  def _current_scope(self) -> int:
    return self._scope_stack[-1]

  def _enter_scope(self) -> None:
    self._next_scope_id += 1
    self._scope_stack.append(self._next_scope_id)

  def _exit_scope(self) -> None:
    self._scope_stack.pop()

  def _register_decl(self, name: str, node: ast.AST) -> None:
    scope = self._current_scope()
    if name in self._decl_scope:
      raise _varstack_scope_error(name, node, "在同一作用域内重复声明")
    self._decl_scope[name] = scope

  def _check_declared(self, name: str, node: ast.AST) -> None:
    if name not in self._decl_scope:
      raise _varstack_scope_error(name, node, "尚未声明")

  def _check_use(self, name: str, node: ast.AST) -> None:
    decl = self._decl_scope.get(name)
    if decl is None:
      raise _varstack_scope_error(name, node, "尚未声明")
    if decl != self._current_scope():
      raise _varstack_scope_error(name, node, "声明与使用不在同一作用域")

  def _check_push(self, name: str, node: ast.AST) -> None:
    self._check_use(name, node)

  def _check_expr_uses(self, node: ast.expr | None) -> None:
    if node is None:
      return
    for stack, sub in _iter_varstack_top_uses_in_expr(node):
      self._check_declared(stack, sub)
    for stack, sub in _iter_varstack_uses_in_expr(node):
      self._check_use(stack, sub)

  def _visit_stmt_list(self, body: list[ast.stmt]) -> None:
    for stmt in body:
      self.visit(stmt)

  def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
    if isinstance(node.target, ast.Name) and _is_varstack_annotation(node.annotation):
      name = _validate_varstack_decl(node)
      self._register_decl(name, node)
      return
    if node.value is not None:
      stack = _is_varstack_pop_expr(node.value)
      if stack is not None:
        self._check_use(stack, node.value)
      else:
        top = _is_varstack_top_expr(node.value)
        if top is not None:
          self._check_declared(top, node.value)
        else:
          self._check_expr_uses(node.value)
    self.generic_visit(node)

  def visit_Assign(self, node: ast.Assign) -> None:
    parsed_push = _parse_varstack_push(node)
    if parsed_push is not None:
      self._check_push(parsed_push[0], node)
      return
    parsed_pop = _parse_varstack_pop_stmt(node)
    if parsed_pop is not None:
      self._check_use(parsed_pop[0], node.value)
      return
    for tgt in node.targets:
      self.visit(tgt)
    if node.value is not None:
      self._check_expr_uses(node.value)

  def visit_Expr(self, node: ast.Expr) -> None:
    parsed_push = _parse_varstack_push(node)
    if parsed_push is not None:
      self._check_push(parsed_push[0], node)
      return
    stack = _is_varstack_pop_expr(node.value)
    if stack is not None:
      self._check_use(stack, node.value)
      return
    top = _is_varstack_top_expr(node.value)
    if top is not None:
      self._check_declared(top, node.value)
      return
    self._check_expr_uses(node.value)

  def visit_Return(self, node: ast.Return) -> None:
    self._check_expr_uses(node.value)

  def visit_For(self, node: ast.For) -> None:
    if _is_any_fields_loop_call(node.iter):
      self._visit_stmt_list(node.body)
      self._visit_stmt_list(node.orelse)
      return
    self._enter_scope()
    try:
      self._visit_stmt_list(node.body)
      self._visit_stmt_list(node.orelse)
    finally:
      self._exit_scope()

  def visit_While(self, node: ast.While) -> None:
    self._check_expr_uses(node.test)
    self._enter_scope()
    try:
      self._visit_stmt_list(node.body)
      self._visit_stmt_list(node.orelse)
    finally:
      self._exit_scope()

  def visit_If(self, node: ast.If) -> None:
    self._check_expr_uses(node.test)
    self._enter_scope()
    try:
      self._visit_stmt_list(node.body)
    finally:
      self._exit_scope()
    self._enter_scope()
    try:
      self._visit_stmt_list(node.orelse)
    finally:
      self._exit_scope()

  def visit_With(self, node: ast.With) -> None:
    for item in node.items:
      self._check_expr_uses(item.context_expr)
      if item.optional_vars is not None:
        self.visit(item.optional_vars)
    self._enter_scope()
    try:
      self._visit_stmt_list(node.body)
    finally:
      self._exit_scope()

  def visit_Try(self, node: ast.Try) -> None:
    self._enter_scope()
    try:
      self._visit_stmt_list(node.body)
    finally:
      self._exit_scope()
    for handler in node.handlers:
      self._enter_scope()
      try:
        self._visit_stmt_list(handler.body)
      finally:
        self._exit_scope()
    self._enter_scope()
    try:
      self._visit_stmt_list(node.orelse)
    finally:
      self._exit_scope()
    self._enter_scope()
    try:
      self._visit_stmt_list(node.finalbody)
    finally:
      self._exit_scope()

  def visit_Match(self, node: ast.Match) -> None:
    self._check_expr_uses(node.subject)
    for case in node.cases:
      self._enter_scope()
      try:
        self._visit_stmt_list(case.body)
      finally:
        self._exit_scope()


def check_varstack_scopes(method: ast.FunctionDef) -> None:
  if not _collect_varstack_names(method):
    return
  _VarStackScopeChecker().visit(method)


@dataclass
class _VarStackState:
  stacks: set[str]
  stack_slots: dict[str, list[str]] = field(default_factory=dict)
  next_idx: dict[str, int] = field(default_factory=dict)

  def __post_init__(self) -> None:
    for name in self.stacks:
      self.stack_slots.setdefault(name, [])
      self.next_idx.setdefault(name, 0)

  def _alloc_temp(self, stack: str) -> str:
    idx = self.next_idx[stack]
    self.next_idx[stack] = idx + 1
    return f"__vs_{stack}{idx}"

  def push_assign(
    self,
    stack: str,
    value: ast.expr,
    *,
    field_ann: ast.expr | None,
  ) -> ast.stmt:
    if stack not in self.stacks:
      raise NotImplementedError(f"未声明的 VarStack: {stack!r}")
    temp = self._alloc_temp(stack)
    self.stack_slots[stack].append(temp)
    target = ast.Name(id=temp, ctx=ast.Store())
    val = copy.deepcopy(value)
    if field_ann is not None:
      return ast.AnnAssign(
        target=target,
        annotation=copy.deepcopy(field_ann),
        value=val,
        simple=1,
      )
    return ast.Assign(targets=[target], value=val)

  def pop_temp(self, stack: str) -> str:
    if stack not in self.stacks:
      raise NotImplementedError(f"未声明的 VarStack: {stack!r}")
    slots = self.stack_slots[stack]
    if not slots:
      raise NotImplementedError(f"VarStack {stack!r} pop 时下栈为空")
    return slots.pop()

  def peek_temp(self, stack: str) -> str:
    if stack not in self.stacks:
      raise NotImplementedError(f"未声明的 VarStack: {stack!r}")
    slots = self.stack_slots[stack]
    if not slots:
      raise NotImplementedError(f"VarStack {stack!r} top 时下栈为空")
    return slots[-1]

  def pop_stmt(self, stack: str, stmt: ast.stmt) -> list[ast.stmt]:
    temp = self.pop_temp(stack)
    if isinstance(stmt, ast.Expr):
      return []
    out = copy.deepcopy(stmt)
    out.value = ast.Name(id=temp, ctx=ast.Load())
    return [out]


def _transform_varstack_in_stmt(
  stmt: ast.stmt,
  state: _VarStackState,
  *,
  field_ann: ast.expr | None,
) -> list[ast.stmt]:
  parsed_push = _parse_varstack_push(stmt)
  if parsed_push is not None:
    stack, value = parsed_push
    return [state.push_assign(stack, value, field_ann=field_ann)]
  parsed_pop = _parse_varstack_pop_stmt(stmt)
  if parsed_pop is not None:
    stack, pop_stmt = parsed_pop
    return state.pop_stmt(stack, pop_stmt)
  if isinstance(stmt, ast.If):
    stmt = copy.deepcopy(stmt)
    stmt.body = [
      s
      for child in stmt.body
      for s in _transform_varstack_in_stmt(child, state, field_ann=field_ann)
    ]
    stmt.orelse = [
      s
      for child in stmt.orelse
      for s in _transform_varstack_in_stmt(child, state, field_ann=field_ann)
    ]
    return [stmt]
  if isinstance(stmt, (ast.For, ast.While, ast.With)):
    stmt = copy.deepcopy(stmt)
    if isinstance(stmt, ast.For):
      stmt.body = [
        s
        for child in stmt.body
        for s in _transform_varstack_in_stmt(child, state, field_ann=field_ann)
      ]
      stmt.orelse = [
        s
        for child in stmt.orelse
        for s in _transform_varstack_in_stmt(child, state, field_ann=field_ann)
      ]
    elif isinstance(stmt, ast.While):
      stmt.body = [
        s
        for child in stmt.body
        for s in _transform_varstack_in_stmt(child, state, field_ann=field_ann)
      ]
      stmt.orelse = [
        s
        for child in stmt.orelse
        for s in _transform_varstack_in_stmt(child, state, field_ann=field_ann)
      ]
    else:
      for item in stmt.body:
        item.body = [
          s
          for child in item.body
          for s in _transform_varstack_in_stmt(child, state, field_ann=field_ann)
        ]
    return [stmt]
  if isinstance(stmt, ast.Try):
    stmt = copy.deepcopy(stmt)
    stmt.body = [
      s
      for child in stmt.body
      for s in _transform_varstack_in_stmt(child, state, field_ann=field_ann)
    ]
    for handler in stmt.handlers:
      handler.body = [
        s
        for child in handler.body
        for s in _transform_varstack_in_stmt(child, state, field_ann=field_ann)
      ]
    stmt.orelse = [
      s
      for child in stmt.orelse
      for s in _transform_varstack_in_stmt(child, state, field_ann=field_ann)
    ]
    stmt.finalbody = [
      s
      for child in stmt.finalbody
      for s in _transform_varstack_in_stmt(child, state, field_ann=field_ann)
    ]
    return [stmt]
  if isinstance(stmt, ast.Match):
    stmt = copy.deepcopy(stmt)
    for case in stmt.cases:
      case.body = [
        s
        for child in case.body
        for s in _transform_varstack_in_stmt(child, state, field_ann=field_ann)
      ]
    return [stmt]
  return [copy.deepcopy(stmt)]


def _transform_varstack_in_body(
  body: list[ast.stmt],
  state: _VarStackState,
  *,
  field_var: str,
  field_name: str,
  field_ann: ast.expr | None,
  known_fields: frozenset[str],
) -> list[ast.stmt]:
  renames = {field_var: ast.Constant(value=field_name)}
  cloned = _clone_body_replace_names(body, renames, known_fields=known_fields)
  out: list[ast.stmt] = []
  for stmt in cloned:
    out.extend(
      _transform_varstack_in_stmt(stmt, state, field_ann=field_ann),
    )
  folder = StaticReflectFolder(known_fields)
  return [folder.visit(s) for s in out]


class _StarredExpander(ast.NodeTransformer):
  """展开 ``*stack`` / ``top()``；表达式内 ``pop`` 仅缩短逻辑栈，不回收 ``__vs_*`` 编号。"""

  def __init__(self, state: _VarStackState) -> None:
    self.state = state

  def _active_slots(self, stack: str) -> list[str]:
    if stack not in self.state.stack_slots:
      raise NotImplementedError(f"未声明的 VarStack: {stack!r}")
    return self.state.stack_slots[stack]

  def _expand_starred(self, stack: str) -> list[ast.expr]:
    names = self._active_slots(stack)
    if not names:
      raise NotImplementedError(f"VarStack {stack!r} 尚无可用 push 结果，不能解包")
    return [ast.Name(id=n, ctx=ast.Load()) for n in names]

  def visit_Call(self, node: ast.Call) -> ast.AST:
    stack = _varstack_top_name(node)
    if stack is not None:
      temp = self.state.peek_temp(stack)
      return ast.Name(id=temp, ctx=ast.Load())
    stack = _varstack_pop_name(node)
    if stack is not None:
      temp = self.state.pop_temp(stack)
      return ast.Name(id=temp, ctx=ast.Load())
    self.generic_visit(node)
    node.args = self._expand_call_args(node.args)
    return node

  def _expand_call_args(self, args: list[ast.expr]) -> list[ast.expr]:
    out: list[ast.expr] = []
    for arg in args:
      if isinstance(arg, ast.Starred):
        stack = _starred_stack_name(arg)
        if stack is None or stack not in self.state.stacks:
          raise NotImplementedError("VarStack 解包仅支持 ``*stack_name``")
        out.extend(self._expand_starred(stack))
      else:
        out.append(arg)
    return out

  def visit_Tuple(self, node: ast.Tuple) -> ast.AST:
    self.generic_visit(node)
    out: list[ast.expr] = []
    for elt in node.elts:
      if isinstance(elt, ast.Starred):
        stack = _starred_stack_name(elt)
        if stack is None or stack not in self.state.stacks:
          raise NotImplementedError("VarStack 解包仅支持 ``*stack_name``")
        out.extend(self._expand_starred(stack))
      else:
        out.append(elt)
    node.elts = out
    return node


def _expand_starred_in_body(body: list[ast.stmt], state: _VarStackState) -> list[ast.stmt]:
  expander = _StarredExpander(state)
  out: list[ast.stmt] = []
  for stmt in body:
    expanded = expander.visit(stmt)
    if expanded is None:
      continue
    if isinstance(expanded, list):
      out.extend(expanded)
    else:
      out.append(expanded)
  return out


def expand_varstack(method: ast.FunctionDef, host: ClassInfo) -> ast.FunctionDef | None:
  """``VarStack`` + ``Self.iter_fields`` / 独立 ``push`` → 具名临时量 + ``new(a, b, …)``。"""
  stacks = _collect_varstack_names(method)
  if not stacks:
    return None
  check_varstack_scopes(method)
  state = _VarStackState(stacks)
  known = frozenset(host.fields)
  new_body: list[ast.stmt] = []
  for stmt in method.body:
    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
      if _is_varstack_annotation(stmt.annotation):
        continue
    if isinstance(stmt, ast.For) and _is_iter_fields_call(stmt.iter):
      if not isinstance(stmt.target, ast.Name):
        raise NotImplementedError("VarStack 的 ``Self.iter_fields`` 循环变量须为简单名")
      field_var = stmt.target.id
      public_only = _parse_iter_fields_public_only(stmt.iter)
      assert public_only is not None
      field_names = _host_iter_field_names(host, public_only=public_only)
      for field_name in field_names:
        ann = field_ann_ast(host, field_name)
        stripped = strip_type_annotation_markers(ann)
        new_body.extend(
          _transform_varstack_in_body(
            stmt.body,
            state,
            field_var=field_var,
            field_name=field_name,
            field_ann=stripped,
            known_fields=known,
          ),
        )
      continue
    new_body.extend(_transform_varstack_in_stmt(stmt, state, field_ann=None))
  out = copy.deepcopy(method)
  out.body = _expand_starred_in_body(new_body, state)
  ast.fix_missing_locations(out)
  return out


def method_uses_varstack(method: ast.FunctionDef) -> bool:
  return bool(_collect_varstack_names(method))


def method_has_unexpanded_varstack(method: ast.FunctionDef) -> bool:
  if method_uses_varstack(method):
    return True
  for node in ast.walk(method):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
      if isinstance(node.func.value, ast.Name):
        if node.func.attr in ("push", "pop", "top"):
          return True
  return False
