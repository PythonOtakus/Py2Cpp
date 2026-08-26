"""RefactorPlan 解析、校验与 AST 改写（P0：单模块 ``rename_symbol``）。"""
from __future__ import annotations

import ast
import difflib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..passes.kwargs_options import TRANSLATOR_ONLY_METHODS

PLAN_VERSION = 1
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_RENAME_KINDS = frozenset({"field", "method", "class", "function"})


@dataclass
class PlanError(Exception):
  message: str

  def __str__(self) -> str:
    return self.message


@dataclass
class FileChange:
  path: Path
  old_text: str
  new_text: str

  @property
  def diff(self) -> str:
    old_lines = self.old_text.splitlines(keepends=True)
    new_lines = self.new_text.splitlines(keepends=True)
    rel = self.path.as_posix()
    return "".join(
      difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{rel}",
        tofile=f"b/{rel}",
      )
    )


@dataclass
class ApplyResult:
  changes: list[FileChange] = field(default_factory=list)
  errors: list[str] = field(default_factory=list)

  @property
  def ok(self) -> bool:
    return not self.errors


def load_plan(path: Path) -> dict[str, Any]:
  try:
    data = json.loads(path.read_text(encoding="utf-8"))
  except OSError as exc:
    raise PlanError(f"无法读取计划: {path}: {exc}") from exc
  except json.JSONDecodeError as exc:
    raise PlanError(f"计划 JSON 无效: {path}: {exc}") from exc
  if not isinstance(data, dict):
    raise PlanError("计划根须为 JSON 对象")
  return data


def _validate_ident(name: str, *, label: str) -> None:
  if not _IDENT_RE.match(name):
    raise PlanError(f"{label} 非法标识符: {name!r}")
  if name in TRANSLATOR_ONLY_METHODS:
    raise PlanError(f"{label} 与译期保留名冲突: {name}")


def _normalize_module(module: str) -> str:
  m = module.replace("\\", "/").strip("/")
  if m.endswith(".py"):
    m = m[:-3]
  return m


def _module_to_path(repo_root: Path, module: str) -> Path:
  rel = _normalize_module(module) + ".py"
  return repo_root / Path(rel.replace("\\", "/"))


def validate_plan(plan: dict[str, Any], repo_root: Path) -> list[str]:
  errors: list[str] = []
  version = plan.get("version")
  if version != PLAN_VERSION:
    errors.append(f"不支持的 plan version: {version!r}（期望 {PLAN_VERSION}）")
  ops = plan.get("ops")
  if not isinstance(ops, list):
    errors.append("ops 须为数组")
    return errors
  if not ops:
    errors.append("ops 为空")
  for i, op in enumerate(ops):
    if not isinstance(op, dict):
      errors.append(f"ops[{i}] 须为对象")
      continue
    kind = op.get("op")
    if kind == "rename_symbol":
      errors.extend(_validate_rename_op(op, repo_root, prefix=f"ops[{i}]"))
    else:
      errors.append(f"ops[{i}] 未知 op: {kind!r}")
  return errors


def _validate_rename_op(op: dict[str, Any], repo_root: Path, *, prefix: str) -> list[str]:
  errors: list[str] = []
  rk = op.get("kind")
  if rk not in _RENAME_KINDS:
    errors.append(f"{prefix}: kind 须为 field/method/class/function，得到 {rk!r}")
  module = op.get("module")
  if not isinstance(module, str) or not module.strip():
    errors.append(f"{prefix}: module 必填")
  else:
    path = _module_to_path(repo_root, module)
    if not path.is_file():
      errors.append(f"{prefix}: 模块文件不存在: {path}")
  old = op.get("from")
  new = op.get("to")
  if not isinstance(old, str) or not isinstance(new, str):
    errors.append(f"{prefix}: from/to 须为字符串")
  else:
    try:
      _validate_ident(old, label=f"{prefix}.from")
      _validate_ident(new, label=f"{prefix}.to")
    except PlanError as exc:
      errors.append(str(exc))
    if old == new:
      errors.append(f"{prefix}: from 与 to 相同")
  if rk in {"field", "method"}:
    owner = op.get("owner")
    if not isinstance(owner, str) or not owner.strip():
      errors.append(f"{prefix}: field/method 须指定 owner（类名）")
    elif not _IDENT_RE.match(owner):
      errors.append(f"{prefix}: owner 非法标识符: {owner!r}")
  return errors


