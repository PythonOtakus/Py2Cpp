"""Pass 合成 / 内联方法：Paw 源 → ``MidFunction``（``Dialect.PAW``）。

长期合成路径应直接写 Paw 源再 ``parse_mid_method``；``ast_function_to_mid`` 仅过渡
（AST 克隆体 → unparse → 改写 ``static def`` → PAW parse），勿当作终态依赖。
"""
from __future__ import annotations

import host.tree_nodes as ast
import copy
import textwrap
from typing import TYPE_CHECKING

from compiler.py.mid.mutate import append_mid_method, mid_class_for_info
from compiler.py.mid.nodes import MidFunction

if TYPE_CHECKING:
  from ..analysis.ir import ClassInfo
  from ..translator import Translator


def parse_mid_method(src: str, *, path: str = "<synthetic>.paw") -> MidFunction:
  """生成方法源（Paw 表面）→ ``MidFunction``（不经 ``ast_from_mid``）。"""
  dedented = textwrap.dedent(src)
  from ..frontend.api import parse_module
  from ..frontend.dialect import Dialect

  parsed = parse_module(
    dedented,
    path=path,
    dialect=Dialect.PAW,
    use_cache=False,
  )
  if parsed.mid is None:
    raise SyntaxError(f"未能得到 MidIR:\n{dedented}")
  fns = [it for it in parsed.mid.items if isinstance(it, MidFunction)]
  if len(fns) != 1:
    raise SyntaxError(
      f"expected 1 MidFunction, got {len(fns)} "
      f"({len(parsed.mid.items)} items):\n{dedented}"
    )
  return fns[0]


def bridge_mid_method_to_ast(
  method: MidFunction, *, filename: str,
) -> ast.FunctionDef | ast.AsyncFunctionDef:
  """临时桥：``MidFunction`` → ``FunctionDef`` / ``AsyncFunctionDef``。"""
  from compiler.py.mid.tree_from_mid import stmts_from_mid_function

  stmts = stmts_from_mid_function(method, filename=filename)
  fns = [
    s for s in stmts
    if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef))
  ]
  if len(fns) != 1:
    raise SyntaxError(
      f"Mid→AST bridge expected 1 FunctionDef/AsyncFunctionDef, "
      f"got {len(fns)} ({method.name})"
    )
  fn = fns[0]
  ast.fix_missing_locations(fn)
  return fn


def _has_staticmethod_decorator(
  fn: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
  return any(
    isinstance(d, ast.Name) and d.id == "staticmethod" for d in fn.decorator_list
  )


def _legacy_type_markers_to_paw(src: str) -> str:
  """物化遗留 ``T @ref`` / ``T @lazy`` → Paw ``ref T`` / ``lazy T``（可叠 ``lazy ref T``）。"""
  import re

  # 反复剥尾缀标记，直至稳定（``T @ref @lazy`` → ``lazy ref T``）
  prev = None
  cur = src
  while prev != cur:
    prev = cur
    cur = re.sub(
      r"([A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]*\])?)\s*@\s*lazy\b",
      r"lazy \1",
      cur,
    )
    cur = re.sub(
      r"([A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]*\])?)\s*@\s*ref\b",
      r"ref \1",
      cur,
    )
  return cur


def function_def_to_paw_source(
  fn: ast.FunctionDef | ast.AsyncFunctionDef,
) -> str:
  """``ast.FunctionDef`` → Paw 方法源；``@staticmethod`` 改写为 ``static def``。"""
  work = copy.deepcopy(fn)
  is_static = _has_staticmethod_decorator(work)
  if is_static:
    work.decorator_list = [
      d
      for d in work.decorator_list
      if not (isinstance(d, ast.Name) and d.id == "staticmethod")
    ]
  src = _legacy_type_markers_to_paw(ast.unparse(work))
  if not is_static:
    return src
  lines = src.splitlines()
  for i, line in enumerate(lines):
    stripped = line.lstrip()
    indent = line[: len(line) - len(stripped)]
    if stripped.startswith("async def "):
      lines[i] = f"{indent}static async def {stripped[len('async def '):]}"
      break
    if stripped.startswith("def "):
      lines[i] = f"{indent}static def {stripped[len('def '):]}"
      break
  return "\n".join(lines)


def ast_function_to_mid(
  fn: ast.FunctionDef | ast.AsyncFunctionDef,
  *,
  path: str = "<synthetic>.paw",
) -> MidFunction:
  """过渡：AST 方法 → Paw 源 → ``MidFunction``（勿长期依赖 unparse）。"""
  # 路径必须带 ``<…>``，以便跳过用户表面禁令扫描
  syn = path if "<" in path else f"<synthetic:{path}>"
  return parse_mid_method(function_def_to_paw_source(fn), path=syn)


def append_method_mid(
  tr: Translator,
  info: ClassInfo,
  method: MidFunction,
) -> None:
  """将 ``MidFunction`` 挂到 ``tr.module_mids`` 对应 ``MidClass``。"""
  mid_cls = mid_class_for_info(tr, info)
  if mid_cls is not None:
    append_mid_method(mid_cls, method)


def register_mid_method_on_classinfo(
  tr: Translator,
  info: ClassInfo,
  method: MidFunction,
  *,
  append_to_body: bool = True,
) -> ast.FunctionDef:
  """回写 ``module_mids``，并桥接 AST 写入 ``ClassInfo.methods``（过渡期）。"""
  append_method_mid(tr, info, method)
  info.mid_methods[method.name] = method
  ast_fn = bridge_mid_method_to_ast(
    method, filename=info.module_path or "<synthetic>",
  )
  info.methods[ast_fn.name] = ast_fn
  if append_to_body:
    info.node.body.append(ast_fn)
  info._collect_fields(ast_fn)
  return ast_fn
