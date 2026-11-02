"""RefactorPlan 解析、校验与 AST 改写（P0：单模块 ``rename_symbol``；P1：``update_select_path`` / select 联动）。"""
from __future__ import annotations

import ast
import difflib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ..passes.kwargs_options import TRANSLATOR_ONLY_METHODS
from ..passes.selector_parse import SelectorParseError, parse_selector_path

PLAN_VERSION = 1
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_RENAME_KINDS = frozenset({"field", "method", "class", "function"})
_SCAN_ROOTS = ("py2cpp", "test", "examples")
_SELECT_RE = re.compile(r"""\.select\s*\(\s*(['"])(.+?)\1""")


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
    elif kind == "update_select_path":
      errors.extend(_validate_update_select_path_op(op, repo_root, prefix=f"ops[{i}]"))
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


def _validate_selector_path(path: str, *, label: str) -> str | None:
  try:
    parse_selector_path(path)
  except SelectorParseError as exc:
    return f"{label} selector 无效: {exc}"
  return None


def _validate_update_select_path_op(op: dict[str, Any], repo_root: Path, *, prefix: str) -> list[str]:
  errors: list[str] = []
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
    if old == new:
      errors.append(f"{prefix}: from 与 to 相同")
    else:
      for label, value in (("from", old), ("to", new)):
        msg = _validate_selector_path(value, label=f"{prefix}.{label}")
        if msg:
          errors.append(msg)
  return errors


def _rewrite_field_in_select_path(path: str, old: str, new: str) -> str:
  if old == new or not old:
    return path
  updated = re.sub(
    r"(\.)" + re.escape(old) + r"(?=[\s}.>\]:,@?&|)]|$)",
    r"\1" + new,
    path,
  )
  updated = re.sub(
    r"(\{\s*\.)" + re.escape(old) + r"(?=[\s}>])",
    r"\1" + new,
    updated,
  )
  if updated == path:
    return path
  try:
    parse_selector_path(updated)
  except SelectorParseError:
    return path
  return updated


def _map_select_literals(
  source: str,
  mapper: Callable[[str], str],
) -> str:
  def regex_repl(match: re.Match[str]) -> str:
    quote, old_path = match.group(1), match.group(2)
    new_path = mapper(old_path)
    if new_path == old_path:
      return match.group(0)
    return f".select({quote}{new_path}{quote}"

  return _SELECT_RE.sub(regex_repl, source)


def _replace_select_path_literal(source: str, old_path: str, new_path: str) -> str:
  if old_path == new_path:
    return source
  return _map_select_literals(
    source,
    lambda path: new_path if path == old_path else path,
  )


def _rewrite_field_in_select_literals(source: str, old_field: str, new_field: str) -> str:
  return _map_select_literals(
    source,
    lambda path: _rewrite_field_in_select_path(path, old_field, new_field),
  )


def _iter_architect_python_files(repo_root: Path) -> list[Path]:
  files: list[Path] = []
  for rel in _SCAN_ROOTS:
    root = repo_root / rel
    if not root.is_dir():
      continue
    files.extend(sorted(root.rglob("*.py")))
  return files


def _select_literal_changes_for_field_rename(
  repo_root: Path,
  old_field: str,
  new_field: str,
) -> list[FileChange]:
  changes: list[FileChange] = []
  for path in _iter_architect_python_files(repo_root):
    try:
      old_text = path.read_text(encoding="utf-8")
    except OSError:
      continue
    new_text = _rewrite_field_in_select_literals(old_text, old_field, new_field)
    if new_text != old_text:
      changes.append(FileChange(path=path, old_text=old_text, new_text=new_text))
  return changes


def _merge_change(pending: dict[Path, FileChange], change: FileChange) -> None:
  if change.path in pending:
    pending[change.path] = FileChange(
      path=change.path,
      old_text=pending[change.path].old_text,
      new_text=change.new_text,
    )
  else:
    pending[change.path] = change


def _apply_update_select_path(repo_root: Path, op: dict[str, Any]) -> FileChange:
  path = _module_to_path(repo_root, op["module"])
  old_text = path.read_text(encoding="utf-8")
  new_text = _replace_select_path_literal(old_text, op["from"], op["to"])
  if new_text == old_text:
    raise PlanError(
      f"update_select_path 未产生变更: {path} ({op['from']!r})",
    )
  try:
    ast.parse(new_text)
  except SyntaxError as exc:
    raise PlanError(f"改写后语法错误 {path}: {exc}") from exc
  return FileChange(path=path, old_text=old_text, new_text=new_text)


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
      op_kind = op.get("op")
      if op_kind == "rename_symbol":
        change = _apply_rename_op(repo_root, op)
        if change.path in pending:
          merged = _rename_symbol_in_source(pending[change.path].new_text, op)
          _merge_change(
            pending,
            FileChange(
              path=change.path,
              old_text=pending[change.path].old_text,
              new_text=merged,
            ),
          )
        else:
          _merge_change(pending, change)
        if op.get("kind") == "field" and op.get("update_select_literals", True):
          for extra in _select_literal_changes_for_field_rename(
            repo_root,
            op["from"],
            op["to"],
          ):
            if extra.path in pending:
              merged = _rewrite_field_in_select_literals(
                pending[extra.path].new_text,
                op["from"],
                op["to"],
              )
              _merge_change(
                pending,
                FileChange(
                  path=extra.path,
                  old_text=pending[extra.path].old_text,
                  new_text=merged,
                ),
              )
            else:
              _merge_change(pending, extra)
      elif op_kind == "update_select_path":
        change = _apply_update_select_path(repo_root, op)
        if change.path in pending:
          merged = _replace_select_path_literal(
            pending[change.path].new_text,
            op["from"],
            op["to"],
          )
          _merge_change(
            pending,
            FileChange(
              path=change.path,
              old_text=pending[change.path].old_text,
              new_text=merged,
            ),
          )
        else:
          _merge_change(pending, change)
  except PlanError as exc:
    result.errors.append(str(exc))
    return result

  result.changes = list(pending.values())
  if write:
    for ch in result.changes:
      ch.path.write_text(ch.new_text, encoding="utf-8")
  return result