class _RenameFieldTransformer(ast.NodeTransformer):
  def __init__(self, owner: str, old: str, new: str) -> None:
    self.owner = owner
    self.old = old
    self.new = new
    self._in_owner = False

  def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
    if node.name != self.owner:
      return node
    prev = self._in_owner
    self._in_owner = True
    node = self.generic_visit(node)
    self._in_owner = prev
    return node

  def visit_AnnAssign(self, node: ast.AnnAssign) -> ast.AST:
    self.generic_visit(node)
    if self._in_owner and isinstance(node.target, ast.Name) and node.target.id == self.old:
      node.target.id = self.new
    return node

  def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
    self.generic_visit(node)
    if (
      self._in_owner
      and isinstance(node.value, ast.Name)
      and node.value.id == "self"
      and node.attr == self.old
    ):
      node.attr = self.new
    return node


class _RenameMethodTransformer(ast.NodeTransformer):
  def __init__(self, owner: str, old: str, new: str) -> None:
    self.owner = owner
    self.old = old
    self.new = new
    self._in_owner = False

  def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
    if node.name != self.owner:
      return node
    prev = self._in_owner
    self._in_owner = True
    for stmt in node.body:
      if isinstance(stmt, ast.FunctionDef) and stmt.name == self.old:
        stmt.name = self.new
    node = self.generic_visit(node)
    self._in_owner = prev
    return node

  def visit_Call(self, node: ast.Call) -> ast.AST:
    self.generic_visit(node)
    if not self._in_owner:
      return node
    func = node.func
    if (
      isinstance(func, ast.Attribute)
      and isinstance(func.value, ast.Name)
      and func.value.id == "self"
      and func.attr == self.old
    ):
      func.attr = self.new
    return node


class _RenameClassTransformer(ast.NodeTransformer):
  def __init__(self, old: str, new: str) -> None:
    self.old = old
    self.new = new

  def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
    if node.name == self.old:
      node.name = self.new
    return self.generic_visit(node)

  def visit_Name(self, node: ast.Name) -> ast.AST:
    if isinstance(node.ctx, ast.Load) and node.id == self.old:
      node.id = self.new
    return node


class _RenameFunctionTransformer(ast.NodeTransformer):
  def __init__(self, old: str, new: str) -> None:
    self.old = old
    self.new = new

  def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
    if node.name == self.old:
      node.name = self.new
    return self.generic_visit(node)

  def visit_Call(self, node: ast.Call) -> ast.AST:
    self.generic_visit(node)
    if isinstance(node.func, ast.Name) and node.func.id == self.old:
      node.func.id = self.new
    return node


def _rename_symbol_in_source(source: str, op: dict[str, Any]) -> str:
  tree = ast.parse(source)
  kind = op["kind"]
  old = op["from"]
  new = op["to"]
  if kind == "field":
    transformer: ast.NodeTransformer = _RenameFieldTransformer(op["owner"], old, new)
  elif kind == "method":
    transformer = _RenameMethodTransformer(op["owner"], old, new)
  elif kind == "class":
    transformer = _RenameClassTransformer(old, new)
  elif kind == "function":
    transformer = _RenameFunctionTransformer(old, new)
  else:
    raise PlanError(f"未知 rename kind: {kind}")
  new_tree = transformer.visit(tree)
  ast.fix_missing_locations(new_tree)
  return ast.unparse(new_tree) + ("\n" if source.endswith("\n") else "")


def _apply_rename_op(repo_root: Path, op: dict[str, Any]) -> FileChange:
  path = _module_to_path(repo_root, op["module"])
  old_text = path.read_text(encoding="utf-8")
  new_text = _rename_symbol_in_source(old_text, op)
  if new_text == old_text:
    raise PlanError(f"rename 未产生变更: {path}")
  try:
    ast.parse(new_text)
  except SyntaxError as exc:
    raise PlanError(f"改写后语法错误 {path}: {exc}") from exc
  return FileChange(path=path, old_text=old_text, new_text=new_text)


def apply_plan(
  plan: dict[str, Any],
  repo_root: Path,
  *,
  write: bool = False,
) -> ApplyResult:
  result = ApplyResult()
  errors = validate_plan(plan, repo_root)
  if errors:
    result.errors = errors
    return result

  pending: dict[Path, FileChange] = {}
  try:
    for op in plan["ops"]:
      if op.get("op") != "rename_symbol":
        continue
      change = _apply_rename_op(repo_root, op)
      if change.path in pending:
        merged = _rename_symbol_in_source(pending[change.path].new_text, op)
        pending[change.path] = FileChange(
          path=change.path,
          old_text=pending[change.path].old_text,
          new_text=merged,
        )
      else:
        pending[change.path] = change
  except PlanError as exc:
    result.errors.append(str(exc))
    return result

  result.changes = list(pending.values())
  if write:
    for ch in result.changes:
      ch.path.write_text(ch.new_text, encoding="utf-8")
  return result
